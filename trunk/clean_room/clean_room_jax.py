"""
Hierarchical country-scale load generator (JAX/Flax version)
===========================================================

This file mirrors the Torch implementation but uses:
- JAX for array compute and autodiff
- Flax (linen) for modules (GRU, embeddings, MLPs)
- Optax for optimizers

Guarantees
----------
1) sum_i P_i(t) == P_agg(t) exactly (via simplex shares + reconstruction)
2) Aggregate mean anchoring supported (global or monthly)

Hard constraint from user
------------------------
- Never use "*" as an argument in any function signature.
- Add reStructuredText docstrings to all functions.

Input conventions
-----------------
- timestamps: ndarray (T,), Unix seconds int64
- P: ndarray (T,N), device power float, may contain NaNs
- region_id: ndarray (N,), int region index in [0..R-1]
- temp: ndarray (T,R) (or (T,) / (T,1)), regional temperature float

Notes
-----
- The aggregate model uses temp[:,0] as a national proxy by default.
- Share model is cross-sectional at each t: predicts N shares conditioned on calendar,
  device-region temperature and y_agg(t).
- CPU-only JAX installs do not expose a "gpu" platform. Device selection below is safe.

"""

from __future__ import annotations

import json
import math
import os
import zipfile
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

import jax
import jax.numpy as jnp

import flax.linen as nn
from flax.serialization import to_bytes, from_bytes
from flax.training import train_state

import optax

import matplotlib.pyplot as plt


# ----------------------------------------------------------------------------------------------------------------------
# 1) DEVICE SELECTION (JAX)
# ----------------------------------------------------------------------------------------------------------------------
def select_jax_device(prefer_gpu: bool, verbose: bool) -> jax.Device:
    """
    Select a JAX device safely even on CPU-only installs.

    Strategy
    --------
    - If prefer_gpu is False -> CPU.
    - Else -> search existing devices for platform == "gpu".
      If none -> CPU.

    :param prefer_gpu: Try GPU if True.
    :param verbose: Print diagnostics if True.
    :returns: A JAX device (GPU if present else CPU).
    """
    cpu_dev = jax.devices("cpu")[0]

    if not prefer_gpu:
        if verbose:
            print("[device] Using CPU (prefer_gpu=False)")
        return cpu_dev

    try:
        gpus = [d for d in jax.devices() if getattr(d, "platform", "") == "gpu"]
    except Exception:
        gpus = []

    if len(gpus) == 0:
        if verbose:
            print("[device] GPU backend not available, using CPU")
        return cpu_dev

    if verbose:
        print(f"[device] GPU OK: {gpus[0]}")
    return gpus[0]


# ----------------------------------------------------------------------------------------------------------------------
# 2) TIME GRID + CALENDAR FEATURES
# ----------------------------------------------------------------------------------------------------------------------
@dataclass
class TimeGrid:
    """
    Time grid diagnostics.

    :param dt_seconds: Dominant timestep in seconds.
    :param is_regular: True if timestamp jitter is within tolerance.
    :param jitter_frac_p95: 95th percentile of relative jitter wrt dt.
    """
    dt_seconds: int
    is_regular: bool
    jitter_frac_p95: float


def infer_time_grid(timestamps: np.ndarray, jitter_tol: float) -> TimeGrid:
    """
    Infer dominant timestep and regularity from Unix timestamps.

    :param timestamps: Unix timestamps (seconds), shape ``(T,)``.
    :param jitter_tol: Relative tolerance for regularity check.
    :returns: :class:`TimeGrid`.
    """
    ts = np.asarray(timestamps, dtype=np.int64)
    dts = np.diff(ts)
    dts = dts[dts > 0]
    if dts.size == 0:
        raise ValueError("Not enough timestamps to infer dt.")
    vals, counts = np.unique(dts, return_counts=True)
    dt_mode = int(vals[np.argmax(counts)])
    jitter = np.abs(dts - dt_mode) / max(dt_mode, 1)
    jitter_p95 = float(np.percentile(jitter, 95))
    return TimeGrid(
        dt_seconds=dt_mode,
        is_regular=(jitter_p95 <= float(jitter_tol)),
        jitter_frac_p95=jitter_p95,
    )


def calendar_features_unix(timestamps: np.ndarray) -> np.ndarray:
    """
    Compute resolution-independent calendar features from Unix timestamps.

    Features (columns)
    ------------------
    - sin/cos hour-of-day
    - sin/cos day-of-week
    - sin/cos day-of-year
    - weekend flag

    :param timestamps: Unix timestamps (seconds), shape ``(T,)``.
    :returns: Feature matrix, shape ``(T, Fcal)`` (float32).
    """
    ts = np.asarray(timestamps, dtype=np.int64)
    sec_day = 86400
    sec_week = 7 * sec_day
    sec_year = 365 * sec_day

    tod = (ts % sec_day) / sec_day
    dow = (ts % sec_week) / sec_week
    doy = (ts % sec_year) / sec_year

    feats = [
        np.sin(2 * np.pi * tod), np.cos(2 * np.pi * tod),
        np.sin(2 * np.pi * dow), np.cos(2 * np.pi * dow),
        np.sin(2 * np.pi * doy), np.cos(2 * np.pi * doy),
        (dow >= (5 / 7)).astype(np.float32),
    ]
    return np.stack(feats, axis=1).astype(np.float32)


# ----------------------------------------------------------------------------------------------------------------------
# 3) DATA HELPERS
# ----------------------------------------------------------------------------------------------------------------------
def ensure_2d_temp(temp: np.ndarray) -> np.ndarray:
    """
    Ensure temperature array has shape ``(T,R)``.

    :param temp: Temperature array. Accepted shapes: ``(T,)``, ``(T,1)``, ``(T,R)``.
    :returns: Temperature array ``(T,R)`` (float32).
    """
    arr = np.asarray(temp, dtype=np.float32)
    if arr.ndim == 1:
        arr = arr[:, None]
    return arr


def compute_aggregate(P: np.ndarray) -> np.ndarray:
    """
    Compute aggregate series from device matrix.

    :param P: Power matrix ``(T,N)``, may contain NaNs.
    :returns: Aggregate power ``(T,)`` (float32).
    """
    return np.nansum(P, axis=1).astype(np.float32)


def stable_shares(P: np.ndarray, eps: float) -> np.ndarray:
    """
    Compute per-time shares:

        s(t,i) = P(t,i) / sum_j P(t,j)

    with stabilization in the denominator.

    :param P: Power matrix ``(T,N)``, NaNs allowed.
    :param eps: Epsilon added to the per-time denominator.
    :returns: Shares matrix ``(T,N)`` (float32).
    """
    P_clean = np.nan_to_num(np.asarray(P, dtype=np.float32), nan=0.0)
    denom = np.sum(P_clean, axis=1, keepdims=True) + float(eps)
    return (P_clean / denom).astype(np.float32)


