# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from typing import Dict, List, Tuple
import time
import numpy as np
from VeraGridEngine.Devices import MultiCircuit
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.block_solver import (SymbolicDerivative, SymbolicJacobian, SymbolicVector,
                                                        SymbolicParamsVector)
from VeraGridEngine.Utils.Symbolic.symbolic import (Var, DiffVar, Const, Expr)
from VeraGridEngine.enumerations import SimulationBackend
from VeraGridEngine.Simulations.Rms.initialization import initialize_rms
from VeraGridEngine.basic_structures import Vec
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowResults
from VeraGridEngine.Simulations.Rms.rms_options import RmsOptions
from VeraGridEngine.Simulations.Rms.problems.rms_problem_template import RmsProblemTemplate


def _tic():
    return time.perf_counter()


def _toc(t0):
    return time.perf_counter() - t0


class RmsProblemDae(RmsProblemTemplate):
    """
    DAE (Differential-Algebraic Equation) class to store and manage.

    Responsibilities:
        - Store state and algebraic variables (x, y)
        - Store Jacobian matrices
        - Store residual equations
        - Store sparsity patterns
    """

    def __init__(self,
                 grid: MultiCircuit,
                 options: RmsOptions,
                 pf_results: PowerFlowResults | None):
        """

        :param grid:
        :param options:
        :param pf_results:
        """
        super().__init__()

        sim_time, ss, init_guess = initialize_rms(grid, pf_results, options.use_init_values)

        self._mapping = init_guess
        self._block_system: Block = ss

        # Flatten the block lists, preserving declaration order
        self._algebraic_vars: List[Var] = list()
        self._algebraic_eqs: List[Expr] = list()
        self._algebraic_eqs_substituted: List[Expr] = list()
        self._state_vars: List[Var] = list()
        self._state_eqs: List[Expr] = list()
        self._state_eqs_substituted: List[Expr] = list()
        self._diff_vars: List[DiffVar] = list()
        self._differential_eqs: List[Expr] = list()
        self._reformulated_vars: List[Var] = list()
        self._event_parameters: List[Var] = list()
        self._event_parameters_eqs: List[Expr] = list()
        self._parameters: List[Var] = list()
        self._parameters_values: List[Const] = list()
        self._stability_eqs: List[Expr] = list()

        # Class-level registry
        self._registry: Dict[int, DiffVar] = dict()  # int uuid , DiffVar
        self._absolute_registry: Dict[Tuple[int, int], DiffVar] = dict()

        # self.v_glob_name2uid = self.block_system.vars_glob_name2uid
        self._glob_time: Var = sim_time
        self._substitute = True

        # Numerical trace
        self._newton_trace_collector = None
        self._backend = SimulationBackend.SymbolicImplicit

        for b in self._block_system.get_all_blocks():
            self._algebraic_vars.extend(b.algebraic_vars)
            self._algebraic_eqs.extend(b.algebraic_eqs)
            self._state_vars.extend(b.state_vars)
            self._state_eqs.extend(b.state_eqs)
            for param, eq in b.event_dict.items():
                self._event_parameters.append(param)
                self._event_parameters_eqs.append(eq)
            for param, constant in b.parameters.items():
                self._parameters.append(param)
                self._parameters_values.append(constant)

            # if isinstance(b, DiffBlock):
            self._diff_vars.extend(b.diff_vars)
            # self._lag_vars.extend(b.lag_vars)
            # self._differential_eqs.extend(b.differential_eqs)
            # self._reformulated_vars.extend(b.reformulated_vars)

        self._diff_vars = sorted(self._diff_vars, key=lambda dv: dv.diff_order)
        self._state_algeb_vars = self._state_vars + self._algebraic_vars
        self._state_eqs_substituted = self._state_eqs.copy()

        # We define the parameter dt and delta
        self._dt = Var(name='dt')
        self._delta = Var(name='delta')
        self._event_parameters.append(self._dt)
        self._event_parameters.append(self._delta)
        self._event_parameters_eqs.append(Const(1e-3))
        self._event_parameters_eqs.append(Const(1))

        self._n_state = len(self._state_vars)
        self._n_alg = len(self._algebraic_vars)
        self._n_vars = self._n_state + self._n_alg
        self._n_event_params = len(self._event_parameters)
        self._n_params = len(self._parameters)
        self._n_diff = len(self._diff_vars)
        self._n_algebraic = len(self._algebraic_eqs)

        # generate the in-code names for each variable
        # inside the compiled functions the variables are
        # going to be represented by an array called vars[]

        self._compiler_names_dict: Dict[int, str] = dict()
        self._alias_names_dict: Dict[int, str] = dict()
        self._uid2idx_vars: Dict[int, int] = dict()
        self._uid2idx_event_params: Dict[int, int] = dict()
        self._uid2idx_params: Dict[int, int] = dict()
        self._uid2idx_diff: Dict[int, int] = dict()
        self._uid2idx_t: Dict[int, int] = dict()

        i = 0
        for v in self._state_vars:
            self._compiler_names_dict[v.uid] = f"vars[{i}]"
            self._alias_names_dict[v.uid] = f"vars_{i}"
            self._uid2idx_vars[v.uid] = i
            i += 1

        for v in self._algebraic_vars:
            self._compiler_names_dict[v.uid] = f"vars[{i}]"
            self._alias_names_dict[v.uid] = f"vars_{i}"
            self._uid2idx_vars[v.uid] = i
            i += 1

        j = 0
        for j, ep in enumerate(self._parameters):
            self._compiler_names_dict[ep.uid] = f"params[{j}]"
            self._alias_names_dict[ep.uid] = f"params_{j}"
            self._uid2idx_params[ep.uid] = j
            j += 1

        l = 0
        for l, ep in enumerate(self._event_parameters):
            self._compiler_names_dict[ep.uid] = f"event_params[{l}]"
            self._alias_names_dict[ep.uid] = f"event_params_{l}"
            self._uid2idx_event_params[ep.uid] = l
            l += 1

        k = 0
        for ep in self._diff_vars:
            self._compiler_names_dict[ep.uid] = f"diff[{k}]"
            self._alias_names_dict[ep.uid] = f"diff_{k}"
            self._uid2idx_diff[ep.uid] = k
            k += 1

        k = 0
        self._compiler_names_dict[self._glob_time.uid] = f"glob_time"
        self._uid2idx_t[self._glob_time.uid] = k

        for it, eq in enumerate(self._event_parameters_eqs):
            if isinstance(eq, Const) and eq.value is None:
                raise Exception(f' Event parameter {self._event_parameters[it]} has None Value')

        # define parameters
        self.alpha = 1
        alpha = self.alpha
        lag_can_be_0 = False  # TODO: will this allways be False??
        if lag_can_be_0:
            lag_init = 0
        else:
            lag_init = 1

        # Substitute in state eqs

        # Substitute in algebraic eqs
        self._stability_eqs = list()
        self._algebraic_eqs_substituted = self._algebraic_eqs.copy() + self._differential_eqs.copy()

        # fill stability equations by putting algebraic equations equal zero
        for it, eq in enumerate(self._algebraic_eqs):
            for diff_var in self._diff_vars:
                eq = eq.subs({diff_var: Const(0)})
                eq = eq.simplify()
            self._stability_eqs.append(eq)

        # Compile RHS and Jacobian

        """
                   state Var   algeb var  
        state eq |J11        | J12       |    | ∆ state var|    | ∆ state eq |
                 |           |           |    |            |    |            |
                 ------------------------- x  |------------|  = |------------|
        algeb eq |J21        | J22       |    | ∆ algeb var|    | ∆ algeb eq |
                 |           |           |    |            |    |            |
        """
        timings = dict()

        print("Compiling...")

        t0 = _tic()
        self._derivative_fn = SymbolicDerivative(
            vars=self._state_algeb_vars,
            uid2idx_vars=self._uid2idx_vars,
            diff_vars=self._diff_vars,
            compiler_names_dict=self._compiler_names_dict
        )
        timings["SymbolicDerivative"] = _toc(t0)

        t0 = _tic()
        self._rhs_algeb_fn = SymbolicVector(
            eqs=self._algebraic_eqs,
            compiler_names_dict=self._compiler_names_dict,
            alias_names_dict=self._alias_names_dict,
        )
        timings["RHS algebraic"] = _toc(t0)

        t0 = _tic()
        self._event_params_fn = SymbolicParamsVector(
            eqs=self._event_parameters_eqs,
            compiler_names_dict=self._compiler_names_dict,
            alias_names_dict=self._alias_names_dict,
        )
        timings["Event parameters"] = _toc(t0)

        if len(self._state_eqs) != 0:

            t0 = _tic()
            self._rhs_state_fn = SymbolicVector(
                eqs=self._state_eqs,
                compiler_names_dict=self._compiler_names_dict,
                alias_names_dict=self._alias_names_dict,
            )
            timings["RHS state"] = _toc(t0)

            t0 = _tic()
            self._j11_fn = SymbolicJacobian(
                eqs=self._state_eqs,
                variables=self._state_vars,
                diff_variables=self._diff_vars,
                compiler_names_dict=self._compiler_names_dict,
                alias_names_dict=self._alias_names_dict,
                uid2idx_vars=self._uid2idx_vars,
                dt=self._dt
            )
            timings["J11 (dF/dx)"] = _toc(t0)

            t0 = _tic()
            self._j12_fn = SymbolicJacobian(
                eqs=self._state_eqs,
                variables=self._algebraic_vars,
                diff_variables=self._diff_vars,
                compiler_names_dict=self._compiler_names_dict,
                alias_names_dict=self._alias_names_dict,
                uid2idx_vars=self._uid2idx_vars,
                dt=self._dt
            )
            timings["J12 (dF/dy)"] = _toc(t0)

            t0 = _tic()
            self._j21_fn = SymbolicJacobian(
                eqs=self._algebraic_eqs,
                variables=self._state_vars,
                diff_variables=self._diff_vars,
                compiler_names_dict=self._compiler_names_dict,
                alias_names_dict=self._alias_names_dict,
                uid2idx_vars=self._uid2idx_vars,
                dt=self._dt
            )
            timings["J21 (dG/dx)"] = _toc(t0)

            t0 = _tic()
            self._j22_fn = SymbolicJacobian(
                eqs=self._algebraic_eqs,
                variables=self._algebraic_vars,
                diff_variables=self._diff_vars,
                compiler_names_dict=self._compiler_names_dict,
                alias_names_dict=self._alias_names_dict,
                uid2idx_vars=self._uid2idx_vars,
                dt=self._dt
            )
            timings["J22 (dG/dy)"] = _toc(t0)

        else:
            t0 = _tic()
            self._j22_fn = SymbolicJacobian(
                eqs=self._algebraic_eqs,
                variables=self._algebraic_vars,
                diff_variables=self._diff_vars,
                compiler_names_dict=self._compiler_names_dict,
                alias_names_dict=self._alias_names_dict,
                uid2idx_vars=self._uid2idx_vars,
                dt=self._dt
            )
            timings["J22 only (no states)"] = _toc(t0)

        print(
            f"Model compiled with {self._n_vars} variables, "
            f"{len(self._algebraic_eqs_substituted)} algebraic eqs and "
            f"{len(self._state_eqs_substituted)} state eqs"
        )

        print("\nCompilation timing summary:")
        for k, v in timings.items():
            print(f"  {k: 30s}: {v: 8.4f} s")

        print(f"\nTotal compile time: {sum(timings.values()):.4f} s")

    @property
    def v_glob_name2uid(self):
        """

        :return:
        """
        return self._block_system.vars_glob_name2uid

    def get_all_vars_number(self) -> int:
        return self._n_vars

    def get_diff_var_number(self) -> int:
        """
        Get the number of diff vars
        :return:
        """
        return len(self._diff_vars)

    def get_algebraic_var_number(self) -> int:
        return len(self._algebraic_vars)

    def get_states_number(self) -> int:
        return self._n_state

    def get_variable_parameter_number(self) -> int:
        return len(self._parameters)

    def get_constant_parameters(self) -> Vec:
        return np.array([const.value for const in self._parameters_values])

    def get_x0(self) -> Vec:
        """
        Helper function to build the initial vector
        :return: array matching with the mapping, matching the solver ordering
        """
        x = np.zeros(len(self._state_vars) + len(self._algebraic_vars))

        for key, val in self._mapping.items():
            uid, name = key
            if uid in self._uid2idx_vars.keys():
                i = self._uid2idx_vars[uid]
                x[i] = val
            else:
                raise ValueError(f"Missing uid {key} definition")

        return x

    def compute_event_params(self, parameters: Vec, time_value: float) -> Vec:
        """

        :param parameters:
        :param time_value:
        :return:
        """
        return self._event_params_fn(parameters, time_value)

    def get_dx(self, x: Vec, xn: Vec, dx: Vec, h: float) -> Vec:
        raise self._derivative_fn(x, xn, dx, h)

    def rhs_state(self, values: Vec, diff_values: Vec, variable_params: Vec, constant_params: Vec) -> Vec:
        raise self._rhs_state_fn(values, diff_values, variable_params, constant_params)

    def rhs_algebraic(self, values: Vec, diff_values: Vec, variable_params: Vec, constant_params: Vec) -> Vec:
        raise self._rhs_algeb_fn(values, diff_values, variable_params, constant_params)

    def get_j11(self, x: Vec, dx: Vec, variable_params: Vec, constant_params: Vec, h: float):
        raise self._j11_fn(x, dx, variable_params, constant_params, h)

    def get_j12(self, x: Vec, dx: Vec, variable_params: Vec, constant_params: Vec, h: float):
        raise self._j12_fn(x, dx, variable_params, constant_params, h)

    def get_j21(self, x: Vec, dx: Vec, variable_params: Vec, constant_params: Vec, h: float):
        raise self._j21_fn(x, dx, variable_params, constant_params, h)

    def get_j22(self, x: Vec, dx: Vec, variable_params: Vec, constant_params: Vec, h: float):
        raise self._j22_fn(x, dx, variable_params, constant_params, h)
