# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import numpy as np
from matplotlib import pyplot as plt

import sys
import time
import os

from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Devices.Substation.bus import Bus
from VeraGridEngine.Devices.Injections.generator import Generator
from VeraGridEngine.Devices.Injections.load import Load
from VeraGridEngine.Devices.Branches.line import Line
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from VeraGridEngine.Devices.Aggregation.rms_event import RmsEvent
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Var
from VeraGridEngine.Utils.Symbolic.block_solver import BlockSolver
from VeraGridEngine.Simulations.Rms.initialization import initialize_rms

from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowResults, PowerFlowOptions
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowDriver
from VeraGridEngine import open_file, power_flow
import VeraGridEngine.api as gce

# ----------------------------------------------------------------------------------------------------------------------
# Power flow
# ----------------------------------------------------------------------------------------------------------------------
# Load system

# grid = open_file('Two_Areas_PSS_E/Benchmark_4ger_33_2015_noshunt_no_transformer.raw')
grid = open_file('Two_Areas_PSS_E/small_system_with_control.raw')
# Run power flow
res = power_flow(grid)

# # Print results
print(res.get_bus_df())
print(res.get_branch_df())
print(f"Converged: {res.converged}")




# ----------------------------------------------------------------------------------------------------------------------
# Time Domain Simulation
# ----------------------------------------------------------------------------------------------------------------------

# TDS initialization
ss, init_guess = initialize_rms(grid, res)
print("init_guess")
print(init_guess)


params_mapping = {}


# # Solver
slv = BlockSolver(ss, grid.time)


params0 = slv.build_init_params_vector(params_mapping)
x0 = slv.build_init_vars_vector_from_uid(init_guess)
vars_in_order = slv.sort_vars_from_uid(init_guess)

# simulate
t, y = slv.simulate(
    t0=0,
    t_end=20.0,
    h=0.001,
    x0=x0,
    params0=params0,
    method="implicit_euler"
)

# # Save to csv
slv.save_simulation_to_csv('simulation_results_Ieee_automatic_init.csv', t, y, csv_saving=True)

# # Plot
# plt.plot(t, y[:, slv.get_var_idx(slv._state_vars[1])], label="ω (pu)")
# plt.plot(t, y[:, slv.get_var_idx(slv._state_vars[4])], label="ω (pu)")
# plt.plot(t, y[:, slv.get_var_idx(slv._state_vars[7])], label="ω (pu)")
# plt.plot(t, y[:, slv.get_var_idx(slv._state_vars[10])], label="ω (pu)")

# plt.legend(loc='upper right', ncol=2)
# plt.xlabel("Time (s)")
# plt.ylabel("Values (pu)")
# plt.xlim([0, 20.0])
# plt.ylim([0.85, 1.15])
# plt.grid(True)
# plt.tight_layout()
# plt.show()
