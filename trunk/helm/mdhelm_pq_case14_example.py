"""
VeraGrid-integrated multidimensional HELM example on MATPOWER case14.

This file is intentionally written as an external prototype, not as a direct patch
inside VeraGridEngine. It uses VeraGrid to:

1. load the MATPOWER file,
2. compile the NumericalCircuit,
3. obtain Ybus, Sbus, bus types and slack/non-slack indices,
4. post-process the MDHEM voltage map into branch flows and mismatch metrics.

Scope of this first integrated prototype
----------------------------------------
- Fixed-injection MDHEM / PQ formulation.
- All non-slack buses are treated as PQ buses in the MDHEM map.
- PV voltage control and Q-limit switching are not enforced here. Those require
  the extended MDHEM matrix with Q and W/X unknowns for PV buses, as in the paper.

This is still useful for the target use case: building an offline polynomial map
V(s_1, ..., s_D) over injection directions, then evaluating many injection
scenarios without running an iterative power flow for every point.

When this module is executed directly, it loads the sibling ``case14.matpower``
file and runs the default ``regions`` setup.
"""

from __future__ import annotations

import math
import shutil
import tempfile
import time
from dataclasses import dataclass
from functools import lru_cache
from itertools import product
from pathlib import Path
from types import SimpleNamespace
from typing import Dict, Iterable, List, Mapping, Sequence, Tuple

import numpy as np
from scipy.sparse import csc_matrix
from scipy.sparse.linalg import factorized


MultiIndex = Tuple[int, ...]


# -------------------------------------------------------------------------------------------------
# Multidimensional coefficient utilities
# -------------------------------------------------------------------------------------------------

def compositions(total: int, dims: int) -> Iterable[MultiIndex]:
    """Yield all D-dimensional non-negative multi-indices with sum == total."""
    if dims <= 0:
        raise ValueError("dims must be positive")
    if dims == 1:
        yield (total,)
        return
    for first in range(total + 1):
        for rest in compositions(total - first, dims - 1):
            yield (first, *rest)


def multi_indices_by_order(dims: int, max_order: int) -> List[List[MultiIndex]]:
    """Return multi-indices grouped by total order."""
    if max_order < 0:
        raise ValueError("max_order must be non-negative")
    return [list(compositions(order, dims)) for order in range(max_order + 1)]


def alpha_minus_e(alpha: MultiIndex, d: int) -> MultiIndex:
    """Return alpha - e_d. Caller must ensure alpha[d] > 0."""
    out = list(alpha)
    out[d] -= 1
    return tuple(out)


def alpha_minus_beta(alpha: MultiIndex, beta: MultiIndex) -> MultiIndex:
    return tuple(a - b for a, b in zip(alpha, beta))


@lru_cache(maxsize=None)
def sub_multi_indices(alpha: MultiIndex) -> Tuple[MultiIndex, ...]:
    """All beta such that 0 <= beta <= alpha, excluding beta = 0."""
    zero = (0,) * len(alpha)
    return tuple(beta for beta in product(*[range(a + 1) for a in alpha]) if beta != zero)


def coefficient_count(dims: int, max_order: int) -> int:
    """Number of multivariate coefficients up to total order M: C(M + D, D)."""
    return math.comb(max_order + dims, dims)


# -------------------------------------------------------------------------------------------------
# MDHEM fixed-injection / PQ map
# -------------------------------------------------------------------------------------------------

