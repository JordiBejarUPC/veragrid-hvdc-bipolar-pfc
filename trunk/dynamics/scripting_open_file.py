# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import os
import VeraGridEngine.api as gce
from matplotlib import pyplot as plt

from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Simulations.Rms.problems.rms_problem_dae import RmsProblemDae
from VeraGridEngine.Simulations.Rms.rms_options import RmsOptions
from VeraGridEngine.Simulations.Rms.numerical.back_euler_fx import BackEulerImplicitIntegration


from VeraGridEngine.enumerations import DynamicIntegrationMethod, RmsInitializationMethod



TEST_GRID_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "grids"))

def get_grid_path(file_name: str) -> str:
    """
    Build an absolute path to a grid fixture used by the strict NTC tests.

    :param file_name: Grid fixture file name.
    :return: Absolute grid fixture path.
    """
    return os.path.join(TEST_GRID_DIR, file_name)

def find_name_in_block(name: str, block: Block):
    for var in block.algebraic_vars + block.state_vars + list(block.event_dict.keys()):
        if name == var.name:
            return var

    for mdl in block.children:
        res = find_name_in_block(name, mdl)
        if res is not None:
            return res

# ###########################################################################################################################
# OPEN GRID
# ###########################################################################################################################


# fname = get_grid_path('genqec_load_grid_load_event.veragrid')
fname = os.path.join('genqec_load_grid_load_event.veragrid')

# 1 way
# options_fileopen = gce.FileOpenOptions(
#                                        )
# grid = gce.FileOpen(fname).open()

# other way
grid = gce.open_file(fname)

# either way when it opens the circuit is none so that's why it can't be opened correctly!

events_group = grid._rms_events_groups

rms_events_group_names = grid.get_rms_events_groups_names()

# ###########################################################################################################################
# Power Flow
# ###########################################################################################################################


options = gce.PowerFlowOptions(
    solver_type=gce.SolverType.NR,
    retry_with_other_methods=False,
    verbose=0,
    initialize_with_existing_solution=True,
    tolerance=1e-6,
    max_iter=25,
    control_q=False,
    control_taps_modules=True,
    control_taps_phase=True,
    control_remote_voltage=True,
    orthogonalize_controls=True,
    apply_temperature_correction=True,
    branch_impedance_tolerance_mode=gce.BranchImpedanceMode.Specified,
    distributed_slack=False,
    ignore_single_node_islands=False,
    trust_radius=1.0,
    backtracking_parameter=0.05,
    use_stored_guess=False,
    initialize_angles=False,
    generate_report=False,
)
res = gce.power_flow(grid, options=options)

print(f"Converged: {res.converged}")
print(res.get_bus_df())
print(res.get_branch_df())

params_mapping = dict()

options = RmsOptions(time_step=0.001,
                     simulation_time=5,
                     tolerance=1e-6,
                     integration_method=DynamicIntegrationMethod.DaeBackEuler,
                     initialization_method=RmsInitializationMethod.Explicit,
                     use_init_values=False,
                     max_iter=1000,
                     verbose=0)

######################################################################################################
# Prepare and run simulation
######################################################################################################


problem = RmsProblemDae(grid=grid,
                        options=options,
                        pf_results=res)

problem.set_events_group(events_group[0])


solver = BackEulerImplicitIntegration(
    problem=problem,
    t0=0,
    t_end=options.simulation_time,
    h=options.time_step,
    max_iter=options.max_iter,
)

t, y, well_initialized, converged = solver.simulate()

xlim = options.simulation_time
genqec_mdl = grid.get_generators()[0].rms_model

omega = find_name_in_block("omega", genqec_mdl)
Pg = genqec_mdl.out_vars[0]
Qg = genqec_mdl.out_vars[1]
Ir = find_name_in_block("Ir", genqec_mdl)
Efd = find_name_in_block("Efd", genqec_mdl)
Te = find_name_in_block("Te", genqec_mdl)
Vm = find_name_in_block("Vm", genqec_mdl)

u_gov1 = find_name_in_block("u_gov1", genqec_mdl)
y_subexciter = find_name_in_block("y_subexciter1", genqec_mdl)
y_exciter1 = find_name_in_block("y_exciter1", genqec_mdl)
y_exciter4 = find_name_in_block("y_exciter4", genqec_mdl)
Efe = find_name_in_block("Efe", genqec_mdl)
delta = find_name_in_block("delta", genqec_mdl)

# Generator state variables
plt.plot(t, y[:, problem.get_var_idx(omega)], label="omega (pu)")
plt.plot(t, y[:, problem.get_var_idx(delta)], label="delta (pu)")
# plt.plot(t, y[:, problem.get_var_idx(Vm)], label="Vm (pu)")
plt.plot(t, y[:, problem.get_var_idx(Pg)], label="P (pu)")
plt.plot(t, y[:, problem.get_var_idx(Qg)], label="Q (pu)")
# plt.plot(t, y[:, solver.get_var_idx(Ir)], label="Ir (pu)")

plt.legend(loc='upper right', ncol=2)
plt.xlabel("Time (s)")
plt.ylabel("Values (pu)")
plt.xlim([0, xlim])
# plt.ylim([0.85, 1.15])
plt.grid(True)
plt.tight_layout()
plt.show()


Eq_prime = find_name_in_block("Eq_prime", genqec_mdl)
Ed_prime = find_name_in_block("Ed_prime", genqec_mdl)
Psiq_prime = find_name_in_block("Psiq_prime", genqec_mdl)
Psid_prime = find_name_in_block("Psid_prime", genqec_mdl)

Ed1 = find_name_in_block("Ed1", genqec_mdl)
Eq1 = find_name_in_block("Eq1", genqec_mdl)

# Generator state variables
plt.plot(t, y[:, problem.get_var_idx(Eq_prime)], label="Eq_prime (pu)")
plt.plot(t, y[:, problem.get_var_idx(Ed_prime)], label="Ed_prime (pu)")
plt.plot(t, y[:, problem.get_var_idx(Psiq_prime)], label="Eq_2prime (pu)")
plt.plot(t, y[:, problem.get_var_idx(Psid_prime)], label="Ed_2prime (pu)")

plt.plot(t, y[:, problem.get_var_idx(Ed1)], label="Ed1 (pu)")
plt.plot(t, y[:, problem.get_var_idx(Eq1)], label="Eq1 (pu)")
plt.legend(loc='upper right', ncol=2)
plt.xlabel("Time (s)")
plt.ylabel("Values (pu)")
plt.xlim([0, xlim])
# plt.ylim([0.85, 1.15])
plt.grid(True)
plt.tight_layout()
plt.show()

# Generator state variables
plt.plot(t, y[:, problem.get_var_idx(u_gov1)], label="u_gov1 (pu)")
plt.plot(t, y[:, problem.get_var_idx(y_subexciter)], label="y_subexciter (pu)")
plt.plot(t, y[:, problem.get_var_idx(Efe)], label="Efe (pu)")
plt.plot(t, y[:, problem.get_var_idx(y_exciter1)], label="y_exciter1 (pu)")
plt.plot(t, y[:, problem.get_var_idx(y_exciter4)], label="y_exciter4 (pu)")

plt.legend(loc='upper right', ncol=2)
plt.xlabel("Time (s)")
plt.ylabel("Values (pu)")
plt.xlim([0, xlim])
# plt.ylim([0.85, 1.15])
plt.grid(True)
plt.tight_layout()
plt.show()
