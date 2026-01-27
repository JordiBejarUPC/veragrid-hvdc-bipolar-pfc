import VeraGridEngine.api as gce
import numpy as np
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Devices.Substation.bus import Bus
from VeraGridEngine.Devices.Injections.load import Load
from VeraGridEngine.Devices.Injections.generator import Generator
from VeraGridEngine.Devices.Branches.line import Line

from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowOptions
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver_3ph import PowerFlowDriver3Ph

grid = MultiCircuit()

Sbase  =160 #MVA
# Vbase = 15/np.sqrt(3) #kV
Vbase = 15 #kV

grid.Sbase = Sbase #*1e6 # MVA

bus1 = Bus(name="Bus1", Vnom=Vbase, is_slack= True)
bus1.ph_n = False
bus1.ph_a = True
bus1.ph_b = True
bus1.ph_c = True

bus2 = Bus(name="Bus2", Vnom=Vbase)
bus2.ph_n = False
bus2.ph_a = True
bus2.ph_b = True
bus2.ph_c = True

l1 = 10 # km
line0 = Line(name="line 1-2", bus_from=bus1, bus_to=bus2, rate = 300, length= l1)
tower = gce.OverheadLineType(name="Tower", Vnom = Vbase)

wire = gce.Wire(name="Panther 30/7 ACSR",
                diameter=21.0,
                diameter_internal=9.0,
                is_tube=True,
                r=0.1363,
                max_current=1)
tower.add_wire_relationship(wire=wire, xpos= -12.65, ypos= 27.5, phase=1)
tower.add_wire_relationship(wire=wire, xpos= 0, ypos= 27.5, phase=2)
tower.add_wire_relationship(wire=wire, xpos= 12.65, ypos= 27.5, phase=3)
tower.compute()

line0.apply_template(tower, grid.Sbase, grid.fBase)

gen1 = Generator(name="Gen1",freq = 50, Snom=grid.Sbase)

P = 10
load1 = Load(name="load1", P1 =P/3 , P2 =P/3 , P3 =P/3, Q1= 0.0, Q2= 0.0, Q3= 0.0) # R in p.u.2.75

grid.add_bus(bus1)
grid.add_bus(bus2)
grid.add_line(line0)
grid.add_generator(bus=bus1, api_obj=gen1)

grid.add_load(bus=bus2, api_obj=load1)

pf_options = PowerFlowOptions(
    solver_type=gce.SolverType.NR,
    retry_with_other_methods=False,
    verbose=True,
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
    initialize_angles=True,
    generate_report=False,
)
power_flow = PowerFlowDriver3Ph(grid, pf_options)
power_flow.run()
res = power_flow.results
print("res.m (branch number)= ", res.m)
print("res.n (bus number)= ", res.n)
print("res.n_gen = ", res.n_gen)
print("res.n_load ", res.n_load)
print("res.bus_names = ", res.bus_names)
print("res.branch_names = ", res.branch_names)
print("res.load_names = ", res.load_names)
print("res.bus_types = ", res.bus_types)
print("res.voltage_A = ", res.voltage_A)
print("res.voltage_B = ", res.voltage_B)
print("res.voltage_C = ", res.voltage_C)
print("res.Sbus_A = ", res.Sbus_A)
print("res.Sbus_B = ", res.Sbus_B)
print("res.Sbus_C = ", res.Sbus_C)
print("res.Sf_A = ", res.Sf_A)
print("res.Sf_B = ", res.Sf_B)
print("res.Sf_C = ", res.Sf_C)
print("res.St_A = ", res.St_A)
print("res.St_B = ", res.St_B)
print("res.St_C = ", res.St_C)
print("res.If_A = ", res.If_A)
print("res.If_B = ", res.If_B)
print("res.If_C = ", res.If_C)
print("res.It_A = ", res.It_A)
print("res.It_B = ", res.It_B)
print("res.It_C = ", res.It_C)

print(f"Converged: {res.converged}")
print(f"res:{res}")