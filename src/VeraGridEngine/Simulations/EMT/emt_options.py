# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from typing import Tuple

from VeraGridEngine.Simulations.options_template import OptionsTemplate
from VeraGridEngine.enumerations import DynamicIntegrationMethod, EmtSolverTypes
from VeraGridEngine.Devices.Parents.editable_device import GCProp



class EmtOptions(OptionsTemplate):
    """
    Rms simulation options
    """

    LOCAL_PROPERTY_DECLARATIONS: Tuple[GCProp, ...] = (
        GCProp(key="time_step", tpe=float),
        GCProp(key="simulation_time", tpe=float),
        GCProp(key="tolerance", tpe=float),
        GCProp(key="solver", tpe=EmtSolverTypes),
        GCProp(key="integration_method", tpe=DynamicIntegrationMethod),
        GCProp(key="verbose", tpe=int),
        GCProp(key="newton_compute_dense_cond", tpe=bool),
        GCProp(key="newton_enable_fallback", tpe=bool),
        GCProp(key="newton_enable_index1_check", tpe=bool),
        GCProp(key="newton_enable_backtracking", tpe=bool),
        GCProp(key="newton_step_norm_explode", tpe=float),
        GCProp(key="newton_dense_cond_warn", tpe=float),
        GCProp(key="newton_dense_cond_max_n", tpe=int),
        GCProp(key="newton_index1_max_block_n", tpe=int),
        GCProp(key="newton_index1_warn_pivot_ratio", tpe=float),
        GCProp(key="newton_index1_fail_pivot_ratio", tpe=float),
        GCProp(key="newton_backtracking_beta", tpe=float),
        GCProp(key="newton_backtracking_min_alpha", tpe=float),
        GCProp(key="newton_backtracking_max_iter", tpe=int),
    )

    def __init__(self,
                 time_step: float = 0.0001,
                 simulation_time: float = 5,
                 tolerance: float = 1e-6,
                 solver: EmtSolverTypes = EmtSolverTypes.StructuralAD,
                 integration_method: DynamicIntegrationMethod = DynamicIntegrationMethod.DaeTrapezoidal,
                 verbose: int = 0,
                 newton_compute_dense_cond: bool = False,
                 newton_enable_fallback: bool = False,
                 newton_enable_index1_check: bool = False,
                 newton_enable_backtracking: bool = False,
                 newton_step_norm_explode: float = 1e6,
                 newton_dense_cond_warn: float = 1e12,
                 newton_dense_cond_max_n: int = 600,
                 newton_index1_max_block_n: int = 128,
                 newton_index1_warn_pivot_ratio: float = 1e-10,
                 newton_index1_fail_pivot_ratio: float = 1e-14,
                 newton_backtracking_beta: float = 0.5,
                 newton_backtracking_min_alpha: float = 1e-4,
                 newton_backtracking_max_iter: int = 6):
        """
        EmtOptions
        :param time_step: time step of the simulations (s)
        :param simulation_time: simulation time (s)
        :param tolerance: Integration tolerance
        :param verbose: Verbosity level
        """

        OptionsTemplate.__init__(self, name='EmtSimulationOptions')

        self.time_step: float = time_step
        self.simulation_time: float = simulation_time
        self.tolerance: float = tolerance
        self.solver: EmtSolverTypes = solver
        self.integration_method: DynamicIntegrationMethod = integration_method
        self.verbose = verbose
        self.newton_compute_dense_cond = newton_compute_dense_cond
        self.newton_enable_fallback = newton_enable_fallback
        self.newton_enable_index1_check = newton_enable_index1_check
        self.newton_enable_backtracking = newton_enable_backtracking
        self.newton_step_norm_explode = newton_step_norm_explode
        self.newton_dense_cond_warn = newton_dense_cond_warn
        self.newton_dense_cond_max_n = newton_dense_cond_max_n
        self.newton_index1_max_block_n = newton_index1_max_block_n
        self.newton_index1_warn_pivot_ratio = newton_index1_warn_pivot_ratio
        self.newton_index1_fail_pivot_ratio = newton_index1_fail_pivot_ratio
        self.newton_backtracking_beta = newton_backtracking_beta
        self.newton_backtracking_min_alpha = newton_backtracking_min_alpha
        self.newton_backtracking_max_iter = newton_backtracking_max_iter


