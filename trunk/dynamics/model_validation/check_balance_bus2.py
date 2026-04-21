
import sys
import os
sys.path.insert(0, '/home/pablo/Desktop/eroots/VeraGrid/src')

import numpy as np
import VeraGridEngine.api as gce

# Grid instantiation
grid = gce.MultiCircuit(Sbase=100, fbase=50.0)

# Define buses
bus1 = gce.Bus(name='B1', Vnom=135, is_slack=True)
bus2 = gce.Bus(name='B2', Vnom=135)
bus3 = gce.Bus(name='B3', Vnom=100)

# Define AC lines
line12 = gce.Line(name="line 1-2", bus_from=bus1, bus_to=bus2, r=0.029585798816568046, x=0.07100591715976332, b=0.03,
                 rate=900.0)

# Define transformer type
trafo_type = gce.TransformerType(name='TransformerType',
                                 hv_nominal_voltage=135,
                                 lv_nominal_voltage=100,
                                 nominal_power=0.5,
                                 copper_losses=1.0,
                                 iron_losses=1e-20,
                                 no_load_current=1e-20,
                                 short_circuit_voltage=22.36067977)
grid.add_transformer_type(trafo_type)

trafo_1 = gce.Transformer2W(name='Transformer',
                            bus_from=bus2,
                            bus_to=bus3,
                            template=trafo_type)
# Define generators
gen1 = gce.Generator(name='Gen1', P=10.0, vset=1.00)

# Define loads
load1 = gce.Load(name='Load1', P=0.09999, Q=0.009999)

###############
# Add to the grid
grid.add_bus(bus1)
grid.add_bus(bus2) 
grid.add_bus(bus3)

grid.add_line(line12)
grid.add_generator(bus=bus1, api_obj=gen1)
grid.add_load(bus=bus3, api_obj=load1)
grid.add_transformer2w(trafo_1)

grid.apply_all_branch_types()

#########
pf_driver = gce.PowerFlowDriver(grid=grid)
pf_driver.run()
res = pf_driver.results

print(f"PF Converged: {res.converged}")
print(f"PF Error Norm: {res.error}")
print(f"PF Iterations: {res.iterations}")

line12_idx = list(res.branch_names).index(line12.name)
trafo_idx = list(res.branch_names).index(trafo_1.name)
bus2_idx = list(res.bus_names).index(bus2.name)

st_line = res.St[line12_idx]
sf_trafo = res.Sf[trafo_idx]
v2 = res.voltage[bus2_idx]
v2_mag = abs(v2)

# Expected shunt reactive power from line (b=0.03, half at each end)
# Q_shunt = V^2 * B_shunt
# Note: VeraGrid usually handles 'b' as the total susceptance, half at each end.
expected_q_shunt = (v2_mag**2) * (line12.B / 2.0)

print(f"Voltage at Bus 2: {v2_mag:.6f} p.u.")
print(f"Power from Line 1-2 leaving Bus 2 (St): {st_line}")
print(f"Power into Transformer leaving Bus 2 (Sf): {sf_trafo}")
print(f"Direct Balance (St + Sf): {st_line + sf_trafo}")
print(f"Expected Line Shunt Injection (approx -j*V^2*b/2): {-1j * expected_q_shunt}")
print(f"Balance check (St + Sf + Injection): {st_line + sf_trafo - 1j * expected_q_shunt}")
