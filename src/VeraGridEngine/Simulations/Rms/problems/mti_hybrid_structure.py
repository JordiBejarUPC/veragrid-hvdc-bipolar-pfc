from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import scipy.sparse as sp
from scipy.sparse.csgraph import connected_components


@dataclass
class MTISubProblemRow:
    var_idx: int
    eq_idx: int
    explicit: int
    subset: int
    subproblem: int


def build_incidence_from_jacobian(jac: sp.spmatrix, tol: float = 0.0) -> np.ndarray:
    """
    Build a boolean incidence matrix from a sparse Jacobian.

    The matrix format follows the MTI-toolbox convention at a high level:
    rows are equations and columns are variables, with 1 where dependency exists.
    """
    if jac is None:
        return np.zeros((0, 0), dtype=int)
    j = jac.tocoo()
    inc = np.zeros(j.shape, dtype=int)
    if j.nnz == 0:
        return inc
    mask = np.abs(j.data) > tol
    inc[j.row[mask], j.col[mask]] = 1
    return inc


def build_single_subproblem_order(n_eq: int, n_vars: int) -> list[MTISubProblemRow]:
    """
    Create a deterministic fallback solving-order where all equations/variables
    belong to one subset and one subproblem.

    This mirrors the toolbox row schema, while keeping the current VeraGrid
    implementation conservative until full incidence-based decomposition is
    ported.
    """
    n = min(n_eq, n_vars)
    rows: list[MTISubProblemRow] = []
    for i in range(n):
        rows.append(MTISubProblemRow(var_idx=i + 1, eq_idx=i + 1, explicit=0, subset=1, subproblem=1))
    return rows


def build_connected_subproblem_order(incidence: np.ndarray) -> list[MTISubProblemRow]:
    """
    Build a solving-order-like structure from equation-variable connectivity.

    We build a bipartite graph [eq | var] and use connected components as
    subsets/subproblems. Rows are paired (eq_i, var_i) within each subset.
    """
    if incidence.size == 0:
        return []

    n_eq, n_var = incidence.shape
    top = sp.csr_matrix(incidence)
    bot = top.T
    z_eq = sp.csr_matrix((n_eq, n_eq))
    z_var = sp.csr_matrix((n_var, n_var))
    bip = sp.bmat([[z_eq, top], [bot, z_var]], format="csr")
    _, labels = connected_components(bip, directed=False)

    eq_labels = labels[:n_eq]
    var_labels = labels[n_eq:]
    unique_components = sorted(set(eq_labels.tolist() + var_labels.tolist()))

    rows: list[MTISubProblemRow] = []
    sub_id = 1
    for comp in unique_components:
        eq_idx = np.where(eq_labels == comp)[0]
        var_idx = np.where(var_labels == comp)[0]

        # Keep full equation/variable membership for each connected component.
        # We encode memberships with lightweight rows so downstream grouping can
        # reconstruct full sets without dropping indices when |eq| != |var|.
        if len(eq_idx) == 0 or len(var_idx) == 0:
            sub_id += 1
            continue

        v0 = int(var_idx[0])
        e0 = int(eq_idx[0])

        for e in eq_idx:
            rows.append(
                MTISubProblemRow(
                    var_idx=v0 + 1,
                    eq_idx=int(e) + 1,
                    explicit=0,
                    subset=sub_id,
                    subproblem=sub_id,
                )
            )

        for v in var_idx:
            rows.append(
                MTISubProblemRow(
                    var_idx=int(v) + 1,
                    eq_idx=e0 + 1,
                    explicit=0,
                    subset=sub_id,
                    subproblem=sub_id,
                )
            )

        sub_id += 1

    return rows
