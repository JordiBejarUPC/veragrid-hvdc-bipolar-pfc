# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from abc import ABC
import numpy as np
from typing import Dict, List, Optional, Any

from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Expr, Var
from VeraGridEngine.basic_structures import Vec


def _get_diff_var_sort_key(diff_var: Var) -> int:
    """
    Return the ordering key used to sort differential variables.

    :param diff_var: Differential variable to inspect.
    :return: Sorting key associated with the differential variable.
    """
    return diff_var.diff_order


def _get_external_mapping(mdl: Block) -> Optional[Dict[Any, Var]]:
    """
    Return the external mapping associated with a model block.

    :param mdl: Model block to inspect.
    :return: External mapping dictionary or None.
    """
    external_mapping: Optional[Dict[Any, Var]] = mdl.external_mapping

    if external_mapping is None:
        return None
    else:
        return external_mapping


class EmtProblemTemplate(ABC):
    """
    Intermediate layer that manages DAE plumbing including indexing, variable mapping,
    and event updating, regardless of whether the system comes from an electrical
    circuit or a generic mathematical model.
    """

    VARS_NAME = "vars"
    VARIABLE_PARAMS_NAME = "vprms"
    CONSTANT_PARAMS_NAME = "cprms"
    DIFF_NAME = "diff"
    TIME_NAME = "glob_time"

    def __init__(self, sys_block: Block, glob_time: Var)->None:
        """
        Initialize the EMT problem template.

        :param sys_block: Root symbolic block that defines the EMT problem.
        :param glob_time: Global time variable used by runtime expressions.
        :return: None
        """
        super().__init__()
        self.sys_block: Block = sys_block
        self._glob_time: Var = glob_time
        self._newton_trace_collector: Optional[Any] = None

        self._state_vars: List[Var] = self.sys_block.state_vars
        self._algebraic_vars: List[Var] = self.sys_block.algebraic_vars
        self._state_eqs: List[Any] = self.sys_block.state_eqs
        self._algebraic_eqs: List[Any] = self.sys_block.algebraic_eqs
        self._diff_vars: List[Var] = self.sys_block.diff_vars

        self._constant_parameters: List[Var] = list(self.sys_block.parameters.keys())
        self._parameters_values: List[Const] = list(self.sys_block.parameters.values())

        self._variable_parameters: List[Var] = list()
        self._event_parameters_eqs: List[Any] = list()

        self._variable_parameters: List[Var] = list()
        self._event_parameters_eqs: List[Any] = list()
        self._runtime_mode_uids: set[int] = set()

        if self.sys_block.event_dict:
            self._variable_parameters.extend(list(self.sys_block.event_dict.keys()))
            self._event_parameters_eqs.extend(list(self.sys_block.event_dict.values()))

        if hasattr(self.sys_block, 'mode_dict') and self.sys_block.mode_dict:
            self._variable_parameters.extend(list(self.sys_block.mode_dict.keys()))
            self._event_parameters_eqs.extend(list(self.sys_block.mode_dict.values()))
            for v in self.sys_block.mode_dict.keys():
                self._runtime_mode_uids.add(v.uid)

        self._runtime_all_parameters_source: List[Var] = list(self._variable_parameters)
        self._runtime_all_eqs_source: List[Any] = list(self._event_parameters_eqs)

        self._runtime_continuous_parameters: List[Var] = list()
        self._runtime_mode_parameters: List[Var] = list()

        self._runtime_continuous_eqs: List[Any] = list()
        self._runtime_mode_eqs: List[Any] = list()

        self._runtime_continuous_slice: slice = slice(0, 0)
        self._runtime_mode_slice: slice = slice(0, 0)

        self._rebuild_runtime_parameter_partition()

        self.init_guess: Dict[int, float] = dict()
        self.diff_init_guess: Dict[int, float] = dict()
        self._vars_info: Dict[Any, List[Var]] = dict()

        self._finalize_order_and_maps()
        self._event_params_values: Vec = np.zeros(0, dtype=np.float64)
        self._constant_params_values: Vec = np.zeros(0, dtype=np.float64)
        self._build_runtime_param_vectors()

    @property
    def glob_time(self) -> Var:
        """
        Return the global time symbolic variable.

        :return: Global time symbolic variable.
        """
        return self._glob_time

    def _finalize_order_and_maps(self)->None:
        """
        Build canonical ordering, index maps and internal counters.

        :return: None
        """

        self._diff_vars = sorted(self._diff_vars, key=_get_diff_var_sort_key)

        self._n_state = len(self._state_vars)
        self._n_alg = len(self._algebraic_vars)
        self._n_vars = self._n_state + self._n_alg
        self._n_event_params = len(self._variable_parameters)
        self._n_params = len(self._constant_parameters)
        self._n_diff = len(self._diff_vars)
        self._n_algebraic = len(self._algebraic_eqs)

        self._compiler_names_dict: Dict[int, str] = dict()
        self._alias_names_dict: Dict[int, str] = dict()
        self._uid2idx_vars: Dict[int, int] = dict()
        self._uid2idx_event_params: Dict[int, int] = dict()
        self._uid2idx_params: Dict[int, int] = dict()
        self._uid2idx_diff: Dict[int, int] = dict()
        self._uid2idx_t: Dict[int, int] = dict()

        i: int = 0
        for v in self._state_vars:
            self._compiler_names_dict[v.uid] = f"{self.VARS_NAME}[{i}]"
            self._alias_names_dict[v.uid] = f"{self.VARS_NAME}_{i}"
            self._uid2idx_vars[v.uid] = i
            i += 1

        for v in self._algebraic_vars:
            self._compiler_names_dict[v.uid] = f"{self.VARS_NAME}[{i}]"
            self._alias_names_dict[v.uid] = f"{self.VARS_NAME}_{i}"
            self._uid2idx_vars[v.uid] = i
            i += 1

        for j, p in enumerate(self._constant_parameters):
            self._compiler_names_dict[p.uid] = f"{self.CONSTANT_PARAMS_NAME}[{j}]"
            self._alias_names_dict[p.uid] = f"{self.CONSTANT_PARAMS_NAME}_{j}"
            self._uid2idx_params[p.uid] = j

        for k, p in enumerate(self._variable_parameters):
            self._compiler_names_dict[p.uid] = f"{self.VARIABLE_PARAMS_NAME}[{k}]"
            self._alias_names_dict[p.uid] = f"{self.VARIABLE_PARAMS_NAME}_{k}"
            self._uid2idx_event_params[p.uid] = k

        for k, d in enumerate(self._diff_vars):
            self._compiler_names_dict[d.uid] = f"{self.DIFF_NAME}[{k}]"
            self._alias_names_dict[d.uid] = f"{self.DIFF_NAME}_{k}"
            self._uid2idx_diff[d.uid] = k

        self._compiler_names_dict[self._glob_time.uid] = self.TIME_NAME
        self._uid2idx_t[self._glob_time.uid] = 0

    def _build_runtime_param_vectors(self) -> None:
        """
        Build and initialize runtime and constant parameter buffers.

        Runtime parameters are kept in a single flat vector. Continuous and mode
        families are only distinguished by slices and by the update rules applied
        later during the simulation.

        :return: None
        """
        n_runtime: int = self.get_variable_parameter_number()

        self._event_params_values = np.zeros(n_runtime, dtype=np.float64)

        if n_runtime > 0:
            self._event_params_values = self._initialize_runtime_parameter_values(0.0)
            self._event_params_values = self.def_event_params_fn(self._event_params_values, 0.0)
        else:
            pass

        self._constant_params_values = np.array(
            [parameter.value for parameter in self._parameters_values],
            dtype=np.float64
        )

    def _rebuild_runtime_parameter_partition(self) -> None:
        """
        Rebuild the runtime parameter partition.

        The runtime parameters are stored in a single flat vector, but their
        order is redefined so that continuous runtime inputs appear first and
        retained discrete mode parameters appear afterwards.

        :return: None
        """
        self._runtime_continuous_parameters = list()
        self._runtime_mode_parameters = list()

        self._runtime_continuous_eqs = list()
        self._runtime_mode_eqs = list()

        n_source: int = len(self._runtime_all_parameters_source)
        i: int = 0

        while i < n_source:
            parameter: Var = self._runtime_all_parameters_source[i]
            equation: Any = self._runtime_all_eqs_source[i]

            if parameter.uid in self._runtime_mode_uids:
                self._runtime_mode_parameters.append(parameter)
                self._runtime_mode_eqs.append(equation)
            else:
                self._runtime_continuous_parameters.append(parameter)
                self._runtime_continuous_eqs.append(equation)

            i += 1

        self._variable_parameters = list()
        self._event_parameters_eqs = list()

        for parameter in self._runtime_continuous_parameters:
            self._variable_parameters.append(parameter)

        for parameter in self._runtime_mode_parameters:
            self._variable_parameters.append(parameter)

        for equation in self._runtime_continuous_eqs:
            self._event_parameters_eqs.append(equation)

        for equation in self._runtime_mode_eqs:
            self._event_parameters_eqs.append(equation)

        n_continuous: int = len(self._runtime_continuous_parameters)
        n_mode: int = len(self._runtime_mode_parameters)

        self._runtime_continuous_slice = slice(0, n_continuous)
        self._runtime_mode_slice = slice(n_continuous, n_continuous + n_mode)

    def set_runtime_mode_parameters(self, mode_parameters: List[Var]) -> None:
        """
        Classify a subset of runtime parameters as retained discrete mode parameters.

        The physical storage remains a single flat runtime vector. This method
        only changes the semantic partition and rebuilds the associated index maps
        and runtime initialization buffers.

        :param mode_parameters: Runtime parameters to classify as mode parameters.
        :return: None
        """
        valid_runtime_uids: set[int] = set()
        selected_mode_uids: set[int] = set()

        for parameter in self._runtime_all_parameters_source:
            valid_runtime_uids.add(parameter.uid)

        for parameter in mode_parameters:
            if parameter.uid in valid_runtime_uids:
                selected_mode_uids.add(parameter.uid)
            else:
                raise KeyError(
                    f"Runtime mode parameter uid={parameter.uid} does not belong to the runtime parameter source."
                )

        self._runtime_mode_uids = selected_mode_uids
        self._rebuild_runtime_parameter_partition()
        self._finalize_order_and_maps()
        self._build_runtime_param_vectors()

    def _initialize_runtime_parameter_values(self, tm: float) -> Vec:
        """
        Initialize the flat runtime parameter vector at a given time.

        This method evaluates the full runtime parameter list once in the final
        flat order. It is used for initialization only. Continuous parameters are
        then refined afterwards by def_event_params_fn().

        :param tm: Initialization time.
        :return: Initialized runtime parameter vector.
        """
        n_runtime: int = len(self._variable_parameters)
        out: Vec = np.zeros(n_runtime, dtype=np.float64)

        i: int = 0
        while i < n_runtime:
            expression: Any = self._event_parameters_eqs[i]
            out[i] = self._evaluate_runtime_expression(expression, out, tm)
            i += 1

        return out

    def _evaluate_runtime_expression(self, expression: Any, runtime_params: Vec, tm: float) -> float:
        """
        Evaluate a runtime parameter expression.

        The evaluation uses UID-based bindings to avoid ambiguous name-based
        dispatch and to keep the runtime parameter update logic deterministic.

        :param expression: Symbolic or numeric expression.
        :param runtime_params: Current flat runtime parameter vector.
        :param tm: Current time.
        :return: Numeric value of the expression.
        """
        if isinstance(expression, Const):
            if expression.value is None:
                return 0.0
            else:
                return float(expression.value)

        elif isinstance(expression, Var):
            if expression.uid == self._glob_time.uid or expression.name in {"time", self.TIME_NAME}:
                return float(tm)
            else:
                idx_runtime: int | None = self._uid2idx_event_params.get(expression.uid, None)
                if idx_runtime is not None:
                    return float(runtime_params[idx_runtime])
                else:
                    idx_const: int | None = self._uid2idx_params.get(expression.uid, None)
                    if idx_const is not None:
                        return float(self._parameters_values[idx_const].value)
                    else:
                        raise KeyError(f"Unknown runtime expression variable uid={expression.uid}")

        elif isinstance(expression, Expr):
            uid_bindings: Dict[int, float] = dict()

            for uid, idx in self._uid2idx_event_params.items():
                uid_bindings[uid] = float(runtime_params[idx])

            for uid, idx in self._uid2idx_params.items():
                uid_bindings[uid] = float(self._parameters_values[idx].value)

            uid_bindings[self._glob_time.uid] = float(tm)
            for var in expression.get_vars():
                if var.name in {"time", self.TIME_NAME}:
                    uid_bindings[var.uid] = float(tm)

            return float(expression.eval_uid(uid_bindings))

        else:
            return float(expression)

    def get_state_vars(self)->List[Var]:
        """
        Return the ordered list of state variables.

        :return: Ordered list of state variables.
        """
        return self._state_vars

    def get_algebraic_vars(self)->List[Var]:
        """
        Return the ordered list of algebraic variables.

        :return: Ordered list of algebraic variables.
        """
        return self._algebraic_vars

    def get_state_eqs(self)->List[Any]:
        """
        Return the ordered list of state equations.

        :return: Ordered list of state equations.
        """
        return self._state_eqs

    def get_algebraic_eqs(self)->List[Any]:
        """
        Return the ordered list of algebraic equations.

        :return: Ordered list of algebraic equations.
        """
        return self._algebraic_eqs

    def get_variable_parameters(self)-> List[Var]:
        """
        Return the ordered list of runtime parameters.

        :return: Ordered list of runtime parameters.
        """
        return self._variable_parameters

    def get_constant_parameters(self)-> List[Var]:
        """
        Return the ordered list of constant parameters.

        :return: Ordered list of constant parameters.
        """
        return self._constant_parameters

    def get_diff_vars(self)-> List[Var]:
        """
        Return the ordered list of differential variables.

        :return: Ordered list of differential variables.
        """
        return self._diff_vars

    def get_parameters_values(self)-> List[Const]:
        """
        Return the ordered list of constant parameter values.

        :return: Ordered list of constant parameter values.
        """
        return self._parameters_values

    def get_all_vars_number(self) -> int:
        """
        Return the total number of state and algebraic variables.

        :return: Total number of variables.
        """
        return self._n_vars

    def get_diff_var_number(self) -> int:
        """
        Return the number of differential variables.

        :return: Number of differential variables.
        """
        return self._n_diff

    def get_algebraic_var_number(self) -> int:
        """
        Return the number of algebraic variables.

        :return: Number of algebraic variables.
        """
        return self._n_alg

    def get_states_number(self) -> int:
        """
        Return the number of state variables.

        :return: Number of state variables.
        """
        return self._n_state

    def get_variable_parameter_number(self) -> int:
        """
        Return the number of runtime parameters.

        :return: Number of runtime parameters.
        """
        return self._n_event_params

    def get_x0(self) -> Vec:
        """
        Build the initial state vector from the stored initialization guess.

        :return: Initial state vector.
        """
        x = np.zeros(self._n_vars, dtype=np.float64)
        for uid, val in self.init_guess.items():
            idx = self._uid2idx_vars.get(uid, None)
            if idx is not None:
                x[idx] = float(val)

        return x

    def get_dx0(self) -> Vec:
        """
        Build the initial differential vector from the stored differential initialization guess.

        :return: Initial differential vector.
        """
        dx = np.zeros(self._n_diff, dtype=np.float64)
        for uid, val in self.diff_init_guess.items():
            idx = self._uid2idx_diff.get(uid, None)
            if idx is not None:
                dx[idx] = float(val)
        return dx

    def def_event_params_fn(self, ev_param: Vec, tm: float) -> Vec:
        """
        Update only the continuous runtime parameter slice.

        Retained discrete mode parameters are preserved exactly as they enter
        this function. They are expected to be modified explicitly by the
        boundary update layer or by future event logic.

        :param ev_param: Current flat runtime parameter vector.
        :param tm: Current simulation time.
        :return: Updated flat runtime parameter vector.
        """
        n_continuous: int = len(self._runtime_continuous_eqs)

        if n_continuous == 0:
            return ev_param
        else:
            out: Vec = ev_param.copy()

            i: int = 0
            while i < n_continuous:
                global_idx: int = self._runtime_continuous_slice.start + i
                expression: Any = self._runtime_continuous_eqs[i]

                out[global_idx] = self._evaluate_runtime_expression(expression, out, tm)
                i += 1

            return out

    def update_variable_params(self, t: float) -> None:
        """
        Update the internal runtime parameter values at the given time.

        :param t: Current time.
        :return: None
        """
        self._event_params_values = self.def_event_params_fn(self._event_params_values, float(t))

    def get_full_param_index(self, uid: int) -> int:
        """
        Return the flat full-parameter index associated with the given UID.

        :param uid: Parameter unique identifier.
        :return: Flat index inside the full parameter vector.
        """
        n_ev = len(self._variable_parameters)
        if uid in self._uid2idx_event_params:
            return self._uid2idx_event_params[uid]
        if uid in self._uid2idx_params:
            return n_ev + self._uid2idx_params[uid]
        raise KeyError(f"Unknown param uid={uid}")

    def get_newton_trace_collector(self) -> Optional[Any]:
        """
        Return the Newton trace collector instance.

        :return: Newton trace collector instance or None.
        """
        return self._newton_trace_collector

    def set_newton_trace_collector(self, collector: Any)->None:
        """
        Set the Newton trace collector instance.

        :param collector: Newton trace collector instance.
        :return: None
        """
        self._newton_trace_collector = collector

    def get_device_vars_dict(self) -> Dict[Any, List[Var]]:
        """
        Return the device-to-variable mapping dictionary.

        :return: Device-to-variable mapping dictionary.
        """
        return self._vars_info

    def get_var_idx(self, v: Var) -> int:
        """
        Return the flat variable index associated with the given variable.

        :param v: Variable to locate.
        :return: Flat variable index.
        """
        return self._uid2idx_vars[v.uid]

    def get_diff_var_idx(self, dv: Var) -> int:
        """
        Return the flat differential index associated with the given differential variable.

        :param dv: Differential variable to locate.
        :return: Flat differential index.
        """
        return self._uid2idx_diff[dv.uid]

    def set_init_guess(self, mdl: Block, reference_powerflow: Any, val: float) -> None:
        """
        Set the initialization guess associated with a model external mapping.

        :param mdl: Model block containing the external mapping.
        :param reference_powerflow: Reference key used to locate the mapped variable.
        :param val: Initialization value.
        :return: None
        """
        external_mapping: Optional[Dict[Any, Var]] = _get_external_mapping(mdl)

        if external_mapping is None:
            pass
        else:
            var: Optional[Var] = external_mapping.get(reference_powerflow, None)

            if var is None:
                pass
            else:
                self.init_guess[var.uid] = float(val)

    def get_floquet_ak_stack(
            self,
            trajectory: np.ndarray,
            h: float,
            jac_evaluator: Optional[Any] = None,
            static_params: Optional[Vec] = None
    ) -> Optional[np.ndarray]:
        """
        Return the stack of transition matrices used for Floquet analysis.

        :param trajectory: State trajectory over one period.
        :param h: Time step.
        :param jac_evaluator: Optional Jacobian evaluator.
        :param static_params: Optional static parameter vector.
        :return: Stack of transition matrices or None.
        """
        return None

    def get_runtime_continuous_slice(self) -> slice:
        """
        Return the slice of continuous runtime inputs inside the flat runtime vector.

        :return: Continuous runtime slice.
        """
        return self._runtime_continuous_slice

    def get_runtime_mode_slice(self) -> slice:
        """
        Return the slice of retained mode parameters inside the flat runtime vector.

        :return: Mode runtime slice.
        """
        return self._runtime_mode_slice

    def get_runtime_continuous_parameters(self) -> List[Var]:
        """
        Return the ordered list of continuous runtime parameters.

        :return: Continuous runtime parameters.
        """
        return self._runtime_continuous_parameters

    def get_runtime_mode_parameters(self) -> List[Var]:
        """
        Return the ordered list of retained mode runtime parameters.

        :return: Mode runtime parameters.
        """
        return self._runtime_mode_parameters

    @property
    def uid2idx_vars(self)-> Dict[int, int]:
        """
        Return the UID-to-variable-index mapping.

        :return: UID-to-variable-index mapping.
        """
        return self._uid2idx_vars

    @property
    def uid2idx_params(self)-> Dict[int, int]:
        """
        Return the UID-to-constant-parameter-index mapping.

        :return: UID-to-constant-parameter-index mapping.
        """
        return self._uid2idx_params

    @property
    def uid2idx_event_params(self)-> Dict[int, int]:
        """
        Return the UID-to-runtime-parameter-index mapping.

        :return: UID-to-runtime-parameter-index mapping.
        """
        return self._uid2idx_event_params

    @property
    def uid2idx_diff(self)-> Dict[int, int]:
        """
        Return the UID-to-differential-index mapping.

        :return: UID-to-differential-index mapping.
        """
        return self._uid2idx_diff

    @property
    def event_params_values(self)-> Vec:
        """
        Return the current flat runtime parameter vector.

        :return: Current flat runtime parameter vector.
        """
        return self._event_params_values



