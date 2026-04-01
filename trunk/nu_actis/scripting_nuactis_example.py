# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0


import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'src')))


from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Simulations.Rms.problems.rms_problem_dae import RmsProblemDae
from VeraGridEngine.Simulations.Rms.rms_options import RmsOptions
from VeraGridEngine.Simulations.Rms.rms_results import RmsResults
from VeraGridEngine.Simulations.Rms.numerical.back_euler_fx import BackEulerImplicitIntegration
from VeraGridEngine.Templates.Rms.line_rms_template import get_line_rms_template
from VeraGridEngine.Templates.Rms.load_rms_template import get_load_rms_template
from VeraGridEngine.Templates.Rms.genqec_exc_gov_sat_template import get_complete_generator_template_rms
from VeraGridEngine.Templates.Rms.bus_rms_template import initialize_bus_rms
from VeraGridEngine.Templates.templates_common_functions import set_rms_model
from VeraGridEngine.Devices.Aggregation.rms_events_group import RmsEventsGroup

from VeraGridEngine.enumerations import VarPowerFlowRefferenceType, DynamicIntegrationMethod, RmsInitializationMethod, ConverterControlType
from VeraGridEngine.Devices.Aggregation import RmsEvent
import VeraGridEngine.api as gce

###########################################################################################################################
# Build VeraGrid object
###########################################################################################################################


def find_name_in_block(name: str, block: Block):
    for var in block.algebraic_vars + block.state_vars + list(block.event_dict.keys()):
        if name == var.name:
            return var

    for mdl in block.children:
        res = find_name_in_block(name, mdl)
        if res is not None:
            return res


#####################################################################################
#                    Grid
#####################################################################################

grid = gce.MultiCircuit(Sbase=100, fbase=50.0)

#####################################################################################
#                    Devices
#####################################################################################

# Buses
bus1 = gce.Bus(name="Bus1", Vnom=400, is_slack=True)
bus2 = gce.Bus(name="Bus2", Vnom=400)
bus2_1 = gce.Bus(name="Bus2_1", Vnom=520) # between trafo and vsc
bus3 = gce.Bus(name="Bus3", Vnom=1013.5, is_dc = True)
bus4 = gce.Bus(name="Bus4", Vnom=1013.5, is_dc = True)
bus5_1 = gce.Bus(name="Bus5_1", Vnom=520) # between trafo and vsc
bus5 = gce.Bus(name="Bus5", Vnom=400)
bus6 = gce.Bus(name="Bus6", Vnom=400)

grid.add_bus(bus1)
grid.add_bus(bus2)
grid.add_bus(bus2_1)
grid.add_bus(bus3)
grid.add_bus(bus4)
grid.add_bus(bus5_1)
grid.add_bus(bus5)
grid.add_bus(bus6)

for bus in grid.buses:
    initialize_bus_rms(bus, vf=grid.rms_var_factory)

# external grid
generatorA: gce.Generator = gce.Generator(
        name="Gen_Thev",
        vset=1.0,
        Snom=grid.Sbase,
        freq=50.0,
        r1=0.001,
        x1=0.3,
    )
grid.add_generator(bus1, generatorA)
generatorB: gce.Generator = gce.Generator(
        name="Gen_Thev",
        vset=1.0,
        Snom=grid.Sbase,
        freq=50.0,
        r1=0.001,
        x1=0.3,
    )
grid.add_generator(bus6, generatorB)

# Lines
lineA = gce.Line(name="line 1-2", bus_from=bus1, bus_to=bus2, r=0.029585798816568046, x=0.07100591715976332, b=0.03,
                 rate=900.0)
grid.add_line(lineA)
lineB = gce.Line(name="line 1-2", bus_from=bus5, bus_to=bus6, r=0.029585798816568046, x=0.07100591715976332, b=0.03,
                 rate=900.0)
grid.add_line(lineB)

# transformers
trafoA = gce.Line(name="line 1-2", bus_from=bus2, bus_to=bus2_1, r=0.029585798816568046, x=0.07100591715976332, b=0.03,
                 rate=900.0)
grid.add_line(trafoA)
trafoB = gce.Line(name="line 1-2", bus_from=bus5_1, bus_to=bus5, r=0.029585798816568046, x=0.07100591715976332, b=0.03,
                 rate=900.0)
grid.add_line(trafoB)

# VSC
p_transfer_mw = 30.0 # MW
q_transfer_mvar = 0.0 # MVAr
emt_control1 = ConverterControlType.Pdc
emt_control2 = ConverterControlType.Qac
vsc_master = gce.VSC(
    name='VSC',
    bus_from=bus3,  # DC side
    bus_to=bus2_1,    # AC side
    rate=100.0,
    control1=ConverterControlType.Qac,
    control2=ConverterControlType.Vm_dc,
    control1_val=q_transfer_mvar,
    control2_val=1.0,
)
grid.add_vsc(vsc_master)

vsc_slave = gce.VSC(
    name='VSC',
    bus_from=bus4,  # DC side
    bus_to=bus5_1,    # AC side
    rate=100.0,
    control1=ConverterControlType.Qac,
    control2=ConverterControlType.Vm_dc,
    control1_val=q_transfer_mvar,
    control2_val=1.0,
)
grid.add_vsc(vsc_slave)

DCline = gce.DcLine(
    name= 'DC line',
    bus_from = bus3,
    bus_to = bus4,
    rate = 900,
    r=2.05
)
grid.add_dc_line(DCline)

######################################################################################################
# Build Rms models
######################################################################################################


# generator
# genA_mdl = get_complete_generator_template_rms(grid.rms_var_factory).block
# genB_mdl = get_complete_generator_template_rms(grid.rms_var_factory).block
#
# # line
# lineA_mdl = get_line_rms_template(grid.rms_var_factory).block
# lineB_mdl = get_line_rms_template(grid.rms_var_factory).block
# trafoA_mdl = get_line_rms_template(grid.rms_var_factory).block
# trafoB_mdl = get_line_rms_template(grid.rms_var_factory).block

# DC line
# DCline_mdl =

# VSC
# vsc_master_mdl =
# vsc_slave_mdl


######################################################################################################
# Add models to devices
######################################################################################################
#grids
# set_rms_model(device=generatorA, model=genA_mdl, var_factory= grid.rms_var_factory)
# set_rms_model(device=generatorB, model=genB_mdl, var_factory= grid.rms_var_factory)
#
# # lines
# set_rms_model(device=lineA, model=lineA_mdl, var_factory= grid.rms_var_factory)
# set_rms_model(device=lineB, model=lineB_mdl, var_factory= grid.rms_var_factory)
#
# #transformers
# set_rms_model(device=trafoA, model=trafoA_mdl, var_factory= grid.rms_var_factory)
# set_rms_model(device=trafoB, model=trafoB_mdl, var_factory= grid.rms_var_factory)

# DC line
# set_rms_model(device=DCline, model=DCline_mdl, var_factory= grid.rms_var_factory)

# VSC
# set_rms_model(device=vsc_master, model=vsc_master_mdl, var_factory= grid.rms_var_factory)
# set_rms_model(device=vsc_slave, model=vsc_slave_mdl, var_factory= grid.rms_var_factory)


######################################################################################################
# Power flow
######################################################################################################

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
events_group = RmsEventsGroup("simulation1")
problem.set_events_group(events_group)


solver = BackEulerImplicitIntegration(
    problem=problem,
    t0=0,
    t_end=options.simulation_time,
    h=options.time_step,
    max_iter=options.max_iter,
)

t, y, well_initialized, converged = solver.simulate()

