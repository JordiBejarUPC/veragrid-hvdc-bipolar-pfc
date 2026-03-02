"""
demo_newton_diagnostics.py
==========================

Standalone demo to validate the Newton diagnostics decorator.

This script is intentionally minimal and does NOT depend on:
    - block_solver
    - any existing VeraGrid demo
    - pytest

It directly exercises the diagnostics layer by solving
artificial linear systems that are:
    - singular
    - ill-conditioned
    - numerically explosive

Expected output:
    - WARNING messages from NewtonDiagnostics

Run with:
    python demo_newton_diagnostics.py
"""

import logging
import numpy as np
import scipy.sparse as sp

from VeraGridEngine.Utils.Symbolic.diagnostic import (
    with_newton_diagnostics,
    NewtonDiagnosticsConfig,
    NewtonSolveContext,
    dense_lstsq_fallback,
    sparse_lsqr_fallback,
)

from VeraGridEngine.Utils.Symbolic.diagnostic import NewtonTraceCollector

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
# Fake Newton context (as block_solver would provide)
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

def dense_singular():
    logger.warning("=== TEST: Dense singular Jacobian ===")

    A = np.array([
        [1.0, 2.0],
        [0.0, 0.0],  # Rank-deficient row
    ])
    b = np.array([1.0, 0.0])

    cfg = NewtonDiagnosticsConfig(
        compute_dense_cond=True,
        enable_fallback=True,
    )

    dense_solve = with_newton_diagnostics(
        np.linalg.solve,
        fallback_solve=dense_lstsq_fallback,
        config=cfg,
        solver_name="dense",
        collector=collector
    )

    dx = dense_solve(A, b, make_ctx(0))
    logger.warning("Result dx = %s", dx)


# ---------------------------------------------------------------------
# Test 2: Dense ill-conditioned Jacobian (large cond number)
# ---------------------------------------------------------------------

def dense_ill_conditioned():
    logger.warning("=== TEST: Dense ill-conditioned Jacobian ===")

    eps = 1e-14
    A = np.array([
        [1.0, 1.0],
        [1.0, 1.0 + eps],
    ])
    b = np.array([2.0, 2.0])

    cfg = NewtonDiagnosticsConfig(
        compute_dense_cond=True,
        dense_cond_warn=1e10,
        enable_fallback=False,
    )

    dense_solve = with_newton_diagnostics(
        np.linalg.solve,
        config=cfg,
        solver_name="dense",
        collector=collector
    )

    dx = dense_solve(A, b, make_ctx(1))
    logger.warning("Result dx = %s", dx)


# ---------------------------------------------------------------------
# Test 3: Exploding Newton step (large ||dx||)
# ---------------------------------------------------------------------

def exploding_step():
    logger.warning("=== TEST: Exploding Newton step ===")

    A = np.eye(2)
    b = np.array([1e8, -1e8])  # Huge RHS → huge dx

    cfg = NewtonDiagnosticsConfig(
        step_norm_explode=1e6,
        enable_fallback=False,
    )

    dense_solve = with_newton_diagnostics(
        np.linalg.solve,
        config=cfg,
        solver_name="dense",
        collector=collector
    )

    dx = dense_solve(A, b, make_ctx(2))
    logger.warning("Result dx = %s", dx)


# ---------------------------------------------------------------------
# Test 4: Sparse singular Jacobian (forces LSQR fallback)
# ---------------------------------------------------------------------

def sparse_singular():
    logger.warning("=== TEST: Sparse singular Jacobian ===")

    A = sp.csr_matrix([
        [1.0, 2.0],
        [0.0, 0.0],
    ])
    b = np.array([1.0, 0.0])

    cfg = NewtonDiagnosticsConfig(
        compute_dense_cond=False,
        enable_fallback=True,
    )

    sparse_solve = with_newton_diagnostics(
        sp.linalg.spsolve,
        fallback_solve=sparse_lsqr_fallback,
        config=cfg,
        solver_name="sparse",
        collector=collector
    )

    dx = sparse_solve(A, b, make_ctx(3))
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
    df = collector.to_dataframe()  # o pd.DataFrame(collector.records)

    # Save full diagnostics
    df.to_csv("newton_diagnostics_demo.csv", index=False)
    logger.warning("Diagnostics written to newton_diagnostics_demo.csv")

    # -----------------------------------------------------------------
    # Analysis examples (optional, demo-only)
    # -----------------------------------------------------------------

    # 1) Worst conditioning / step per solver
    df_max = df.groupby("method")[["cond_J", "dx_norm_inf"]].max()
    logger.warning("Max diagnostics per solver:\n%s", df_max)

    # 2) Rows where fallback was used
    df_fallback = df[df["used_fallback"] == True]
    logger.warning("Fallback cases:\n%s", df_fallback)