@dataclass
class MDHEMPQMap:
    """Truncated multidimensional HELM map for fixed-injection/PQ power flow."""

    Ybus: csc_matrix
    sl: np.ndarray
    no_slack: np.ndarray
    Vslack: np.ndarray
    S_basis_full: np.ndarray          # shape: (D, nbus), p.u. complex injections
    max_order: int
    alphas: List[MultiIndex]
    alpha_to_idx: Dict[MultiIndex, int]
    U: np.ndarray                     # shape: (n_terms, n_no_slack)
    X: np.ndarray                     # shape: (n_terms, n_no_slack)
    bus_names: np.ndarray | None = None
    dimension_names: List[str] | None = None

    @property
    def dims(self) -> int:
        return int(self.S_basis_full.shape[0])

    @property
    def nbus(self) -> int:
        return int(self.Ybus.shape[0])

    def evaluate(self, s: Sequence[float | complex]) -> np.ndarray:
        """Evaluate V(s) from the truncated multivariate power series."""
        s_arr = np.asarray(s, dtype=np.complex128)
        if s_arr.shape != (self.dims,):
            raise ValueError(f"Expected s with shape ({self.dims},), got {s_arr.shape}")

        weights = np.empty(len(self.alphas), dtype=np.complex128)
        for k, alpha in enumerate(self.alphas):
            w = 1.0 + 0.0j
            for d, power in enumerate(alpha):
                if power:
                    w *= s_arr[d] ** power
            weights[k] = w

        V = np.empty(self.nbus, dtype=np.complex128)
        V[self.sl] = self.Vslack
        V[self.no_slack] = weights @ self.U
        return V

    def injection(self, s: Sequence[float | complex]) -> np.ndarray:
        """Return the p.u. complex bus injection S(s) represented by this map."""
        s_arr = np.asarray(s, dtype=np.complex128)
        if s_arr.shape != (self.dims,):
            raise ValueError(f"Expected s with shape ({self.dims},), got {s_arr.shape}")
        return s_arr @ self.S_basis_full


@dataclass
class MDHEMRunResult:
    """Light result object for the evaluated MDHEM map using VeraGrid post-processing."""

    s: np.ndarray
    voltage: np.ndarray
    Sbus: np.ndarray
    Scalc: np.ndarray
    norm_f: float
    converged_like: bool
    Sf: np.ndarray | None = None
    St: np.ndarray | None = None
    loading: np.ndarray | None = None
    losses: np.ndarray | None = None


def solve_mdhelm_pq(
    Ybus: csc_matrix,
    V0: np.ndarray,
    sl: Sequence[int],
    no_slack: Sequence[int],
    S_basis_full: np.ndarray,
    max_order: int = 6,
    bus_names: Sequence[str] | None = None,
    dimension_names: Sequence[str] | None = None,
) -> MDHEMPQMap:
    """
    Compute the fixed-injection/PQ multidimensional HELM map.

    Recurrence for alpha != 0:

        Yred U[alpha] = sum_d conj(S_basis[d]) X[alpha - e_d]

    and X is defined by:

        conj(V(s*)) X(s) = 1

    Parameters
    ----------
    Ybus:
        Full VeraGrid admittance matrix in p.u.
    V0:
        Full voltage vector. Only V0[sl] is used as fixed slack voltage.
    sl:
        Slack bus indices.
    no_slack:
        Non-slack buses solved by the map.
    S_basis_full:
        Shape (D, nbus). Each row is one independent p.u. injection direction.
        Sign convention must match VeraGrid: generation positive, load negative.
    max_order:
        Maximum total polynomial order.
    """
    Ybus = csc_matrix(Ybus)
    V0 = np.asarray(V0, dtype=np.complex128)
    sl = np.asarray(sl, dtype=int)
    no_slack = np.asarray(no_slack, dtype=int)
    S_basis_full = np.asarray(S_basis_full, dtype=np.complex128)

    if Ybus.shape[0] != Ybus.shape[1]:
        raise ValueError("Ybus must be square")
    nbus = Ybus.shape[0]
    if V0.shape != (nbus,):
        raise ValueError(f"V0 must have shape ({nbus},)")
    if S_basis_full.ndim != 2 or S_basis_full.shape[1] != nbus:
        raise ValueError(f"S_basis_full must have shape (D, {nbus})")
    if max_order < 0:
        raise ValueError("max_order must be non-negative")

    dims = S_basis_full.shape[0]
    grouped = multi_indices_by_order(dims=dims, max_order=max_order)
    alphas = [alpha for group in grouped for alpha in group]
    alpha_to_idx = {alpha: k for k, alpha in enumerate(alphas)}

    n_no_slack = len(no_slack)
    n_terms = len(alphas)
    U = np.zeros((n_terms, n_no_slack), dtype=np.complex128)
    X = np.zeros_like(U)

    Yred = Ybus[np.ix_(no_slack, no_slack)].tocsc()
    Ysl = Ybus[np.ix_(no_slack, sl)].tocsc()
    Vslack = V0[sl].copy()
    S_basis = S_basis_full[:, no_slack]

    solve = factorized(Yred)

    # Physical germ: zero non-slack injections, fixed slack voltage(s).
    alpha0 = (0,) * dims
    idx0 = alpha_to_idx[alpha0]
    rhs0 = -np.asarray(Ysl @ Vslack).ravel()
    U[idx0, :] = solve(rhs0)
    X[idx0, :] = 1.0 / np.conj(U[idx0, :])

    # Higher-order coefficients.
    for order in range(1, max_order + 1):
        for alpha in grouped[order]:
            idx = alpha_to_idx[alpha]
            rhs = np.zeros(n_no_slack, dtype=np.complex128)

            # Coefficient of S(s)^* X(s).
            for d in range(dims):
                if alpha[d] > 0:
                    prev_alpha = alpha_minus_e(alpha, d)
                    rhs += np.conj(S_basis[d, :]) * X[alpha_to_idx[prev_alpha], :]

            U[idx, :] = solve(rhs)

            # Coefficient of X = 1 / conj(V(s*)).
            accum = np.zeros(n_no_slack, dtype=np.complex128)
            for beta in sub_multi_indices(alpha):
                gamma = alpha_minus_beta(alpha, beta)
                accum += np.conj(U[alpha_to_idx[beta], :]) * X[alpha_to_idx[gamma], :]
            X[idx, :] = -accum / np.conj(U[idx0, :])

    return MDHEMPQMap(
        Ybus=Ybus,
        sl=sl,
        no_slack=no_slack,
        Vslack=Vslack,
        S_basis_full=S_basis_full,
        max_order=max_order,
        alphas=alphas,
        alpha_to_idx=alpha_to_idx,
        U=U,
        X=X,
        bus_names=np.asarray(bus_names, dtype=object) if bus_names is not None else None,
        dimension_names=list(dimension_names) if dimension_names is not None else None,
    )


