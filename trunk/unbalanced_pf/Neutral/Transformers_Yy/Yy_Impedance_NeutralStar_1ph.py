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
gen = gce.Generator()
grid.add_generator(bus = bus_632, api_obj = gen)

bus_634 = gce.Bus(name='Bus634', Vnom=0.48, xpos=200*5, ypos=0)
grid.add_bus(obj=bus_634)

bus_636 = gce.Bus(name='Bus636', Vnom=0.48, xpos=400*5, ypos=0)
grid.add_bus(obj=bus_636)

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
XFM_1.phases = np.array([1, 2, 3])
grid.add_transformer2w(XFM_1)

# ----------------------------------------------------------------------------------------------------------------------
# Line
# ----------------------------------------------------------------------------------------------------------------------
z_nabc = np.array([
    [0.2735 + 1j*0.8143, 0.0173 + 1j*0.0509, 0.0173 + 1j*0.0509, 0.0173 + 1j*0.0509],
    [0.0173 + 1j*0.0509, 0.3465 + 1j*1.0179, 0.1560 + 1j*0.5017, 0.1580 + 1j*0.4236],
    [0.0173 + 1j*0.0509, 0.1560 + 1j*0.5017, 0.3375 + 1j*1.0478, 0.1535 + 1j*0.3849],
    [0.0173 + 1j*0.0509, 0.1580 + 1j*0.4236, 0.1535 + 1j*0.3849, 0.3414 + 1j*1.0348]
], dtype=complex) / 1.60934  # Ω/km

y_nabc = np.array([
    [1j*6.1541, -1j*1.8918, -1j*2.0022, -1j*2.2602],
    [-1j*1.8918, 1j*6.2998, -1j*1.9958, -1j*1.2595],
    [-1j*2.0022, -1j*1.9958, 1j*5.9597, -1j*0.7417],
    [-1j*2.2602, -1j*1.2595, -1j*0.7417, 1j*5.6386]
], dtype=complex) / (10**6) / 1.60934  # S/km


configuration = gce.create_known_abc_overhead_template(name='4 wire line',
                                                       z_nabc=z_nabc,
                                                       ysh_nabc=y_nabc,
                                                       phases=np.array([0, 1, 2, 3]),
                                                       Vnom=4.16,
                                                       frequency=60)
grid.add_overhead_line(configuration)

line = gce.Line(bus_from=bus_634,
                bus_to=bus_636,
                length=100 * 0.0003048)
line.apply_template(configuration, grid.Sbase, grid.fBase, logger)
grid.add_line(obj=line)

# ----------------------------------------------------------------------------------------------------------------------
# Load
# ----------------------------------------------------------------------------------------------------------------------
load_636 = gce.Load(G1=0.3,
                    B1=0.3)
load_636.conn = ShuntConnectionType.NeutralStar
grid.add_load(bus=bus_636, api_obj=load_636)

# ----------------------------------------------------------------------------------------------------------------------
# Run power flow
# ----------------------------------------------------------------------------------------------------------------------
res = gce.power_flow3ph(grid=grid, options=gce.PowerFlowOptions(solver_type=SolverType.NR,
                                                             retry_with_other_methods=False))

# ----------------------------------------------------------------------------------------------------------------------
# Show the results
# ----------------------------------------------------------------------------------------------------------------------
pd.set_option("display.float_format", "{:.5f}".format)

print()
print(res.get_voltage_3ph_df())
print()
print(res.get_current_3ph_df())

print("\nConverged? ", res.converged)
print("Iterations: ", res.iterations)

# gce.save_file(grid=grid, filename='transformer_neutral.veragrid')

print(res.voltage_N)
print(res.voltage_A)
print(res.voltage_B)
print(res.voltage_C)