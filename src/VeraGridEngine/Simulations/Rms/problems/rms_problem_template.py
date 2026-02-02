# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from abc import ABC
from VeraGridEngine.basic_structures import Vec


class RmsProblemTemplate(ABC):

    def __init__(self):
        pass

    def get_all_vars_number(self) -> int:
        return 0

    def get_diff_var_number(self) -> int:
        return 0

    def get_algebraic_var_number(self) -> int:
        return 0

    def get_states_number(self) -> int:
        return 0

    def get_variable_parameter_number(self) -> int:
        return 0

    def get_constant_parameters(self) -> Vec:
        raise NotImplementedError("get_constant_parameters")

    def get_x0(self) -> Vec:
        raise NotImplementedError("get_x0")

    def compute_event_params(self, parameters: Vec, time_value: float) -> Vec:
        raise NotImplementedError("compute_event_params")

    def get_dx(self, x: Vec, xn: Vec, dx: Vec, h: float) -> Vec:
        raise NotImplementedError("derivative")

    def rhs_state(self, values: Vec, diff_values: Vec, variable_params: Vec, constant_params: Vec) -> Vec:
        raise NotImplementedError("rhs_state")

    def rhs_algebraic(self, values: Vec, diff_values: Vec, variable_params: Vec, constant_params: Vec) -> Vec:
        raise NotImplementedError("rhs_algebraic")

    def get_j11(self, x: Vec, dx: Vec, variable_params: Vec, constant_params: Vec, h: float):
        raise NotImplementedError("get_j11")

    def get_j12(self, x: Vec, dx: Vec, variable_params: Vec, constant_params: Vec, h: float):
        raise NotImplementedError("get_j12")

    def get_j21(self, x: Vec, dx: Vec, variable_params: Vec, constant_params: Vec, h: float):
        raise NotImplementedError("get_j21")

    def get_j22(self, x: Vec, dx: Vec, variable_params: Vec, constant_params: Vec, h: float):
        raise NotImplementedError("get_j22")