# -------------------------------------------------------------------------------------------------
# Injection basis builders
# -------------------------------------------------------------------------------------------------

# A practical 4-region case14 grouping. It covers all non-slack buses 2..14.
# Edit this dictionary to use the exact partition you want in your studies.
DEFAULT_CASE14_GROUPS_1B: Mapping[str, Sequence[int]] = {
    "Area 1 - central/east": [4, 5, 7, 8, 9, 10],
    "Area 2 - north": [11, 12, 13, 14],
    "Area 3 - bus 6 area": [6],
    "Area 4 - west/slack-neighbour": [2, 3],
}


def build_group_basis_from_sbus(
    S0: np.ndarray,
    groups_1b: Mapping[str, Sequence[int]],
    slack: Sequence[int],
) -> Tuple[np.ndarray, List[str]]:
    """
    Build one injection direction per group from the base Sbus.

    Buses are passed as MATPOWER/VeraGrid display numbers, i.e. 1-based in this
    helper. Slack buses are ignored, because their injection is not prescribed.
    """
    S0 = np.asarray(S0, dtype=np.complex128)
    nbus = S0.size
    slack_set = set(int(i) for i in slack)

    basis = []
    names = []
    covered = set()

    for name, buses_1b in groups_1b.items():
        row = np.zeros(nbus, dtype=np.complex128)
        for bus_1b in buses_1b:
            bus = int(bus_1b) - 1
            if bus < 0 or bus >= nbus:
                raise ValueError(f"Bus {bus_1b} is outside 1..{nbus}")
            if bus in slack_set:
                continue
            row[bus] = S0[bus]
            covered.add(bus)
        if np.any(np.abs(row) > 0):
            basis.append(row)
            names.append(name)

    missing = sorted(set(range(nbus)) - slack_set - covered)
    if missing:
        # Add a final bucket so the basis reconstructs the full fixed-injection vector at s=1.
        row = np.zeros(nbus, dtype=np.complex128)
        for bus in missing:
            row[bus] = S0[bus]
        if np.any(np.abs(row) > 0):
            basis.append(row)
            names.append("Ungrouped non-slack injections")

    if not basis:
        raise ValueError("The group basis is empty; check groups and S0")

    return np.vstack(basis), names


