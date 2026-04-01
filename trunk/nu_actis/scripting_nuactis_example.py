# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import os
import sys

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
src_root = os.path.join(repo_root, "src")
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)
if src_root not in sys.path:
    sys.path.insert(0, src_root)
from VeraGridEngine.Devices.Aggregation.rms_events_group import RmsEventsGroup
from VeraGridEngine.Simulations.Rms.numerical.back_euler_fx import BackEulerImplicitIntegration
from VeraGridEngine.Simulations.Rms.problems.rms_problem_dae import RmsProblemDae
from VeraGridEngine.Simulations.Rms.rms_options import RmsOptions
from VeraGridEngine.Templates.Rms.bus_rms_template import initialize_bus_rms
from VeraGridEngine.Templates.Rms.line_rms_template import get_dc_line_rms_template, get_line_rms_template
from VeraGridEngine.Templates.Rms.voltage_source_template import VoltageSourceBuild
from VeraGridEngine.Templates.Rms.vsc_gfl_dclinked import build_vsc_rms
from VeraGridEngine.Templates.templates_common_functions import set_rms_model
from VeraGridEngine.enumerations import DynamicIntegrationMethod, RmsInitializationMethod, ConverterControlType, VarPowerFlowRefferenceType
import VeraGridEngine.api as gce

from trunk.nu_actis.nuactis_master_pwm_template import build_trafo_master_block
from trunk.nu_actis.nuactis_slave_pwm_template import build_trafo_slave_block, connect_rms_vsc_to_buses


def dump_grid_topology(grid, label: str):
    print(f"\n[DEBUG] {label}")
    print(f"transformers2w order ({len(grid.get_transformers2w())}):")
    for i, t in enumerate(grid.get_transformers2w()):
        print(f"  [{i}] {t.name}: {t.idtag[:8]} {t.bus_from.name}->{t.bus_to.name}")

    print("branch iterator order add_vsc=False/add_hvdc=False/add_switch=True:")
    for i, br in enumerate(grid.get_branches_iter(add_vsc=False, add_hvdc=False, add_switch=True)):
        print(f"  [{i}] {type(br).__name__} | {br.name} | {br.idtag[:8]}")


grid = gce.MultiCircuit(Sbase=100, fbase=50.0)

# Buses
bus1 = gce.Bus(name="Bus1", Vnom=400, is_slack=True)
bus2 = gce.Bus(name="Bus2", Vnom=400)
bus2_1 = gce.Bus(name="Bus2_1", Vnom=520)
bus3 = gce.Bus(name="Bus3", Vnom=1013.5, is_dc=True)
bus4 = gce.Bus(name="Bus4", Vnom=1013.5, is_dc=True)
bus5_1 = gce.Bus(name="Bus5_1", Vnom=520)
bus5 = gce.Bus(name="Bus5", Vnom=400)
bus6 = gce.Bus(name="Bus6", Vnom=400, is_slack=True)

for bus in [bus1, bus2, bus2_1, bus3, bus4, bus5_1, bus5, bus6]:
    grid.add_bus(bus)

for bus in grid.buses:
    initialize_bus_rms(bus, vf=grid.rms_var_factory)

# External grids
generatorA = gce.Generator(name="Gen_Thev_A", vset=1.0, Snom=grid.Sbase, freq=50.0, r1=0.001, x1=0.3)
generatorB = gce.Generator(name="Gen_Thev_B", vset=1.0, Snom=grid.Sbase, freq=50.0, r1=0.001, x1=0.3)
grid.add_generator(bus1, generatorA)
grid.add_generator(bus6, generatorB)

# AC lines
lineA = gce.Line(name="L12", bus_from=bus1, bus_to=bus2, r=0.029585798816568046, x=0.07100591715976332, b=0.03, rate=900.0)
lineB = gce.Line(name="L56", bus_from=bus5, bus_to=bus6, r=0.029585798816568046, x=0.07100591715976332, b=0.03, rate=900.0)
grid.add_line(lineA)
grid.add_line(lineB)

# Transformers
trafoA = gce.Transformer2W(
    name="Trafo_2_2_1",
    bus_from=bus2,
    bus_to=bus2_1,
    HV=520.0,
    LV=400.0,
    nominal_power=900.0,
    r=0.005,
    x=0.12,
    rate=900.0,
    tap_module=1.0,
    tap_phase=0.0,
)
trafoB = gce.Transformer2W(
    name="Trafo_5_1_5",
    bus_from=bus5_1,
    bus_to=bus5,
    HV=520.0,
    LV=400.0,
    nominal_power=900.0,
    r=0.005,
    x=0.12,
    rate=900.0,
    tap_module=1.0,
    tap_phase=0.0,
)
grid.add_transformer2w(trafoB)

grid.add_transformer2w(trafoA)
dump_grid_topology(grid, "after adding trafoA and trafoB")

# VSCs
p_transfer_mw = 30.0
q_transfer_mvar = 0.0