def compute_month_index(timestamps: np.ndarray) -> np.ndarray:
    """
    Compute a month index ``0..11`` from Unix timestamps (approx).

    This uses a simplified 365-day year mapping (no leap years). It is intended
    for anchoring only.

    :param timestamps: Unix timestamps (seconds), shape ``(T,)``.
    :returns: Month indices, shape ``(T,)`` (int64).
    """
    ts = np.asarray(timestamps, dtype=np.int64)
    sec_day = 86400
    day_of_year = ((ts // sec_day) % 365).astype(np.int64)
    bounds = np.array([31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334, 365], dtype=np.int64)
    month = np.zeros_like(day_of_year)
    for m in range(12):
        month = np.where(day_of_year < bounds[m], m, month)
    return month.astype(np.int64)


# ----------------------------------------------------------------------------------------------------------------------
# 4) BATCH SAMPLERS (NumPy)
# ----------------------------------------------------------------------------------------------------------------------
def sample_aggregate_batch(
    rng: np.random.Generator,
    y: np.ndarray,
    temp: np.ndarray,
    cal: np.ndarray,
    context_len: int,
    batch_size: int,
) -> Dict[str, np.ndarray]:
    """
    Sample a random aggregate training batch.

    :param rng: NumPy RNG.
    :param y: Log aggregate series ``(T,)``.
    :param temp: Temperature matrix ``(T,R)``.
    :param cal: Calendar features ``(T,F)``.
    :param context_len: Context length ``L``.
    :param batch_size: Batch size ``B``.
    :returns: Dict with keys: y_ctx, temp_hist, cal_t, temp_t, y_next.
    """
    T = int(y.shape[0])
    L = int(context_len)
    B = int(batch_size)
    if T <= L + 1:
        raise ValueError("Not enough time steps for chosen context_len.")

    t = rng.integers(low=L, high=T - 1, size=B, dtype=np.int64)
    idx_ctx = (t[:, None] - L + np.arange(L)[None, :]).astype(np.int64)

    y_ctx = y[idx_ctx].astype(np.float32)
    y_next = y[t].astype(np.float32)[:, None]
    temp_hist = temp[idx_ctx, 0:1].astype(np.float32)
    cal_t = cal[t].astype(np.float32)
    temp_t = temp[t, 0:1].astype(np.float32)

    return {
        "y_ctx": y_ctx,
        "temp_hist": temp_hist,
        "cal_t": cal_t,
        "temp_t": temp_t,
        "y_next": y_next,
    }


def sample_share_batch(
    rng: np.random.Generator,
    share: np.ndarray,
    temp_dev: np.ndarray,
    cal: np.ndarray,
    y_agg: np.ndarray,
    batch_size: int,
) -> Dict[str, np.ndarray]:
    """
    Sample a random share training batch (cross-section at time t).

    :param rng: NumPy RNG.
    :param share: Target shares ``(T,N)``.
    :param temp_dev: Device temperature ``(T,N)`` (mapped via region_id).
    :param cal: Calendar features ``(T,F)``.
    :param y_agg: Log aggregate ``(T,)``.
    :param batch_size: Batch size ``B`` (time-slices per update).
    :returns: Dict with keys: cal_t, temp_dev_t, y_agg_t, share_t.
    """
    T = int(share.shape[0])
    B = int(batch_size)
    t = rng.integers(low=0, high=T, size=B, dtype=np.int64)

    return {
        "cal_t": cal[t].astype(np.float32),
        "temp_dev_t": temp_dev[t].astype(np.float32),
        "y_agg_t": y_agg[t].astype(np.float32)[:, None],
        "share_t": share[t].astype(np.float32),
    }


# ----------------------------------------------------------------------------------------------------------------------
# 5) MODELS (Flax)
# ----------------------------------------------------------------------------------------------------------------------
class AggregateARModel(nn.Module):
    """
    Aggregate one-step probabilistic model.

    Learns
    ------
    ``y_agg(t) = log(P_agg(t) + eps_agg)``

    Predicts
    --------
    Normal distribution parameters ``(mu, sigma)`` for the next step.
    """
    cal_dim: int
    hidden: int
    input_proj: int

    @nn.compact
    def __call__(
        self,
        y_ctx: jnp.ndarray,
        temp_hist: jnp.ndarray,
        cal_t: jnp.ndarray,
        temp_t: jnp.ndarray,
    ) -> Tuple[jnp.ndarray, jnp.ndarray]:
        """
        Forward pass.

        :param y_ctx: Tensor ``(B,L)``.
        :param temp_hist: Tensor ``(B,L,1)``.
        :param cal_t: Tensor ``(B,F)``.
        :param temp_t: Tensor ``(B,1)``.
        :returns: ``(mu, sigma)`` each shape ``(B,1)``.
        """
        x = jnp.concatenate([y_ctx[..., None], temp_hist], axis=-1)  # (B,L,2)
        x = nn.Dense(self.input_proj, name="in_proj")(x)

        # Flax GRUCell requires features in recent versions
        cell = nn.GRUCell(features=self.hidden, name="gru_cell")
        rnn = nn.RNN(cell, return_carry=True, name="gru_rnn")

        B = x.shape[0]
        init_carry = jnp.zeros((B, self.hidden), dtype=x.dtype)

        carry, _ = rnn(x, initial_carry=init_carry)
        h = carry

        feat = jnp.concatenate([h, cal_t, temp_t], axis=-1)

        z = nn.LayerNorm(name="head_ln")(feat)
        z = nn.Dense(128, name="head_fc1")(z)
        z = jax.nn.gelu(z)
        z = nn.Dense(64, name="head_fc2")(z)
        z = jax.nn.gelu(z)

        mu = nn.Dense(1, name="mu")(z)
        log_sigma = nn.Dense(1, name="log_sigma")(z)
        sigma = jax.nn.softplus(log_sigma) + 1e-4
        return mu, sigma


class ShareSoftmaxModel(nn.Module):
    """
    Simplex-constrained share model.

    Produces logits for all devices at a given time t and later uses softmax
    to obtain shares on the simplex.

    Supports chunking over devices to reduce peak memory.
    """
    n_devices: int
    n_regions: int
    cal_dim: int
    dev_emb_dim: int
    reg_emb_dim: int
    hidden: int

    @nn.compact
    def __call__(
        self,
        cal_t: jnp.ndarray,
        temp_dev_t: jnp.ndarray,
        y_agg_t: jnp.ndarray,
        region_id: jnp.ndarray,
        chunk_size: int,
    ) -> jnp.ndarray:
        """
        Compute logits for all devices.

        :param cal_t: Tensor ``(B,F)``.
        :param temp_dev_t: Tensor ``(B,N)``.
        :param y_agg_t: Tensor ``(B,1)``.
        :param region_id: Tensor ``(N,)`` with region index per device.
        :param chunk_size: If ``>0``, process devices in chunks.
        :returns: Logits tensor ``(B,N)``.
        """
        B = int(cal_t.shape[0])
        N = int(self.n_devices)

        dev_emb = nn.Embed(num_embeddings=self.n_devices, features=self.dev_emb_dim, name="dev_emb")
        reg_emb = nn.Embed(num_embeddings=self.n_regions, features=self.reg_emb_dim, name="reg_emb")

        feat_dim = int(self.dev_emb_dim + self.reg_emb_dim + self.cal_dim + 1 + 1)

        # Create MLP submodules once and reuse across all chunks
        mlp_ln = nn.LayerNorm(name="mlp_ln")
        mlp_fc1 = nn.Dense(self.hidden, name="mlp_fc1")
        mlp_fc2 = nn.Dense(self.hidden, name="mlp_fc2")
        mlp_out = nn.Dense(1, name="mlp_out")

        def mlp_apply(x: jnp.ndarray) -> jnp.ndarray:
            """
            Per-device MLP block.

            :param x: Tensor ``(M, feat_dim)``.
            :returns: Tensor ``(M, 1)``.
            """
            z = mlp_ln(x)
            z = mlp_fc1(z)
            z = jax.nn.gelu(z)
            z = mlp_fc2(z)
            z = jax.nn.gelu(z)
            z = mlp_out(z)
            return z

        if chunk_size is None or int(chunk_size) <= 0:
            chunk_size_eff = N
        else:
            chunk_size_eff = int(chunk_size)

        logits_chunks: List[jnp.ndarray] = []
        start = 0
        while start < N:
            end = min(N, start + chunk_size_eff)
            k = int(end - start)

            dev_ids = jnp.arange(start, end, dtype=jnp.int32)
            reg_ids = region_id[start:end].astype(jnp.int32)

            dev_e = dev_emb(dev_ids)[None, :, :]
            reg_e = reg_emb(reg_ids)[None, :, :]

            dev_e = jnp.broadcast_to(dev_e, (B, k, self.dev_emb_dim))
            reg_e = jnp.broadcast_to(reg_e, (B, k, self.reg_emb_dim))

            cal_rep = jnp.broadcast_to(cal_t[:, None, :], (B, k, self.cal_dim))
            y_rep = jnp.broadcast_to(y_agg_t[:, None, :], (B, k, 1))
            temp_rep = temp_dev_t[:, start:end][:, :, None]

            feat = jnp.concatenate([dev_e, reg_e, cal_rep, temp_rep, y_rep], axis=-1)
            feat2 = feat.reshape((B * k, feat_dim))

            out = mlp_apply(feat2).reshape((B, k))
            logits_chunks.append(out)

            start = end

        return jnp.concatenate(logits_chunks, axis=1)


# ----------------------------------------------------------------------------------------------------------------------
# 6) LOSSES
# ----------------------------------------------------------------------------------------------------------------------
def gaussian_nll(y: jnp.ndarray, mu: jnp.ndarray, sigma: jnp.ndarray) -> jnp.ndarray:
    """
    Gaussian negative log-likelihood.

    :param y: Target tensor ``(B,1)``.
    :param mu: Mean tensor ``(B,1)``.
    :param sigma: Std dev tensor ``(B,1)``.
    :returns: Scalar loss tensor.
    """
    nll = 0.5 * math.log(2 * math.pi) + jnp.log(sigma) + 0.5 * jnp.square((y - mu) / sigma)
    return jnp.mean(nll)


def share_kl_loss(logits: jnp.ndarray, target_share: jnp.ndarray) -> jnp.ndarray:
    """
    KL divergence KL(target || pred) where pred = softmax(logits).

    :param logits: Logits tensor ``(B,N)``.
    :param target_share: Target shares tensor ``(B,N)`` rows sum to 1.
    :returns: Scalar loss tensor.
    """
    log_pred = jax.nn.log_softmax(logits, axis=1)
    eps = 1e-12
    log_t = jnp.log(jnp.clip(target_share, a_min=eps, a_max=1.0))
    kl = jnp.sum(target_share * (log_t - log_pred), axis=1)
    return jnp.mean(kl)


# ----------------------------------------------------------------------------------------------------------------------
# 7) TRAINING (Optax + Flax TrainState)
# ----------------------------------------------------------------------------------------------------------------------
def make_aggregate_train_step(model: AggregateARModel) -> Any:
    """
    Create a JITted aggregate training step.

    :param model: Aggregate model.
    :returns: A function (state, batch) -> (new_state, loss).
    """
    def step_fn(state: train_state.TrainState, batch: Dict[str, jnp.ndarray]) -> Tuple[train_state.TrainState, jnp.ndarray]:
        """
        One optimisation step.

        :param state: Flax TrainState.
        :param batch: Batch dict.
        :returns: Updated state and scalar loss.
        """
        def loss_fn(params: Any) -> jnp.ndarray:
            """
            Loss closure.

            :param params: Parameters pytree.
            :returns: Scalar loss.
            """
            mu, sigma = model.apply(
                {"params": params},
                batch["y_ctx"],
                batch["temp_hist"],
                batch["cal_t"],
                batch["temp_t"],
            )
            return gaussian_nll(batch["y_next"], mu, sigma)

        loss, grads = jax.value_and_grad(loss_fn)(state.params)
        new_state = state.apply_gradients(grads=grads)
        return new_state, loss

    return jax.jit(step_fn)


def make_share_train_step(model: ShareSoftmaxModel) -> Any:
    """
    Create a JITted share training step.

    :param model: Share model.
    :returns: A function (state, batch, region_id, chunk_size) -> (new_state, loss).
    """
    def step_fn(
        state: train_state.TrainState,
        batch: Dict[str, jnp.ndarray],
        region_id: jnp.ndarray,
        chunk_size: int,
    ) -> Tuple[train_state.TrainState, jnp.ndarray]:
        """
        One optimisation step.

        :param state: Flax TrainState.
        :param batch: Batch dict.
        :param region_id: Region indices ``(N,)``.
        :param chunk_size: Chunk size (static for JIT compilation).
        :returns: Updated state and scalar loss.
        """
        def loss_fn(params: Any) -> jnp.ndarray:
            """
            Loss closure.

            :param params: Parameters pytree.
            :returns: Scalar loss.
            """
            logits = model.apply(
                {"params": params},
                batch["cal_t"],
                batch["temp_dev_t"],
                batch["y_agg_t"],
                region_id,
                int(chunk_size),
            )
            return share_kl_loss(logits, batch["share_t"])

        loss, grads = jax.value_and_grad(loss_fn)(state.params)
        new_state = state.apply_gradients(grads=grads)
        return new_state, loss

    return jax.jit(step_fn, static_argnums=(3,))


def train_aggregate_model(
    timestamps: np.ndarray,
    P_agg: np.ndarray,
    temp: np.ndarray,
    context_len: int,
    steps: int,
    batch_size: int,
    lr: float,
    prefer_gpu: bool,
    verbose: bool,
    eps_agg: float,
) -> Tuple[AggregateARModel, Any, List[float], Dict[str, Any]]:
    """
    Train the aggregate model.

    :param timestamps: Unix timestamps ``(T,)``.
    :param P_agg: Aggregate power ``(T,)``.
    :param temp: Temperature ``(T,R)``.
    :param context_len: Context length ``L``.
    :param steps: Optimisation steps.
    :param batch_size: Batch size.
    :param lr: Learning rate.
    :param prefer_gpu: Try GPU.
    :param verbose: Print progress.
    :param eps_agg: Epsilon for log stability.
    :returns: ``(model, params, losses, meta)``.
    """
    dev = select_jax_device(bool(prefer_gpu), bool(verbose))

    ts = np.asarray(timestamps, dtype=np.int64)
    cal = calendar_features_unix(ts)
    cal_dim = int(cal.shape[1])

    temp_arr = ensure_2d_temp(temp)
    P_agg_arr = np.asarray(P_agg, dtype=np.float32)
    y = np.log(np.maximum(P_agg_arr, 0.0) + float(eps_agg)).astype(np.float32)

    hidden = 96
    input_proj = 32
    model = AggregateARModel(cal_dim=cal_dim, hidden=hidden, input_proj=input_proj)

    key = jax.random.PRNGKey(0)
    with jax.default_device(dev):
        dummy_y_ctx = jnp.zeros((1, int(context_len)), dtype=jnp.float32)
        dummy_temp_hist = jnp.zeros((1, int(context_len), 1), dtype=jnp.float32)
        dummy_cal_t = jnp.zeros((1, cal_dim), dtype=jnp.float32)
        dummy_temp_t = jnp.zeros((1, 1), dtype=jnp.float32)

        variables = model.init(key, dummy_y_ctx, dummy_temp_hist, dummy_cal_t, dummy_temp_t)
        params = variables["params"]

    tx = optax.chain(
        optax.clip_by_global_norm(1.0),
        optax.adamw(learning_rate=float(lr), weight_decay=1e-4),
    )
    state = train_state.TrainState.create(apply_fn=model.apply, params=params, tx=tx)
    train_step = make_aggregate_train_step(model)

    rng = np.random.default_rng(0)
    losses: List[float] = []

    for k in range(1, int(steps) + 1):
        batch_np = sample_aggregate_batch(rng, y, temp_arr, cal, int(context_len), int(batch_size))
        batch = {name: jax.device_put(jnp.asarray(val), device=dev) for name, val in batch_np.items()}
        state, loss = train_step(state, batch)
        losses.append(float(loss))

        if verbose and (k % 500 == 0):
            print(f"[agg step {k:6d}] NLL={float(loss):.4f}")

    meta = {
        "device": str(dev),
        "cal_dim": int(cal_dim),
        "hidden": int(hidden),
        "input_proj": int(input_proj),
        "context_len": int(context_len),
        "eps_agg": float(eps_agg),
    }
    return model, state.params, losses, meta


def train_share_softmax_model(
    timestamps: np.ndarray,
    P: np.ndarray,
    region_id: np.ndarray,
    temp: np.ndarray,
    steps: int,
    batch_size: int,
    lr: float,
    prefer_gpu: bool,
    verbose: bool,
    eps_share_denominator: float,
    eps_agg: float,
    chunk_size: int,
) -> Tuple[ShareSoftmaxModel, Any, List[float], Dict[str, Any]]:
    """
    Train the simplex share model.

    :param timestamps: Unix timestamps ``(T,)``.
    :param P: Device power matrix ``(T,N)``.
    :param region_id: Region index per device ``(N,)``.
    :param temp: Temperature matrix ``(T,R)``.
    :param steps: Optimisation steps.
    :param batch_size: Batch size.
    :param lr: Learning rate.
    :param prefer_gpu: Try GPU.
    :param verbose: Print progress.
    :param eps_share_denominator: Epsilon for share denominator.
    :param eps_agg: Epsilon for aggregate log.
    :param chunk_size: Forward chunk size over devices (0 disables).
    :returns: ``(model, params, losses, meta)``.
    """
    dev = select_jax_device(bool(prefer_gpu), bool(verbose))

    ts = np.asarray(timestamps, dtype=np.int64)
    cal = calendar_features_unix(ts)
    cal_dim = int(cal.shape[1])

    P_arr = np.asarray(P, dtype=np.float32)
    temp_arr = ensure_2d_temp(temp)
    region_id_arr = np.asarray(region_id, dtype=np.int64)

    T, N = P_arr.shape
    R = int(temp_arr.shape[1])

    if region_id_arr.shape[0] != N:
        raise ValueError("region_id must have length N.")
    if temp_arr.shape[0] != T:
        raise ValueError("temp must have T rows.")

    share = stable_shares(P_arr, float(eps_share_denominator))
    P_agg = compute_aggregate(P_arr)
    y_agg = np.log(np.maximum(P_agg, 0.0) + float(eps_agg)).astype(np.float32)
    temp_dev = temp_arr[:, region_id_arr].astype(np.float32)

    model = ShareSoftmaxModel(
        n_devices=int(N),
        n_regions=int(R),
        cal_dim=int(cal_dim),
        dev_emb_dim=32,
        reg_emb_dim=8,
        hidden=128,
    )

    key = jax.random.PRNGKey(1)
    with jax.default_device(dev):
        dummy_cal = jnp.zeros((1, cal_dim), dtype=jnp.float32)
        dummy_temp = jnp.zeros((1, N), dtype=jnp.float32)
        dummy_y = jnp.zeros((1, 1), dtype=jnp.float32)
        dummy_region = jnp.zeros((N,), dtype=jnp.int32)

        variables = model.init(key, dummy_cal, dummy_temp, dummy_y, dummy_region, 0)
        params = variables["params"]

    tx = optax.chain(
        optax.clip_by_global_norm(1.0),
        optax.adamw(learning_rate=float(lr), weight_decay=1e-4),
    )
    state = train_state.TrainState.create(apply_fn=model.apply, params=params, tx=tx)
    train_step = make_share_train_step(model)

    rng = np.random.default_rng(1)
    losses: List[float] = []
    region_id_j = jax.device_put(jnp.asarray(region_id_arr, dtype=jnp.int32), device=dev)

    for k in range(1, int(steps) + 1):
        batch_np = sample_share_batch(rng, share, temp_dev, cal, y_agg, int(batch_size))
        batch = {name: jax.device_put(jnp.asarray(val), device=dev) for name, val in batch_np.items()}
        state, loss = train_step(state, batch, region_id_j, int(chunk_size))
        losses.append(float(loss))

        if verbose and (k % 500 == 0):
            print(f"[share step {k:6d}] KL={float(loss):.4f}")

    meta = {
        "device": str(dev),
        "cal_dim": int(cal_dim),
        "n_devices": int(N),
        "n_regions": int(R),
        "dev_emb_dim": 32,
        "reg_emb_dim": 8,
        "hidden": 128,
        "eps_share_denom": float(eps_share_denominator),
        "eps_agg": float(eps_agg),
        "chunk_size": int(chunk_size),
    }
    return model, state.params, losses, meta


# ----------------------------------------------------------------------------------------------------------------------
# 8) AGGREGATE SAMPLING + CORRECTIONS
# ----------------------------------------------------------------------------------------------------------------------
def sample_aggregate(
    model: AggregateARModel,
    params: Any,
    timestamps: np.ndarray,
    temp: np.ndarray,
    y_agg_init: np.ndarray,
    seed: int,
    sigma_damp: float,
    prefer_gpu: bool,
    verbose: bool,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Sample y_agg(t) auto-regressively and return per-step effective sigma.

    Effective sigma used for sampling:
        sigma_eff = sigma_damp * sigma

    :param model: Trained aggregate model.
    :param params: Aggregate model params pytree.
    :param timestamps: Unix timestamps ``(T,)``.
    :param temp: Temperature ``(T,R)``.
    :param y_agg_init: Initial context ``(L,)``.
    :param seed: RNG seed.
    :param sigma_damp: Multiplicative damping factor in [0,1].
    :param prefer_gpu: Try GPU.
    :param verbose: Print device diagnostics.
    :returns: ``(y_syn, sigma_eff_hist)`` each shape ``(T,)``.
    """
    dev = select_jax_device(bool(prefer_gpu), bool(verbose))
    ts = np.asarray(timestamps, dtype=np.int64)
    cal = calendar_features_unix(ts).astype(np.float32)
    temp_arr = ensure_2d_temp(temp).astype(np.float32)

    T = int(temp_arr.shape[0])
    L = int(y_agg_init.shape[0])
    if L <= 0:
        raise ValueError("y_agg_init must have length >= 1.")

    rng = np.random.default_rng(int(seed))

    y_ctx = np.asarray(y_agg_init, dtype=np.float32).copy()
    y_out = np.zeros(T, dtype=np.float32)
    sigma_eff_out = np.zeros(T, dtype=np.float32)

    for t in range(T):
        t0 = max(0, t - L)
        hist = temp_arr[t0:t, 0:1]
        if hist.shape[0] < L:
            pad = np.repeat(temp_arr[0:1, 0:1], repeats=(L - hist.shape[0]), axis=0)
            hist = np.concatenate([pad, hist], axis=0)

        y_ctx_j = jax.device_put(jnp.asarray(y_ctx[None, :], dtype=jnp.float32), device=dev)
        temp_hist_j = jax.device_put(jnp.asarray(hist[None, :, :], dtype=jnp.float32), device=dev)
        cal_t_j = jax.device_put(jnp.asarray(cal[t:t + 1], dtype=jnp.float32), device=dev)
        temp_t_j = jax.device_put(jnp.asarray(temp_arr[t:t + 1, 0:1], dtype=jnp.float32), device=dev)

        mu, sigma = model.apply({"params": params}, y_ctx_j, temp_hist_j, cal_t_j, temp_t_j)
        mu_f = float(mu[0, 0])
        sigma_f = float(sigma[0, 0])
        sigma_eff = float(sigma_damp) * sigma_f

        eps = float(rng.standard_normal())
        y_next = mu_f + sigma_eff * eps

        y_out[t] = float(y_next)
        sigma_eff_out[t] = float(sigma_eff)

        y_ctx[:-1] = y_ctx[1:]
        y_ctx[-1] = float(y_next)

    return y_out, sigma_eff_out


def lognormal_mean_correction(y: np.ndarray, sigma_eff: np.ndarray) -> np.ndarray:
    """
    Apply log-normal mean correction when mapping y to power:

        P = exp(y - 0.5 * sigma_eff^2)

    :param y: Log series ``(T,)``.
    :param sigma_eff: Effective sigma used in sampling ``(T,)``.
    :returns: Corrected power series ``(T,)``.
    """
    y_arr = np.asarray(y, dtype=np.float32)
    s_arr = np.asarray(sigma_eff, dtype=np.float32)
    return np.exp(y_arr - 0.5 * (s_arr ** 2)).astype(np.float32)


def anchor_log_mean_global(y_syn: np.ndarray, y_real: np.ndarray) -> np.ndarray:
    """
    Anchor synthetic log-series to match the real mean (global).

        y_syn := y_syn + (mean(y_real) - mean(y_syn))

    :param y_syn: Synthetic log series ``(T,)``.
    :param y_real: Real log series ``(T,)``.
    :returns: Mean-anchored synthetic log series ``(T,)``.
    """
    ys = np.asarray(y_syn, dtype=np.float32)
    yr = np.asarray(y_real, dtype=np.float32)
    delta = float(np.mean(yr) - np.mean(ys))
    return (ys + delta).astype(np.float32)


def anchor_log_mean_monthly(y_syn: np.ndarray, y_real: np.ndarray, timestamps: np.ndarray) -> np.ndarray:
    """
    Anchor synthetic log-series to match real mean per month.

    :param y_syn: Synthetic log series ``(T,)``.
    :param y_real: Real log series ``(T,)``.
    :param timestamps: Unix timestamps ``(T,)``.
    :returns: Month-anchored synthetic log series ``(T,)``.
    """
    ys = np.asarray(y_syn, dtype=np.float32).copy()
    yr = np.asarray(y_real, dtype=np.float32)
    month = compute_month_index(timestamps)

    for m in range(12):
        mask = (month == m)
        if not np.any(mask):
            continue
        delta = float(np.mean(yr[mask]) - np.mean(ys[mask]))
        ys[mask] = ys[mask] + delta

    return ys.astype(np.float32)


# ----------------------------------------------------------------------------------------------------------------------
# 9) SHARE SAMPLING (SIMPLEX)
# ----------------------------------------------------------------------------------------------------------------------
def sample_shares_softmax(
    model: ShareSoftmaxModel,
    params: Any,
    timestamps: np.ndarray,
    region_id: np.ndarray,
    temp: np.ndarray,
    y_agg: np.ndarray,
    seed: int,
    logit_noise_std: float,
    chunk_size: int,
    prefer_gpu: bool,
    verbose: bool,
) -> np.ndarray:
    """
    Sample shares s(t,:) using softmax(logits + noise), ensuring simplex constraints.

    :param model: Trained share model.
    :param params: Share model params pytree.
    :param timestamps: Unix timestamps ``(T,)``.
    :param region_id: Region per device ``(N,)``.
    :param temp: Temperature ``(T,R)``.
    :param y_agg: Log aggregate series ``(T,)`` used for conditioning.
    :param seed: RNG seed.
    :param logit_noise_std: Std of Gaussian noise added to logits before softmax.
    :param chunk_size: Forward chunk size over devices (0 disables).
    :param prefer_gpu: Try GPU.
    :param verbose: Print device diagnostics.
    :returns: Shares matrix ``(T,N)`` with row sums == 1 (numerical tolerance).
    """
    dev = select_jax_device(bool(prefer_gpu), bool(verbose))
    ts = np.asarray(timestamps, dtype=np.int64)
    cal_np = calendar_features_unix(ts).astype(np.float32)
    temp_arr = ensure_2d_temp(temp).astype(np.float32)
    region_id_np = np.asarray(region_id, dtype=np.int64)

    T = int(cal_np.shape[0])
    N = int(region_id_np.shape[0])

    rng = np.random.default_rng(int(seed))
    region_id_j = jax.device_put(jnp.asarray(region_id_np, dtype=jnp.int32), device=dev)
    temp_dev = temp_arr[:, region_id_np].astype(np.float32)

    out = np.zeros((T, N), dtype=np.float32)

    for t in range(T):
        cal_t = jax.device_put(jnp.asarray(cal_np[t:t + 1], dtype=jnp.float32), device=dev)
        temp_dev_t = jax.device_put(jnp.asarray(temp_dev[t:t + 1], dtype=jnp.float32), device=dev)
        y_agg_t = jax.device_put(jnp.asarray(np.array([[float(y_agg[t])]], dtype=np.float32)), device=dev)

        logits = model.apply({"params": params}, cal_t, temp_dev_t, y_agg_t, region_id_j, int(chunk_size))
        logits_np = np.asarray(logits[0], dtype=np.float32)

        if logit_noise_std is not None and float(logit_noise_std) > 0.0:
            logits_np = logits_np + float(logit_noise_std) * rng.standard_normal(size=(N,)).astype(np.float32)

        x = logits_np - float(np.max(logits_np))
        share = np.exp(x).astype(np.float32)
        share = share / (float(np.sum(share)) + 1e-12)

        out[t, :] = share

    return out


def reconstruct_power_from_shares(P_agg: np.ndarray, shares: np.ndarray) -> np.ndarray:
    """
    Reconstruct device powers from aggregate and shares.

    :param P_agg: Aggregate power ``(T,)``.
    :param shares: Shares ``(T,N)``.
    :returns: Device power matrix ``(T,N)``.
    """
    return (np.asarray(shares, dtype=np.float32) * np.asarray(P_agg, dtype=np.float32)[:, None]).astype(np.float32)


# ----------------------------------------------------------------------------------------------------------------------
# 10) ARTIFACT ZIP SAVE/LOAD (params bytes + JSON only)
# ----------------------------------------------------------------------------------------------------------------------
@dataclass
class HierarchicalZipSpec:
    """
    Serializable spec for training and generation.

    :param context_len: Aggregate context length L.
    :param steps_agg: Optimisation steps for aggregate model.
    :param steps_share: Optimisation steps for share model.
    :param batch_size_agg: Batch size for aggregate model.
    :param batch_size_share: Batch size for share model.
    :param lr_agg: Learning rate for aggregate model.
    :param lr_share: Learning rate for share model.
    :param prefer_gpu: Try to use GPU if available.
    :param verbose: Print diagnostics during training.
    :param eps_agg: Epsilon for log stability in aggregate model.
    :param eps_share_denominator: Epsilon in share normalisation denom.
    :param share_chunk_size: Chunk size for share forward (0 disables).
    :param sigma_damp: Damping factor for aggregate sampling sigma.
    :param logit_noise_std: Optional noise added to share logits during sampling.
    """
    context_len: int
    steps_agg: int
    steps_share: int
    batch_size_agg: int
    batch_size_share: int
    lr_agg: float
    lr_share: float
    prefer_gpu: bool
    verbose: bool
    eps_agg: float
    eps_share_denominator: float
    share_chunk_size: int
    sigma_damp: float
    logit_noise_std: Optional[float]


class HierarchicalZipArtifact:
    """
    Orchestrates training, prediction, and durable ZIP save/load.

    Stores:
    - aggregate_params.msgpack (Flax params bytes)
    - share_params.msgpack (Flax params bytes)
    - spec.json
    - meta.json (model dims)
    - losses_agg.json
    - losses_share.json
    """

    def __init__(self, spec: HierarchicalZipSpec):
        """
        :param spec: Training/generation spec.
        """
        self.spec = spec

        self.agg_model: Optional[AggregateARModel] = None
        self.share_model: Optional[ShareSoftmaxModel] = None

        self.agg_params: Any = None
        self.share_params: Any = None

        self.agg_losses: List[float] = []
        self.share_losses: List[float] = []

        self.agg_meta: Dict[str, Any] = {}
        self.share_meta: Dict[str, Any] = {}

    def train(self, timestamps: np.ndarray, P: np.ndarray, region_id: np.ndarray, temp: np.ndarray) -> None:
        """
        Train both aggregate and share models.

        :param timestamps: Unix timestamps ``(T,)``.
        :param P: Device power matrix ``(T,N)``.
        :param region_id: Region index per device ``(N,)``.
        :param temp: Temperature matrix ``(T,R)``.
        :returns: None.
        """
        P_arr = np.nan_to_num(np.asarray(P, dtype=np.float32), nan=0.0)
        P_agg = np.sum(P_arr, axis=1).astype(np.float32)

        agg_model, agg_params, agg_losses, agg_meta = train_aggregate_model(
            timestamps=np.asarray(timestamps, dtype=np.int64),
            P_agg=P_agg,
            temp=np.asarray(temp, dtype=np.float32),
            context_len=int(self.spec.context_len),
            steps=int(self.spec.steps_agg),
            batch_size=int(self.spec.batch_size_agg),
            lr=float(self.spec.lr_agg),
            prefer_gpu=bool(self.spec.prefer_gpu),
            verbose=bool(self.spec.verbose),
            eps_agg=float(self.spec.eps_agg),
        )

        share_model, share_params, share_losses, share_meta = train_share_softmax_model(
            timestamps=np.asarray(timestamps, dtype=np.int64),
            P=P_arr,
            region_id=np.asarray(region_id, dtype=np.int64),
            temp=np.asarray(temp, dtype=np.float32),
            steps=int(self.spec.steps_share),
            batch_size=int(self.spec.batch_size_share),
            lr=float(self.spec.lr_share),
            prefer_gpu=bool(self.spec.prefer_gpu),
            verbose=bool(self.spec.verbose),
            eps_share_denominator=float(self.spec.eps_share_denominator),
            eps_agg=float(self.spec.eps_agg),
            chunk_size=int(self.spec.share_chunk_size),
        )

        self.agg_model = agg_model
        self.share_model = share_model
        self.agg_params = agg_params
        self.share_params = share_params
        self.agg_losses = list(agg_losses)
        self.share_losses = list(share_losses)
        self.agg_meta = dict(agg_meta)
        self.share_meta = dict(share_meta)

    def predict(self, timestamps: np.ndarray, temp: np.ndarray, region_id: np.ndarray, y_agg_init: np.ndarray, seed: int) -> np.ndarray:
        """
        Generate synthetic device powers ``(T,N)``.

        :param timestamps: Unix timestamps ``(T,)``.
        :param temp: Temperature matrix ``(T,R)``.
        :param region_id: Region index per device ``(N,)``.
        :param y_agg_init: Initial context for aggregate log-series ``(L,)``.
        :param seed: RNG seed.
        :returns: Synthetic device power matrix ``(T,N)``.
        """
        if self.agg_model is None or self.share_model is None:
            raise RuntimeError("Models are not loaded or trained.")
        if self.agg_params is None or self.share_params is None:
            raise RuntimeError("Params are not loaded or trained.")

        y_syn, sigma_eff = sample_aggregate(
            model=self.agg_model,
            params=self.agg_params,
            timestamps=np.asarray(timestamps, dtype=np.int64),
            temp=np.asarray(temp, dtype=np.float32),
            y_agg_init=np.asarray(y_agg_init, dtype=np.float32),
            seed=int(seed),
            sigma_damp=float(self.spec.sigma_damp),
            prefer_gpu=bool(self.spec.prefer_gpu),
            verbose=bool(self.spec.verbose),
        )

        P_agg_syn = lognormal_mean_correction(y_syn, sigma_eff)

        shares = sample_shares_softmax(
            model=self.share_model,
            params=self.share_params,
            timestamps=np.asarray(timestamps, dtype=np.int64),
            temp=np.asarray(temp, dtype=np.float32),
            y_agg=np.asarray(y_syn, dtype=np.float32),
            region_id=np.asarray(region_id, dtype=np.int64),
            seed=int(seed) + 1,
            logit_noise_std=float(self.spec.logit_noise_std) if self.spec.logit_noise_std is not None else 0.0,
            chunk_size=int(self.spec.share_chunk_size),
            prefer_gpu=bool(self.spec.prefer_gpu),
            verbose=bool(self.spec.verbose),
        )

        return reconstruct_power_from_shares(P_agg_syn, shares)

    def save(self, zip_path: str) -> None:
        """
        Save a ZIP artifact.

        :param zip_path: Destination ZIP path.
        :returns: None.
        """
        if self.agg_model is None or self.share_model is None:
            raise RuntimeError("Models are not loaded or trained.")
        if self.agg_params is None or self.share_params is None:
            raise RuntimeError("Params are not loaded or trained.")

        os.makedirs(os.path.dirname(os.path.abspath(zip_path)), exist_ok=True)

        spec_json = json.dumps(asdict(self.spec), indent=2)
        meta_json = json.dumps({"agg_meta": self.agg_meta, "share_meta": self.share_meta}, indent=2)
        losses_agg_json = json.dumps(self.agg_losses, indent=2)
        losses_share_json = json.dumps(self.share_losses, indent=2)

        agg_bytes = to_bytes(self.agg_params)
        share_bytes = to_bytes(self.share_params)

        with zipfile.ZipFile(zip_path, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("aggregate_params.msgpack", agg_bytes)
            zf.writestr("share_params.msgpack", share_bytes)
            zf.writestr("spec.json", spec_json)
            zf.writestr("meta.json", meta_json)
            zf.writestr("losses_agg.json", losses_agg_json)
            zf.writestr("losses_share.json", losses_share_json)

    @classmethod
    def load(cls, zip_path: str) -> "HierarchicalZipArtifact":
        """
        Load from a ZIP artifact produced by :meth:`save`.

        Reconstruction is explicit:
        - AggregateARModel(cal_dim, hidden, input_proj)
        - ShareSoftmaxModel(n_devices, n_regions, cal_dim, dev_emb_dim, reg_emb_dim, hidden)

        :param zip_path: ZIP path.
        :returns: Loaded instance.
        """
        with zipfile.ZipFile(zip_path, mode="r") as zf:
            spec = HierarchicalZipSpec(**json.loads(zf.read("spec.json")))
            meta = json.loads(zf.read("meta.json"))
            agg_meta = dict(meta["agg_meta"])
            share_meta = dict(meta["share_meta"])

            agg_bytes = zf.read("aggregate_params.msgpack")
            share_bytes = zf.read("share_params.msgpack")

            agg_losses = list(json.loads(zf.read("losses_agg.json")))
            share_losses = list(json.loads(zf.read("losses_share.json")))

        obj = cls(spec=spec)
        obj.agg_meta = agg_meta
        obj.share_meta = share_meta
        obj.agg_losses = agg_losses
        obj.share_losses = share_losses

        obj.agg_model = AggregateARModel(
            cal_dim=int(obj.agg_meta["cal_dim"]),
            hidden=int(obj.agg_meta["hidden"]),
            input_proj=int(obj.agg_meta["input_proj"]),
        )

        obj.share_model = ShareSoftmaxModel(
            n_devices=int(obj.share_meta["n_devices"]),
            n_regions=int(obj.share_meta["n_regions"]),
            cal_dim=int(obj.share_meta["cal_dim"]),
            dev_emb_dim=int(obj.share_meta["dev_emb_dim"]),
            reg_emb_dim=int(obj.share_meta["reg_emb_dim"]),
            hidden=int(obj.share_meta["hidden"]),
        )

        # Build param templates via init, then deserialize into them
        key0 = jax.random.PRNGKey(0)
        L = int(obj.spec.context_len)
        F = int(obj.agg_meta["cal_dim"])
        N = int(obj.share_meta["n_devices"])

        dummy_y_ctx = jnp.zeros((1, L), dtype=jnp.float32)
        dummy_temp_hist = jnp.zeros((1, L, 1), dtype=jnp.float32)
        dummy_cal_t = jnp.zeros((1, F), dtype=jnp.float32)
        dummy_temp_t = jnp.zeros((1, 1), dtype=jnp.float32)

        vars_agg = obj.agg_model.init(key0, dummy_y_ctx, dummy_temp_hist, dummy_cal_t, dummy_temp_t)
        template_agg = vars_agg["params"]
        obj.agg_params = from_bytes(template_agg, agg_bytes)

        key1 = jax.random.PRNGKey(1)
        dummy_cal = jnp.zeros((1, int(obj.share_meta["cal_dim"])), dtype=jnp.float32)
        dummy_temp = jnp.zeros((1, N), dtype=jnp.float32)
        dummy_y = jnp.zeros((1, 1), dtype=jnp.float32)
        dummy_region = jnp.zeros((N,), dtype=jnp.int32)

        vars_share = obj.share_model.init(key1, dummy_cal, dummy_temp, dummy_y, dummy_region, 0)
        template_share = vars_share["params"]
        obj.share_params = from_bytes(template_share, share_bytes)

        return obj


# ----------------------------------------------------------------------------------------------------------------------
# 11) PLOTTING
# ----------------------------------------------------------------------------------------------------------------------
def plot_losses(losses: List[float], title: str) -> None:
    """
    Plot training loss curve.

    :param losses: Loss list.
    :param title: Plot title.
    :returns: None.
    """
    if len(losses) == 0:
        print(f"[plot] No losses to plot for: {title} (likely loaded artifact).")
        return
    plt.figure()
    plt.plot(losses)
    plt.title(title)
    plt.xlabel("Step")
    plt.ylabel("Loss")
    plt.grid(True)
    plt.tight_layout()


def plot_aggregate_real_vs_syn(P_agg_real: np.ndarray, P_agg_syn: np.ndarray, max_points: int, title: str) -> None:
    """
    Plot aggregate series real vs synthetic.

    :param P_agg_real: Real aggregate ``(T,)``.
    :param P_agg_syn: Synthetic aggregate ``(T,)``.
    :param max_points: Downsample cap.
    :param title: Plot title.
    :returns: None.
    """
    T = int(P_agg_real.shape[0])
    idx = np.arange(T)
    if T > int(max_points):
        idx = np.linspace(0, T - 1, int(max_points)).astype(int)

    plt.figure()
    plt.plot(idx, P_agg_real[idx], label="real aggregate")
    plt.plot(idx, P_agg_syn[idx], label="synthetic aggregate", linestyle="--")
    plt.title(title)
    plt.xlabel("time index")
    plt.ylabel("Aggregate power")
    plt.grid(True)
    plt.legend()
    plt.tight_layout()


def plot_share_sum_sanity(P_syn: np.ndarray, P_agg_syn: np.ndarray, max_points: int, title: str) -> None:
    """
    Plot sanity check: sum_i P_syn(t,i) / P_agg_syn(t). Should be ~1.

    :param P_syn: Device powers ``(T,N)``.
    :param P_agg_syn: Aggregate powers ``(T,)``.
    :param max_points: Downsample cap.
    :param title: Plot title.
    :returns: None.
    """
    P = np.asarray(P_syn, dtype=np.float32)
    A = np.asarray(P_agg_syn, dtype=np.float32)
    ratio = P.sum(axis=1) / (A + 1e-12)

    T = int(ratio.shape[0])
    idx = np.arange(T)
    if T > int(max_points):
        idx = np.linspace(0, T - 1, int(max_points)).astype(int)

    plt.figure()
    plt.plot(idx, ratio[idx])
    plt.axhline(1.0, linestyle="--")
    plt.title(title)
    plt.xlabel("time index")
    plt.ylabel("sum(P_syn)/P_agg_syn")
    plt.grid(True)
    plt.tight_layout()


def plot_devices_real_vs_syn(P_real: np.ndarray, P_syn: np.ndarray, devices: List[int], max_points: int, title: str) -> None:
    """
    Plot selected devices real vs synthetic.

    :param P_real: Real device powers ``(T,N)``.
    :param P_syn: Synthetic device powers ``(T,N)``.
    :param devices: Device indices.
    :param max_points: Downsample cap.
    :param title: Plot title.
    :returns: None.
    """
    T = int(P_real.shape[0])
    idx = np.arange(T)
    if T > int(max_points):
        idx = np.linspace(0, T - 1, int(max_points)).astype(int)

    plt.figure()
    for d in devices:
        plt.plot(idx, P_real[idx, d], label=f"real d{d}", alpha=0.8)
        plt.plot(idx, P_syn[idx, d], label=f"syn d{d}", alpha=0.8, linestyle="--")
    plt.title(title)
    plt.xlabel("time index")
    plt.ylabel("Power")
    plt.grid(True)
    plt.legend(ncol=2, fontsize=8)
    plt.tight_layout()


# ----------------------------------------------------------------------------------------------------------------------
# 12) DEMO (standalone synthetic data)
# ----------------------------------------------------------------------------------------------------------------------
def _make_synthetic_demo_data(T: int, N: int, R: int, seed: int) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Create a small synthetic dataset so the demo can run standalone.

    :param T: Number of timesteps.
    :param N: Number of devices.
    :param R: Number of regions.
    :param seed: RNG seed.
    :returns: (timestamps, P, region_id, temp).
    """
    rng = np.random.default_rng(int(seed))
    timestamps = (np.arange(T, dtype=np.int64) * 3600) + np.int64(1700000000)

    region_id = rng.integers(low=0, high=R, size=N, dtype=np.int64)
    base_temp = 10.0 + 10.0 * np.sin(2.0 * np.pi * np.arange(T) / (24.0 * 30.0))
    temp = np.stack([base_temp + rng.normal(0.0, 1.5, size=T) for _ in range(R)], axis=1).astype(np.float32)

    hour = (timestamps // 3600) % 24
    dow = (timestamps // (3600 * 24)) % 7
    daily = 1.0 + 0.3 * np.sin(2.0 * np.pi * hour / 24.0 - 0.5)
    weekly = 1.0 - 0.12 * (dow >= 5).astype(np.float32)
    temp_effect = 1.0 + 0.02 * np.maximum(0.0, 18.0 - temp[:, 0]) + 0.01 * np.maximum(0.0, temp[:, 0] - 24.0)

    P_agg = (1000.0 * daily * weekly * temp_effect + rng.normal(0.0, 20.0, size=T)).astype(np.float32)
    P_agg = np.maximum(P_agg, 1.0)

    w_dev = rng.lognormal(mean=0.0, sigma=0.5, size=N).astype(np.float32)
    w_reg = rng.lognormal(mean=0.0, sigma=0.3, size=R).astype(np.float32)
    w = w_dev * w_reg[region_id]
    w = w / np.sum(w)

    mod = (1.0 + 0.05 * np.sin(2.0 * np.pi * hour / 24.0))[..., None].astype(np.float32)
    P = (P_agg[:, None] * w[None, :] * mod).astype(np.float32)

    mask = rng.random(P.shape) < 0.0005
    P[mask] = np.nan

    return timestamps, P, region_id, temp


def demo() -> None:
    """
    Demo: Train / Save / Load / Predict with HierarchicalZipArtifact.

    :returns: None.
    """
    timestamps, P, region_id, temp = _make_synthetic_demo_data(T=24 * 30, N=400, R=6, seed=123)
    print(f"[demo] T={timestamps.shape[0]} N={P.shape[1]} R={temp.shape[1]}")

    artifact_path = "./artifacts/hierarchical_country_load_jax.zip"
    os.makedirs(os.path.dirname(artifact_path), exist_ok=True)

    spec = HierarchicalZipSpec(
        context_len=48,
        steps_agg=2000,
        steps_share=2000,
        batch_size_agg=64,
        batch_size_share=16,
        lr_agg=3e-4,
        lr_share=3e-4,
        prefer_gpu=True,
        verbose=True,
        eps_agg=1e-6,
        eps_share_denominator=1e-6,
        share_chunk_size=0,
        sigma_damp=0.25,
        logit_noise_std=0.05,
    )

    if os.path.exists(artifact_path):
        print(f"[demo] Loading: {artifact_path}")
        art = HierarchicalZipArtifact.load(artifact_path)
    else:
        print(f"[demo] Training new artifact: {artifact_path}")
        art = HierarchicalZipArtifact(spec=spec)
        art.train(timestamps=timestamps, P=P, region_id=region_id, temp=temp)
        art.save(artifact_path)
        print(f"[demo] Saved: {artifact_path}")

    P_clean = np.nan_to_num(P.astype(np.float32), nan=0.0)
    P_agg_real = np.sum(P_clean, axis=1)
    y_agg_init = np.log(P_agg_real[:int(spec.context_len)] + float(spec.eps_agg)).astype(np.float32)

    P_syn = art.predict(
        timestamps=timestamps,
        temp=temp.astype(np.float32),
        region_id=region_id.astype(np.int64),
        y_agg_init=y_agg_init,
        seed=1234,
    )

    P_agg_syn = np.sum(P_syn, axis=1)

    plt.figure()
    plt.plot(P_agg_real, label="Real aggregate")
    plt.plot(P_agg_syn, label="Synthetic aggregate")
    plt.legend()
    plt.title("Aggregate: Real vs Synthetic (JAX/Flax)")
    plt.tight_layout()

    plt.figure()
    dev_idx = 0
    plt.plot(P_clean[:, dev_idx], label=f"Real dev {dev_idx}")
    plt.plot(P_syn[:, dev_idx], label=f"Synth dev {dev_idx}")
    plt.legend()
    plt.title("Example device trajectory (JAX/Flax)")
    plt.tight_layout()

    plt.show()


if __name__ == "__main__":
    demo()