def build_bus_basis_from_sbus(
    S0: np.ndarray,
    buses: Sequence[int],
    separate_pq: bool = False,
    bus_names: Sequence[str] | None = None,
) -> Tuple[np.ndarray, List[str]]:
    """
    Build an injection basis with one or two dimensions per bus.

    Parameters
    ----------
    S0:
        Full p.u. complex base injection vector.
    buses:
        0-based bus indices to map.
    separate_pq:
        False -> one fixed-power-factor direction per bus.
        True  -> separate P and Q dimensions per bus.
    bus_names:
        Optional names for readable dimension labels.
    """
    S0 = np.asarray(S0, dtype=np.complex128)
    buses = np.asarray(buses, dtype=int)
    nbus = S0.size

    basis = []
    names = []

    for bus in buses:
        if bus < 0 or bus >= nbus:
            raise ValueError(f"Bus index {bus} outside 0..{nbus - 1}")
        label = str(bus_names[bus]) if bus_names is not None else f"Bus {bus + 1}"
        if separate_pq:
            if abs(S0[bus].real) > 0:
                row = np.zeros(nbus, dtype=np.complex128)
                row[bus] = S0[bus].real
                basis.append(row)
                names.append(f"{label} P")
            if abs(S0[bus].imag) > 0:
                row = np.zeros(nbus, dtype=np.complex128)
                row[bus] = 1j * S0[bus].imag
                basis.append(row)
                names.append(f"{label} Q")
        else:
            if abs(S0[bus]) > 0:
                row = np.zeros(nbus, dtype=np.complex128)
                row[bus] = S0[bus]
                basis.append(row)
                names.append(label)

    if not basis:
        raise ValueError("The bus basis is empty; check S0 and selected buses")

    return np.vstack(basis), names


# -------------------------------------------------------------------------------------------------
# VeraGrid adapter
# -------------------------------------------------------------------------------------------------

def _open_veragrid_file(path: Path):
    """Load a file through VeraGridEngine, with a .matpower -> temporary .m fallback."""
    import VeraGridEngine as vg

    try:
        return vg.open_file(str(path))
    except Exception as original_error:
        if path.suffix.lower() in {".matpower", ".mpc"}:
            tmp_dir = Path(tempfile.mkdtemp(prefix="mdhelm_case14_"))
            tmp_path = tmp_dir / f"{path.stem}.m"
            shutil.copyfile(path, tmp_path)
            try:
                return vg.open_file(str(tmp_path))
            except Exception:
                raise original_error
        raise


def _compile_numerical_circuit(grid):
    """Compile using the public root API if available, otherwise the compiler module."""
    import VeraGridEngine as vg

    compile_fn = getattr(vg, "compile_numerical_circuit_at", None)
    if compile_fn is None:
        from VeraGridEngine.Compilers.circuit_to_data import compile_numerical_circuit_at
        compile_fn = compile_numerical_circuit_at

    # Different VeraGrid versions use either grid= or circuit=.
    try:
        return compile_fn(circuit=grid, t_idx=None)
    except TypeError:
        return compile_fn(grid, t_idx=None)


def _run_veragrid_nr(grid):
    """Run a standard VeraGrid NR power flow only to verify the MATPOWER import."""
    import VeraGridEngine as vg

    try:
        options = vg.PowerFlowOptions(
            solver_type=vg.SolverType.NR,
            retry_with_other_methods=False,
            control_q=False,
            control_taps_phase=False,
            control_taps_modules=False,
            apply_temperature_correction=False,
            use_stored_guess=False,
            tolerance=1e-9,
        )
    except TypeError:
        options = vg.PowerFlowOptions(vg.SolverType.NR, verbose=False)

    return vg.power_flow(grid=grid, options=options)


def _get_voltage_result(pf_results):
    """VeraGrid result field names changed over time; accept the common variants."""
    for name in ("voltage", "V"):
        value = getattr(pf_results, name, None)
        if value is not None:
            return np.asarray(value, dtype=np.complex128)
    return None


def _get_error_result(pf_results):
    for name in ("error", "norm_f"):
        value = getattr(pf_results, name, None)
        if value is not None:
            return float(value)
    return None


