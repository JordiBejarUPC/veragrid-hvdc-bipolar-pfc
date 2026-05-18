# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

from typing import Tuple
import os

import numpy as np

from VeraGridEngine.basic_structures import Vec
from VeraGridEngine.Utils.Symbolic.symbolic import Expr, Comparison, get_expression_vars
from VeraGridEngine.Utils.Symbolic.jit_compiler import RMSCompiler
from VeraGridEngine.Simulations.Rms.problems.rms_problem_dae import RmsProblemDae
from VeraGridEngine.Simulations.Rms.problems.rms_problem_phasor import RmsProblemPhasor


class RmsProblemMTI(RmsProblemPhasor):
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
        self._mti_bool_param_indices: list[int] = []
        self._mti_bool_guard_compiled_by_param_idx: dict[int, object] = {}
        self._compile_mti_inequalities()
        self._compile_mti_boolean_guards()
        self._initialize_mti_booleans_at_t0()

    def add_variables_to_compilation_dicts(self, elm, mdl):
        super().add_variables_to_compilation_dicts(elm=elm, mdl=mdl)

        ineq_uids: set[int] = set()
        for ineq in mdl.inequalities:
            try:
                vars_in_ineq = get_expression_vars(ineq)
                for v in vars_in_ineq:
                    ineq_uids.add(v.uid)
            except Exception:
                pass

        for ep in mdl.boolean_guards.keys():
            if ep.uid not in ineq_uids:
                continue
            if ep.uid in self._uid2idx_event_params:
                continue
            self._compiler_names_dict[ep.uid] = f"{self.VARIABLE_PARAMS_NAME}[{self._n_event_params}]"
            self._alias_names_dict[ep.uid] = f"{self.VARIABLE_PARAMS_NAME}_{self._n_event_params}"
            self._uid2idx_event_params[ep.uid] = self._n_event_params
            self._variable_parameters.append(ep)
            self._event_parameters_eqs.append(ep)
            self._n_event_params += 1

    def update_variable_params(self, t: float, x_snapshot: Vec | None = None):
        self._variable_parameters_values[:self._n_event_params] = self._event_params_fn(self._variable_parameters_values, t)
        self._variable_parameters_values[self._n_event_params:] = self._mti_boolean_values(x_snapshot=x_snapshot)

    def _mti_boolean_values(self, x_snapshot: Vec | None = None) -> Vec:
        if self._variable_parameters_values is None:
            return np.zeros(0, dtype=float)
        n_bool = max(0, len(self._variable_parameters) - self._n_event_params)
        if n_bool == 0:
            return np.zeros(0, dtype=float)
        if x_snapshot is not None:
            try:
                dx = np.zeros(self.get_diff_var_number(), dtype=float)
                z = self.update_mti_boolean_state(x_snapshot, dx, x_snapshot, 0.0)
                if z is not None and len(z) == n_bool:
                    return np.asarray(z, dtype=float)
            except Exception:
                pass
        return np.asarray(self._variable_parameters_values[self._n_event_params:], dtype=float)

    def _initialize_mti_booleans_at_t0(self) -> None:
        """
        Initialize MTI boolean runtime parameters from their guards at x0.

        This avoids starting Newton with inconsistent all-zero mode values when
        many booleans are present.
        """
        if self._variable_parameters_values is None:
            return

        idx = self.get_mti_boolean_parameter_indices()
        if len(idx) == 0:
            return

        x0 = self.get_x0()
        dx0 = np.zeros(self.get_diff_var_number(), dtype=float)
        debug = os.getenv("RMS_MTI_DEBUG", "0").strip() in ("1", "true", "True", "yes", "on")
        if debug:
            print("[MTI-INIT] x0:", x0)

        z0 = np.zeros(len(idx), dtype=float)
        for k in range(len(idx)):
            guard_val = self.evaluate_boolean_guard(bool_position=k, x=x0, dx=dx0)
            if guard_val is None:
                # Keep existing value when no dedicated guard exists.
                current = float(self._variable_parameters_values[idx[k]])
                z0[k] = 1.0 if current >= 0.5 else 0.0
            else:
                # Guard residual convention in MTI is G <= 0 when condition holds.
                z0[k] = 1.0 if guard_val <= 0.0 else 0.0
            if debug:
                print(f"[MTI-INIT] bool_pos={k} param_idx={idx[k]} guard={guard_val} z0={z0[k]}")

        self.set_mti_boolean_state(z0)
        if debug:
            print("[MTI-INIT] initial z0:", z0)

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

    def _compile_mti_boolean_guards(self) -> None:
        self._mti_bool_param_indices = []
        self._mti_bool_guard_compiled_by_param_idx = {}

        rms_compiler = RMSCompiler(
            variables=self._state_algeb_vars,
            diff_vars=self._diff_vars,
            v_params=self._variable_parameters,
            c_params=self._constant_parameters,
            dt_var=self._dt,
            compiler_names_dict=self._compiler_names_dict,
        )

        for blk in self.sys_block.get_all_blocks():
            for bool_var, guard_expr in getattr(blk, "boolean_guards", {}).items():
                param_idx = self._uid2idx_event_params.get(bool_var.uid, None)
                if param_idx is None:
                    continue
                if int(param_idx) not in self._mti_bool_param_indices:
                    self._mti_bool_param_indices.append(int(param_idx))

                guard_residual = self._normalize_inequality_expression(guard_expr)
                self._mti_bool_guard_compiled_by_param_idx[int(param_idx)] = rms_compiler.compile_rhs(
                    [guard_residual],
                    f"rhs_mti_guard_{int(param_idx)}",
                )

        self._mti_bool_param_indices.sort()

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
        Return current values of MTI boolean parameters.
        """
        if self._variable_parameters_values is None:
            return np.zeros(0, dtype=float)

        z = np.zeros(len(self._mti_bool_param_indices), dtype=float)
        for k, idx in enumerate(self._mti_bool_param_indices):
            z[k] = 1.0 if float(self._variable_parameters_values[idx]) >= 0.5 else 0.0
        return z

    def get_mti_boolean_parameter_indices(self) -> list[int]:
        return list(self._mti_bool_param_indices)

    def set_mti_boolean_state(self, z: Vec) -> None:
        idx = self.get_mti_boolean_parameter_indices()
        if len(idx) == 0 or self._variable_parameters_values is None:
            return
        for k, i in enumerate(idx):
            self._variable_parameters_values[i] = float(z[k])

    def evaluate_boolean_guard(self, bool_position: int, x: Vec, dx: Vec) -> float | None:
        idx = self.get_mti_boolean_parameter_indices()
        if bool_position < 0 or bool_position >= len(idx):
            return None

        param_idx = idx[bool_position]
        guard_fn = self._mti_bool_guard_compiled_by_param_idx.get(param_idx, None)
        if guard_fn is None:
            return None

        out = guard_fn(x, dx, self._variable_parameters_values, self._constant_params)
        if out is None or len(out) == 0:
            return None
        return float(out[0])

    def has_boolean_guard(self, bool_position: int) -> bool:
        idx = self.get_mti_boolean_parameter_indices()
        if bool_position < 0 or bool_position >= len(idx):
            return False
        return idx[bool_position] in self._mti_bool_guard_compiled_by_param_idx

    def split_direct_and_coupled_booleans(self) -> tuple[list[int], list[int]]:
        """
        Return boolean positions split into direct-test and coupled groups.

        A boolean is considered direct if a dedicated guard expression exists.
        """
        n_bool = len(self.get_mti_boolean_parameter_indices())
        direct: list[int] = []
        coupled: list[int] = []
        for pos in range(n_bool):
            if self.has_boolean_guard(pos):
                direct.append(pos)
            else:
                coupled.append(pos)
        return direct, coupled

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
