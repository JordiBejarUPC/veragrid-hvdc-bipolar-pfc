# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

from typing import Tuple

import numpy as np

from VeraGridEngine.basic_structures import Vec
from VeraGridEngine.Utils.Symbolic.symbolic import Expr, Comparison
from VeraGridEngine.Utils.Symbolic.jit_compiler import RMSCompiler
from VeraGridEngine.Simulations.Rms.problems.rms_problem_dae import RmsProblemDae


class RmsProblemMTI(RmsProblemDae):
    """
    RMS problem exposing MTI-style equality/inequality evaluation.

    Equalities are the same implicit residuals used by the DAE solver.
    Inequalities are compiled locally in this MTI class from
    ``Block.inequalities`` and evaluated at runtime via ``rhs_inequalities``.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._mti_inequalities_raw: list[Expr | Comparison] = []
        self._mti_inequalities_compiled: list[Expr] = []
        self._rhs_ineq_fn = None
        self._compile_mti_inequalities()

    def _compile_mti_inequalities(self) -> None:
        self._mti_inequalities_raw = []
        for blk in self.sys_block.get_all_blocks():
            if hasattr(blk, "inequalities") and blk.inequalities:
                self._mti_inequalities_raw.extend(blk.inequalities)

        self._mti_inequalities_compiled = [self._normalize_inequality_expression(eq) for eq in self._mti_inequalities_raw]
        if len(self._mti_inequalities_compiled) == 0:
            self._rhs_ineq_fn = None
            return

        rms_compiler = RMSCompiler(
            variables=self._state_algeb_vars,
            diff_vars=self._diff_vars,
            v_params=self._variable_parameters,
            c_params=self._constant_parameters,
            dt_var=self._dt,
            compiler_names_dict=self._compiler_names_dict,
        )
        self._rhs_ineq_fn = rms_compiler.compile_rhs(self._mti_inequalities_compiled, "rhs_mti_ineq")

    @staticmethod
    def _normalize_inequality_expression(expr: Expr | Comparison) -> Expr:
        if isinstance(expr, Comparison):
            return expr.to_residual()
        if isinstance(expr, Expr):
            return expr
        raise TypeError(f"Unsupported inequality type: {type(expr).__name__}")

    def rhs_inequalities(self, x: Vec, dx: Vec) -> Vec:
        if self._rhs_ineq_fn is None:
            return np.zeros(0, dtype=float)
        return self._rhs_ineq_fn(x, dx, self._variable_parameters_values, self._constant_params)

    def compute_mti_equalities(self, x: Vec, dx: Vec, xn: Vec, h: float) -> Vec:
        """
        Compute equality residual vector F.
        """
        f_algeb = self.rhs_algebraic(x, dx)
        if self.get_states_number() > 0:
            f_state = self.rhs_state(x, dx)
            f_state_update = x[: self.get_states_number()] - xn[: self.get_states_number()] - h * f_state
            return np.r_[f_state_update, f_algeb]
        return np.asarray(f_algeb, dtype=float)

    def compute_mti_inequalities(self, x: Vec, dx: Vec, xn: Vec, h: float) -> Vec:
        """
        Compute inequality vector G (constraint convention: G <= 0).
        """
        return np.asarray(self.rhs_inequalities(x, dx), dtype=float)

    def update_mti_boolean_state(self, x: Vec, dx: Vec, xn: Vec, h: float) -> Vec:
        """
        Return current values of mode parameters.

        In this RMS implementation, Boolean/mode behavior is represented by
        runtime mode/event parameters (``mode_dict``/``event_dict``), not as a
        separate algebraic unknown vector.
        """
        if len(self.sys_block.mode_dict) == 0:
            return np.zeros(0, dtype=float)

        z = []
        for mode_var in self.sys_block.mode_dict.keys():
            idx = self._uid2idx_event_params.get(mode_var.uid, None)
            if idx is not None and self._variable_parameters_values is not None:
                z.append(float(self._variable_parameters_values[idx]))
        return np.asarray(z, dtype=float)

    def get_mti_boolean_parameter_indices(self) -> list[int]:
        indices: list[int] = []
        for mode_var in self.sys_block.mode_dict.keys():
            idx = self._uid2idx_event_params.get(mode_var.uid, None)
            if idx is not None:
                indices.append(int(idx))
        return indices

    def set_mti_boolean_state(self, z: Vec) -> None:
        idx = self.get_mti_boolean_parameter_indices()
        if len(idx) == 0 or self._variable_parameters_values is None:
            return
        for k, i in enumerate(idx):
            self._variable_parameters_values[i] = float(z[k])

    def evaluate_mti_step(self, x: Vec, dx: Vec, xn: Vec, h: float) -> Tuple[Vec, Vec, Vec]:
        """
        Evaluate one MTI step and return (F, G, z).
        """
        f = self.compute_mti_equalities(x, dx, xn, h)
        g = self.compute_mti_inequalities(x, dx, xn, h)
        z = self.update_mti_boolean_state(x, dx, xn, h)
        return f, g, z

    @staticmethod
    def inequalities_satisfied(g: Vec, tol: float = 1e-9) -> bool:
        """
        Check if all inequalities satisfy G <= tol.
        """
        if g is None or len(g) == 0:
            return True
        return bool(np.all(np.asarray(g) <= tol))