def evaluate_mdhelm_with_veragrid_postprocess(
    nc,
    md_map: MDHEMPQMap,
    s: Sequence[float | complex],
    tolerance: float = 1e-8,
) -> MDHEMRunResult:
    """
    Evaluate the MDHEM map and compute VeraGrid-style mismatch and branch flows.

    The mismatch is fixed-injection/PQ mismatch:
        fx = [dP(no_slack), dQ(no_slack)]
    because this prototype intentionally treats every non-slack bus as PQ.
    """
    from VeraGridEngine.Simulations.PowerFlow.NumericalMethods import common_functions as cf

    adm = nc.get_admittance_matrices()
    s_arr = np.asarray(s, dtype=np.complex128)
    V = md_map.evaluate(s_arr)
    Sbus = md_map.injection(s_arr)
    Scalc = cf.compute_power(adm.Ybus, V)
    fx = cf.compute_fx(Scalc=Scalc, Sbus=Sbus, idx_dP=md_map.no_slack, idx_dQ=md_map.no_slack)
    norm_f = float(cf.compute_fx_error(fx))

    Sf = St = loading = losses = None
    try:
        Sf, St, If, It, Vbranch, loading, losses, Sbus_pp = cf.power_flow_post_process_nonlinear(
            Sbus=Scalc,
            V=V,
            F=nc.passive_branch_data.F,
            T=nc.passive_branch_data.T,
            pv=np.array([], dtype=int),
            vd=md_map.sl,
            Ybus=adm.Ybus,
            Yf=adm.Yf,
            Yt=adm.Yt,
            Yshunt_bus=adm.Yshunt_bus,
            branch_rates=nc.passive_branch_data.rates,
            Sbase=nc.Sbase,
        )
    except Exception:
        # Keep the voltage map usable even if the local VeraGrid branch-flow API changed.
        pass

    return MDHEMRunResult(
        s=s_arr,
        voltage=V,
        Sbus=Sbus,
        Scalc=Scalc,
        norm_f=norm_f,
        converged_like=norm_f <= tolerance,
        Sf=Sf,
        St=St,
        loading=loading,
        losses=losses,
    )


def build_mdhelm_map_from_veragrid_case(
    matpower_path: str | Path,
    mode: str = "regions",
    order: int = 6,
    groups_1b: Mapping[str, Sequence[int]] | None = None,
) -> Tuple[object, object, MDHEMPQMap, SimpleNamespace]:
    """
    Load MATPOWER case through VeraGrid and build a fixed-injection MDHEM map.

    Returns
    -------
    grid:
        VeraGrid MultiCircuit.
    nc:
        VeraGrid NumericalCircuit.
    md_map:
        MDHEMPQMap object.
    info:
        Small namespace with S0, V0, indices, admittance object and optional NR result.
    """
    path = Path(matpower_path).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(path)

    grid = _open_veragrid_file(path)
    nc = _compile_numerical_circuit(grid)

    adm = nc.get_admittance_matrices()
    S0 = nc.get_power_injections_pu()
    V0 = np.asarray(nc.bus_data.Vbus, dtype=np.complex128)
    bus_names = np.asarray(nc.bus_data.names, dtype=object)

    indices = nc.get_simulation_indices(Sbus=S0, force_only_pq_pv_vd_types=True)
    slack = np.asarray(indices.vd, dtype=int)
    no_slack = np.asarray(indices.no_slack, dtype=int)

    if mode == "regions":
        basis, dimension_names = build_group_basis_from_sbus(
            S0=S0,
            groups_1b=groups_1b or DEFAULT_CASE14_GROUPS_1B,
            slack=slack,
        )
    elif mode == "buses":
        basis, dimension_names = build_bus_basis_from_sbus(
            S0=S0,
            buses=no_slack,
            separate_pq=False,
            bus_names=bus_names,
        )
    elif mode == "bus-pq":
        basis, dimension_names = build_bus_basis_from_sbus(
            S0=S0,
            buses=no_slack,
            separate_pq=True,
            bus_names=bus_names,
        )
    else:
        raise ValueError("mode must be one of: regions, buses, bus-pq")

    md_map = solve_mdhelm_pq(
        Ybus=adm.Ybus,
        V0=V0,
        sl=slack,
        no_slack=no_slack,
        S_basis_full=basis,
        max_order=order,
        bus_names=bus_names,
        dimension_names=dimension_names,
    )

    # Optional baseline: normal VeraGrid NR with PV buses. This is not the same mathematical problem
    # as the fixed-injection MDHEM map, but it verifies loading/import and gives a reference solution.
    try:
        nr_results = _run_veragrid_nr(grid)
    except Exception as e:
        nr_results = e

    info = SimpleNamespace(
        adm=adm,
        S0=S0,
        V0=V0,
        indices=indices,
        slack=slack,
        no_slack=no_slack,
        bus_names=bus_names,
        nr_results=nr_results,
    )
    return grid, nc, md_map, info


