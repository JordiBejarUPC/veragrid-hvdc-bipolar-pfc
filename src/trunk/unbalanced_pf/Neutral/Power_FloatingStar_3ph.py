import VeraGridEngine.api as gce
from VeraGridEngine import WindingType, ShuntConnectionType, SolverType
import numpy as np
import pandas as pd

logger = gce.Logger()

grid = gce.MultiCircuit()
grid.fBase = 60

# ----------------------------------------------------------------------------------------------------------------------
# Buses
# ----------------------------------------------------------------------------------------------------------------------
bus_632 = gce.Bus(name='Bus632', Vnom=4.16, xpos=0, ypos=0)
bus_632.is_slack = True
grid.add_bus(obj=bus_632)
gen = gce.Generator(vset = 1.0)
grid.add_generator(bus = bus_632, api_obj = gen)

bus_634 = gce.Bus(name='Bus634', Vnom=0.48, xpos=200*5, ypos=0)
grid.add_bus(obj=bus_634)

# ----------------------------------------------------------------------------------------------------------------------
# Load
# ----------------------------------------------------------------------------------------------------------------------
load_634 = gce.Load(P1=0.3,
                    Q1=0.3,
                    P2=0.2,
                    Q2=0.2,
                    P3=0.1,
                    Q3=0.1)
load_634.conn = ShuntConnectionType.FloatingStar
grid.add_load(bus=bus_634, api_obj=load_634)

# ----------------------------------------------------------------------------------------------------------------------
# Transformer
# ----------------------------------------------------------------------------------------------------------------------
XFM_1 = gce.Transformer2W(name='XFM-1',
                          bus_from=bus_632,
                          bus_to=bus_634,
                          HV=4.16,
                          LV=0.48,
                          nominal_power=0.5,
                          rate=0.5,
                          r=1.1*2,
                          x=2*2)
XFM_1.conn_f = WindingType.GroundedStar
XFM_1.conn_t = WindingType.GroundedStar
grid.add_transformer2w(XFM_1)

# ----------------------------------------------------------------------------------------------------------------------
# Run power flow
# ----------------------------------------------------------------------------------------------------------------------
res = gce.power_flow(grid=grid, options=gce.PowerFlowOptions(three_phase_unbalanced=True,
                                                             solver_type=SolverType.NR,
                                                             retry_with_other_methods=False))

# ----------------------------------------------------------------------------------------------------------------------
# Show the results
# ----------------------------------------------------------------------------------------------------------------------
pd.set_option("display.float_format", "{:.5f}".format)

print()
print(res.get_voltage_3ph_df())
print()
print(res.get_load_neutral_voltage_df())

print("\nConverged? ", res.converged)
print("\nIterations: ", res.iterations)

# print()
# print(res.load_Vn)
# print()
# print(res.voltage_A)
# print()
# print(res.voltage_B)
# print()
# print(res.voltage_C)

print("\nSpecified Power Modules:")
Sspec = np.zeros(3)
Sspec[0] = abs(0.7 + 0.5j) / (100/3)
Sspec[1] = abs(0.6 + 0.45j) / (100/3)
Sspec[2] = abs(0.5 + 0.4j) / (100/3)
print(Sspec)

print("\nPower Modules at VeraGrid UI*:")
Svg = np.zeros(3)
Svg[0] = abs(np.conj(res.It_A[0]) * (res.voltage_A[1] - 0.4366946443796176 *np.exp(1j * -83.64411053109009 * np.pi/180)))
Svg[1] = abs(np.conj(res.It_B[0]) * (res.voltage_B[1] - 0.4366946443796176 *np.exp(1j * -83.64411053109009 * np.pi/180)))
Svg[2] = abs(np.conj(res.It_C[0]) * (res.voltage_C[1] - 0.4366946443796176 *np.exp(1j * -83.64411053109009 * np.pi/180)))
print(Svg)

print('\nRatio Sspec/Svg')
Sratio = Sspec / Svg
print(Sratio)

print("\nPower Modules at VeraGrid:")
Svg = np.zeros(3)
Svg[0] = abs(res.St_A[0]) / (100/3)
Svg[1] = abs(res.St_B[0]) / (100/3)
Svg[2] = abs(res.St_C[0]) / (100/3)
print(Svg)

# print('\nRatio Sspec/Svg')
# Sratio = Sspec / Svg
# print(Sratio)

print("\nSum of Currents at VeraGrid:")
Ivg_a = res.It_A
Ivg_b = res.It_B
Ivg_c = res.It_C
print(Ivg_a+Ivg_b+Ivg_c)