"""
demo_newton_diagnostics.py
==========================
Standalone demo to validate the Newton diagnostics decorator.
"""

import logging
import numpy as np
import scipy.sparse as sp
import pandas as pd

from typing import Any

from VeraGridEngine.Utils.Symbolic.diagnostic import (
    with_newton_diagnostics,
    NewtonDiagnosticsConfig,
    NewtonSolveContext,
    dense_lstsq_fallback,
    sparse_lsqr_fallback,
    NewtonTraceCollector
)

collector = NewtonTraceCollector()

# ---------------------------------------------------------------------
# Logging configuration
# ---------------------------------------------------------------------
logging.basicConfig(
    level=logging.WARNING,
    format="%(levelname)s:%(name)s:%(message)s",
)

logger = logging.getLogger("NewtonDiagnosticsDemo")

# ---------------------------------------------------------------------
# Fake Newton context
# ---------------------------------------------------------------------
def make_ctx(iteration: int) -> NewtonSolveContext:
    return NewtonSolveContext(
        t=0.0,
        step_idx=0,
        newton_iter=iteration,
        phase="demo",
        method="diagnostics_test",
    )

# ---------------------------------------------------------------------
# Test 1: Dense singular Jacobian (forces LS fallback)
# ---------------------------------------------------------------------
def dense_singular() -> None:
    logger.warning("=== TEST: Dense singular Jacobian ===")

    A: np.ndarray = np.array(list([
        list([1.0, 2.0]),
        list([0.0, 0.0]),  # Rank-deficient row
    ]), dtype=np.float64)
    b: np.ndarray = np.array(list([1.0, 0.0]), dtype=np.float64)

    cfg: NewtonDiagnosticsConfig = NewtonDiagnosticsConfig(
        compute_dense_cond=True,
        enable_fallback=True,
    )

    dense_solve: Any = with_newton_diagnostics(
        np.linalg.solve,
        fallback_solve=dense_lstsq_fallback,
        config=cfg,
        solver_name="dense",
        collector=collector
    )

    dx: np.ndarray = dense_solve(A, b, make_ctx(0))
    logger.warning("Result dx = %s", dx)

# ---------------------------------------------------------------------
# Test 2: Dense ill-conditioned Jacobian (large cond number)
# ---------------------------------------------------------------------
def dense_ill_conditioned() -> None:
    logger.warning("=== TEST: Dense ill-conditioned Jacobian ===")

    eps: float = 1e-14
    A: np.ndarray = np.array(list([
        list([1.0, 1.0]),
        list([1.0, 1.0 + eps]),
    ]), dtype=np.float64)
    b: np.ndarray = np.array(list([2.0, 2.0]), dtype=np.float64)

    cfg: NewtonDiagnosticsConfig = NewtonDiagnosticsConfig(
        compute_dense_cond=True,
        dense_cond_warn=1e10,
        enable_fallback=False,
    )

    dense_solve: Any = with_newton_diagnostics(
        np.linalg.solve,
        config=cfg,
        solver_name="dense",
        collector=collector
    )

    dx: np.ndarray = dense_solve(A, b, make_ctx(1))
    logger.warning("Result dx = %s", dx)

# ---------------------------------------------------------------------
# Test 3: Exploding Newton step (large ||dx||)
# ---------------------------------------------------------------------
def exploding_step() -> None:
    logger.warning("=== TEST: Exploding Newton step ===")

    A: np.ndarray = np.eye(2, dtype=np.float64)
    b: np.ndarray = np.array(list([1e8, -1e8]), dtype=np.float64)

    cfg: NewtonDiagnosticsConfig = NewtonDiagnosticsConfig(
        step_norm_explode=1e6,
        enable_fallback=False,
    )

    dense_solve: Any = with_newton_diagnostics(
        np.linalg.solve,
        config=cfg,
        solver_name="dense",
        collector=collector
    )

    dx: np.ndarray = dense_solve(A, b, make_ctx(2))
    logger.warning("Result dx = %s", dx)

# ---------------------------------------------------------------------
# Test 4: Sparse singular Jacobian (forces LSQR fallback)
# ---------------------------------------------------------------------
def sparse_singular() -> None:
    logger.warning("=== TEST: Sparse singular Jacobian ===")

    A = sp.csr_matrix(list([
        list([1.0, 2.0]),
        list([0.0, 0.0]),
    ]), dtype=np.float64)
    b: np.ndarray = np.array(list([1.0, 0.0]), dtype=np.float64)

    cfg: NewtonDiagnosticsConfig = NewtonDiagnosticsConfig(
        compute_dense_cond=False,
        enable_fallback=True,
    )

    sparse_solve: Any = with_newton_diagnostics(
        sp.linalg.spsolve,
        fallback_solve=sparse_lsqr_fallback,
        config=cfg,
        solver_name="sparse",
        collector=collector
    )

    dx: np.ndarray = sparse_solve(A, b, make_ctx(3))
    logger.warning("Result dx = %s", dx)

# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------
if __name__ == "__main__":
    dense_singular()
    dense_ill_conditioned()
    exploding_step()
    sparse_singular()

    # Convert collected diagnostics to DataFrame
    df: pd.DataFrame = collector.to_dataframe()

    # Save full diagnostics
    df.to_csv("newton_diagnostics_demo.csv", index=False)
    logger.warning("Diagnostics written to newton_diagnostics_demo.csv")

    # 1) Worst conditioning / step per solver
    df_max: pd.DataFrame = df.groupby("method")[list(["cond_J", "dx_norm_inf"])].max()
    logger.warning("Max diagnostics per solver:\n%s", df_max)

    # 2) Rows where fallback was used
    df_fallback: pd.DataFrame = df[df["used_fallback"] == True]
    logger.warning("Fallback cases:\n%s", df_fallback)