# -------------------------------------------------------------------------------------------------
# CLI demo
# -------------------------------------------------------------------------------------------------

def _format_complex(z: complex, nd: int = 6) -> str:
    return f"{z.real:.{nd}f}{z.imag:+.{nd}f}j"


def run_demo(matpower_path: str | Path, mode: str, order: int, tolerance: float = 1e-8) -> None:
    t0 = time.time()
    grid, nc, md_map, info = build_mdhelm_map_from_veragrid_case(
        matpower_path=matpower_path,
        mode=mode,
        order=order,
    )
    build_time = time.time() - t0

    s_base = np.ones(md_map.dims, dtype=np.complex128)
    res = evaluate_mdhelm_with_veragrid_postprocess(nc=nc, md_map=md_map, s=s_base, tolerance=tolerance)

    print("\nMDHEM fixed-injection map built from VeraGrid/MATPOWER case")
    print("----------------------------------------------------------")
    print(f"Grid name:       {getattr(grid, 'name', '<unknown>')}")
    print(f"Buses:           {nc.nbus}")
    print(f"Branches:        {nc.nbr}")
    print(f"Sbase:           {nc.Sbase} MVA")
    print(f"Mode:            {mode}")
    print(f"Dimensions D:    {md_map.dims}")
    print(f"Order M:         {order}")
    print(f"Coefficients:    {len(md_map.alphas)} = C(M + D, D)")
    print(f"Build time:      {build_time:.3f} s")
    print(f"Slack buses:     {[int(i) + 1 for i in md_map.sl]}")
    print(f"Non-slack buses: {[int(i) + 1 for i in md_map.no_slack]}")
    print("\nDimensions:")
    for k, name in enumerate(md_map.dimension_names or []):
        print(f"  s{k + 1}: {name}")

    print("\nEvaluation at s = ones(D)")
    print(f"Fixed-PQ MDHEM mismatch ||f||_inf: {res.norm_f:.4e}")
    print(f"Converged-like against tolerance {tolerance:g}: {res.converged_like}")

    nr = info.nr_results
    if not isinstance(nr, Exception):
        nr_v = _get_voltage_result(nr)
        nr_err = _get_error_result(nr)
        nr_conv = getattr(nr, "converged", None)
        print("\nStandard VeraGrid NR baseline, with original bus types")
        print(f"NR converged:    {nr_conv}")
        if nr_err is not None:
            print(f"NR error:        {nr_err:.4e}")
        if nr_v is not None:
            dv = np.max(np.abs(res.voltage - nr_v))
            print(f"max |V_MDHEM_fixed_PQ - V_NR_original_PV|: {dv:.4e}")
            print("Note: this voltage difference is expected because this prototype treats PV buses as fixed PQ injections.")
    else:
        print("\nStandard VeraGrid NR baseline failed:")
        print(f"  {nr}")

    print("\nVoltage samples")
    print("bus, name, |V|, angle_deg, V_complex")
    for i, V in enumerate(res.voltage):
        name = str(info.bus_names[i]) if info.bus_names is not None else f"Bus {i + 1}"
        print(f"{i + 1:>3}, {name:<20}, {abs(V):.6f}, {np.angle(V, deg=True): .6f}, {_format_complex(V)}")

    if res.Sf is not None:
        print("\nFirst 5 branch flows from VeraGrid post-process, MVA")
        for k in range(min(5, len(res.Sf))):
            print(f"branch {k:>2}: Sf = {res.Sf[k].real: .4f} MW {res.Sf[k].imag:+.4f} MVAr")


if __name__ == "__main__":
    # Load the bundled case directly to keep the example self-contained.
    case_path: Path = Path(__file__).resolve().with_name("case14.matpower")
    mode: str = "regions"
    order: int = 8
    tolerance: float = 1e-8

    print(f"Requested coefficient count: C({order} + D, D). D depends on mode={mode}.")
    run_demo(
        matpower_path=case_path,
        mode=mode,
        order=order,
        tolerance=tolerance,
    )
