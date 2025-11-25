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
load_634 = gce.Load(G1=0.7,
                    B1=0.5,
                    G2=0.6,
                    B2=0.45,
                    G3=0.5,
                    B3=0.4,
                    name='Original')
load_634.conn = ShuntConnectionType.FloatingStar
grid.add_load(bus=bus_634, api_obj=load_634)

load_634 = gce.Load(G1=0.3,
                    B1=0.3,
                    G2=0.2,
                    B2=0.2,
                    G3=0.1,
                    B3=0.1,
                    name='Half')
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