# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import numpy as np
from scipy import sparse

from VeraGridEngine.Simulations.EMT.problems.emt_problem_dae import EmtProblemDae
from VeraGridEngine.Simulations.Rms.problems.rms_problem_multilinear import (
    RmsProblemMultilinear,
    SparseCoefficientTensor,
)
from VeraGridEngine.Utils.Symbolic.symbolic import Const, get_expr_factors


class EmtProblemMultilinear(EmtProblemDae):
    """
    EMT DAE problem with multilinear-oriented utilities.

    This class keeps the regular EMT symbolic assembly from ``EmtProblemDae``
    and adds the same sparse multilinear matrix extraction helpers used by
    ``RmsProblemMultilinear``. The EMT-specific part is parameter substitution:
    EMT runtime and constant values are stored in ``_event_params_values`` and
    ``_constant_params_values``.
    """

    def _ensure_multilinear_index_cache(self) -> None:
        """Build and cache multilinear index maps reused across methods."""
        if hasattr(self, "_ml_uid_to_idx_full"):
            return

        all_vars_sa = list(self._state_vars) + list(self._algebraic_vars)
        all_basis_vars = all_vars_sa + list(self._diff_vars)

        self._ml_all_vars_sa = all_vars_sa
        self._ml_all_basis_vars = all_basis_vars
        self._ml_idx_vars = [self._uid2idx_vars[v.uid] for v in all_vars_sa]
        self._ml_uid_to_basis_idx = {v.uid: i for i, v in enumerate(all_basis_vars)}
        self._ml_uid_to_idx_full = dict(self._ml_uid_to_basis_idx)

    def build_multilinear_matrices(self) -> tuple[sparse.csc_matrix, sparse.csr_matrix]:
        """
        Build ``(S, Phi)`` multilinear matrices from the EMT problem equations.

        ``S`` encodes monomial structure as ``variables x monomials`` and
        ``Phi`` encodes equation coefficients as ``equations x monomials``.
        """
        self._ensure_multilinear_index_cache()
        all_eqs = list(self._state_eqs) + list(self._algebraic_eqs)
        all_vars = self._ml_all_basis_vars
        uid_to_idx = self._ml_uid_to_basis_idx

        param_by_uid: dict[int, float] = {}
        subs_map: dict = {}

        for p, val in zip(self._variable_parameters, self._event_params_values):
            value = float(val)
            param_by_uid[p.uid] = value
            subs_map[p] = Const(value)

        for p, val in zip(self._constant_parameters, self._constant_params_values):
            value = float(val)
            param_by_uid[p.uid] = value
            subs_map[p] = Const(value)

        all_eqs = [eq.subs(subs_map) for eq in all_eqs]

        s_cols: list[tuple[tuple[int, float], ...]] = []
        monom_to_idx: dict[tuple[tuple[int, float], ...], int] = {}
        phi_rows: list[dict[int, float]] = []

        for eq in all_eqs:
            eq_row: dict[int, float] = {}
            mono_terms = self._collect_monomials(eq.simplify())

            for mono in mono_terms:
                monom_tuple, gain = self._term_to_monomial(
                    factors=get_expr_factors(mono),
                    base_gain=1.0,
                    uid_to_idx=uid_to_idx,
                    param_by_uid=param_by_uid,
                )
                if monom_tuple is None:
                    continue

                col_idx = monom_to_idx.get(monom_tuple)
                if col_idx is None:
                    col_idx = len(s_cols)
                    monom_to_idx[monom_tuple] = col_idx
                    s_cols.append(monom_tuple)

                eq_row[col_idx] = eq_row.get(col_idx, 0.0) + gain

            phi_rows.append(eq_row)

        n_vars = len(all_vars)
        n_mon = len(s_cols)
        n_eq = len(all_eqs)

        s_row: list[int] = []
        s_col: list[int] = []
        s_val: list[float] = []
        for j, mon in enumerate(s_cols):
            for i, val in mon:
                s_row.append(i)
                s_col.append(j)
                s_val.append(val)

        p_row: list[int] = []
        p_col: list[int] = []
        p_val: list[float] = []
        for i, row in enumerate(phi_rows):
            for j, val in row.items():
                p_row.append(i)
                p_col.append(j)
                p_val.append(val)

        S = sparse.csc_matrix((s_val, (s_row, s_col)), shape=(n_vars, n_mon))
        Phi = sparse.csr_matrix((p_val, (p_row, p_col)), shape=(n_eq, n_mon))
        self.S = S
        self.Phi = Phi
        return S, Phi

    _term_to_monomial = RmsProblemMultilinear._term_to_monomial
    _collect_monomials = RmsProblemMultilinear._collect_monomials
    _expr_to_float = staticmethod(RmsProblemMultilinear._expr_to_float)
    build_sparse_h_from_s_phi = RmsProblemMultilinear.build_sparse_h_from_s_phi
    fit_cptensor_from_s_phi = RmsProblemMultilinear.fit_cptensor_from_s_phi
    evaluate_residual_from_cptensor = RmsProblemMultilinear.evaluate_residual_from_cptensor
    exact_phi_from_s = RmsProblemMultilinear.exact_phi_from_s
    exact_residual_from_s_phi = RmsProblemMultilinear.exact_residual_from_s_phi
    linearize_multilinear = RmsProblemMultilinear.linearize_multilinear
    get_E_matrix = RmsProblemMultilinear.get_E_matrix
    get_static_state_matrix = RmsProblemMultilinear.get_static_state_matrix
    _compute_jacobian_sparse_from_S = staticmethod(RmsProblemMultilinear._compute_jacobian_sparse_from_S)


__all__ = [
    "EmtProblemMultilinear",
    "MultilinearCpTensor",
    "MultilinearCpnApproximator",
    "SparseCoefficientTensor",
]