vsc_slave = gce.VSC(
    name="VSC_slave",
    bus_from=bus4,
    bus_to=bus5_1,
    rate=100.0,
    control1=ConverterControlType.Qac,
    control2=ConverterControlType.Pac,
    control1_val=q_transfer_mvar,
    control2_val=p_transfer_mw,
)

vsc_master = gce.VSC(
    name="VSC_master",
    bus_from=bus3,
    bus_to=bus2_1,
    rate=100.0,
    control1=ConverterControlType.Qac,
    control2=ConverterControlType.Vm_dc,
    control1_val=q_transfer_mvar,
    control2_val=1.0,
)
grid.add_vsc(vsc_master)
grid.add_vsc(vsc_slave)

# DC line
dc_line = gce.DcLine(name="DC_line", bus_from=bus3, bus_to=bus4, rate=900.0, r=0.001)
grid.add_dc_line(dc_line)

# Build RMS models
genA_mdl = VoltageSourceBuild(grid.rms_var_factory, name=generatorA.name).block
genB_mdl = VoltageSourceBuild(grid.rms_var_factory, name=generatorB.name).block

lineA_mdl = get_line_rms_template(grid.rms_var_factory, name=lineA.name).block
lineB_mdl = get_line_rms_template(grid.rms_var_factory, name=lineB.name).block
dc_line_mdl = get_dc_line_rms_template(grid.rms_var_factory, name=dc_line.name).block

trafo_master_mdl = build_trafo_master_block(vfactory=grid.rms_var_factory, name=trafoA.name).block
trafo_slave_mdl = build_trafo_slave_block(vfactory=grid.rms_var_factory, name=trafoB.name).block

vsc_master_mdl = build_vsc_rms(vfactory=grid.rms_var_factory, name=vsc_master.name).block
vsc_slave_mdl = build_vsc_rms(vfactory=grid.rms_var_factory, name=vsc_slave.name).block

# Assign models
set_rms_model(device=generatorA, model=genA_mdl, var_factory=grid.rms_var_factory)
set_rms_model(device=generatorB, model=genB_mdl, var_factory=grid.rms_var_factory)
set_rms_model(device=lineA, model=lineA_mdl, var_factory=grid.rms_var_factory)
set_rms_model(device=lineB, model=lineB_mdl, var_factory=grid.rms_var_factory)

dc_line.rms_model = dc_line_mdl
trafoA.rms_model = trafo_master_mdl
trafoB.rms_model = trafo_slave_mdl
vsc_master.rms_model = vsc_master_mdl
vsc_slave.rms_model = vsc_slave_mdl

# Connect DC line to DC buses
dc_vm_f = dc_line.rms_model.external_mapping[VarPowerFlowRefferenceType.Vmf]
dc_vm_t = dc_line.rms_model.external_mapping[VarPowerFlowRefferenceType.Vmt]
bus3_vdc = bus3.rms_model.external_mapping[VarPowerFlowRefferenceType.Vdc]
bus4_vdc = bus4.rms_model.external_mapping[VarPowerFlowRefferenceType.Vdc]
dc_line.rms_model.connect([dc_vm_f, dc_vm_t], [bus3_vdc, bus4_vdc])

# Connect master/slave trafo-control models to buses
connect_rms_vsc_to_buses(
    vsc_model=trafoA.rms_model,
    controlled_bus_model=bus2_1.rms_model,
    grid_bus_model=bus2.rms_model,
    dc_bus_model=bus3.rms_model,
)
connect_rms_vsc_to_buses(
    vsc_model=trafoB.rms_model,
    controlled_bus_model=bus5_1.rms_model,
    grid_bus_model=bus5.rms_model,
    dc_bus_model=bus4.rms_model,
)

# Connect standalone VSC DC/link model to trafo-control outputs
for vsc_dev, trafo_model in [(vsc_master, trafoA.rms_model), (vsc_slave, trafoB.rms_model)]:
    im_trafo = trafo_model.external_mapping[VarPowerFlowRefferenceType.Im]
    pt_trafo = trafo_model.external_mapping[VarPowerFlowRefferenceType.Pt]

    vsc_dev.rms_model.connect(
        [vsc_dev.rms_model.in_vars[0], vsc_dev.rms_model.in_vars[1]],
        [im_trafo, pt_trafo],
    )


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
print(f"Converged? {res.converged}")
print(res.get_bus_df())
print(res.get_branch_df())

rms_options = RmsOptions(
    time_step=0.001,
    simulation_time=5,
    tolerance=1e-6,
    integration_method=DynamicIntegrationMethod.DaeBackEuler,
    initialization_method=RmsInitializationMethod.Explicit,
    use_init_values=False,
    max_iter=1000,
    verbose=0,
)

problem = RmsProblemDae(grid=grid, options=rms_options, pf_results=res)
problem.set_events_group(RmsEventsGroup("simulation1"))

solver = BackEulerImplicitIntegration(
    problem=problem,
    t0=0,
    t_end=rms_options.simulation_time,
    h=rms_options.time_step,
    max_iter=rms_options.max_iter,
)

t, y, well_initialized, converged = solver.simulate()
print("RMS simulation finished", well_initialized, converged, len(t))
