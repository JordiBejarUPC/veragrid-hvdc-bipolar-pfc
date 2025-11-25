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
bus_632 = gce.Bus(name='632', Vnom=4.16, xpos=0, ypos=0)
bus_632.is_slack = True
grid.add_bus(obj=bus_632)
gen = gce.Generator(vset = 1.0)
grid.add_generator(bus = bus_632, api_obj = gen)

bus_634 = gce.Bus(name='634', Vnom=0.48, xpos=200*5, ypos=0)
grid.add_bus(obj=bus_634)

# ----------------------------------------------------------------------------------------------------------------------
# Load
# ----------------------------------------------------------------------------------------------------------------------
load_634 = gce.Load(G1=0.7,
                    B1=0.5,
                    G2=0.6,
                    B2=0.45,
                    G3=0.5,
                    B3=0.4)
load_634.conn = ShuntConnectionType.GroundedStar
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
# Line
# ----------------------------------------------------------------------------------------------------------------------
# z_601 = np.array([
#     [0.3465 + 1j * 1.0179, 0.1560 + 1j * 0.5017, 0.1580 + 1j * 0.4236],
#     [0.1560 + 1j * 0.5017, 0.3375 + 1j * 1.0478, 0.1535 + 1j * 0.3849],
#     [0.1580 + 1j * 0.4236, 0.1535 + 1j * 0.3849, 0.3414 + 1j * 1.0348]
# ], dtype=complex) / 1.60934
# y_601 = np.array([
#     [1j * 6.2998, 1j * -1.9958, 1j * -1.2595],
#     [1j * -1.9958, 1j * 5.9597, 1j * -0.7417],
#     [1j * -1.2595, 1j * -0.7417, 1j * 5.6386]
# ], dtype=complex) / 10**6 / 1.60934
#
# config_601 = gce.create_known_abc_overhead_template(name='Config. 601',
#                                                     z_abcn=z_601,
#                                                     ysh_abcn=y_601,
#                                                     phases=np.array([1, 2, 3]),
#                                                     Vnom=4.16,
#                                                     frequency=60)
# grid.add_overhead_line(config_601)
#
# line_632_671 = gce.Line(bus_from=bus_632,
#                         bus_to=bus_634,
#                         length= 2000 * 0.0003048)
# line_632_671.apply_template(config_601, grid.Sbase, grid.fBase, logger)
# grid.add_line(obj=line_632_671)

# ----------------------------------------------------------------------------------------------------------------------
# Run power flow
# ----------------------------------------------------------------------------------------------------------------------
res = gce.power_flow(grid=grid, options=gce.PowerFlowOptions(three_phase_unbalanced=True,
                                                             solver_type=SolverType.NR))

# ----------------------------------------------------------------------------------------------------------------------
# Show the results
# ----------------------------------------------------------------------------------------------------------------------
pd.set_option("display.float_format", "{:.5f}".format)

print(res.get_voltage_3ph_df())

print("\nConverged? ", res.converged)
print("\nIterations: ", res.iterations)