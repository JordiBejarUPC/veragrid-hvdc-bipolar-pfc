import VeraGridEngine.api as vge
from VeraGridEngine import ShuntConnectionType, SolverType
import numpy as np

logger = vge.Logger()
grid = vge.MultiCircuit()

# -----------------------------------------------------------------------------------------------------------------
# Buses
# -----------------------------------------------------------------------------------------------------------------
bus_slack = vge.Bus(name='Slack Bus ABC', xpos=0, ypos=0)
bus_slack.is_slack = True
grid.add_bus(obj=bus_slack)

bus_middle = vge.Bus(name='Middle Bus CB', xpos=1000, ypos=0)
grid.add_bus(obj=bus_middle)

bus_load = vge.Bus(name='Load Bus CB', xpos=1000, ypos=0)
grid.add_bus(obj=bus_load)

# -----------------------------------------------------------------------------------------------------------------
# Generator
# -----------------------------------------------------------------------------------------------------------------
gen = vge.Generator()
grid.add_generator(bus=bus_slack, api_obj=gen)

# ----------------------------------------------------------------------------------------------------------------------
# Load
# ----------------------------------------------------------------------------------------------------------------------
load = vge.Load(P1=1.0,
                Q1=0.5,
                P2=1.0,
                Q2=0.5,
                P3=1.0,
                Q3=0.5)
load.conn = ShuntConnectionType.Delta
grid.add_load(bus=bus_load, api_obj=load)

# -----------------------------------------------------------------------------------------------------------------
# Lines
# -----------------------------------------------------------------------------------------------------------------
z_abc = np.array([
    [0.3 + 1j * 1.0, 0.1 + 1j * 0.4, 0.1 + 1j * 0.4],
    [0.1 + 1j * 0.4, 0.3 + 1j * 1.0, 0.1 + 1j * 0.4],
    [0.1 + 1j * 0.4, 0.1 + 1j * 0.4, 0.3 + 1j * 1.0]
], dtype=complex)  # Ω/km

y_abc = np.array([
    [1j * 6.0, -1j * 1.0, -1j * 1.0],
    [-1j * 1.0, 1j * 6.0, -1j * 1.0],
    [-1j * 1.0, -1j * 1.0, 1j * 6.0]
], dtype=complex) / (10 ** 6)  # S/km

configuration_abc = vge.create_known_abc_overhead_template(name='Three-phase line',
                                                           z_nabc=z_abc,
                                                           ysh_nabc=y_abc,
                                                           phases=np.array([1, 2, 3]),
                                                           Vnom=10.0)
grid.add_overhead_line(configuration_abc)

line_3ph = vge.Line(bus_from=bus_slack,
                    bus_to=bus_middle)
line_3ph.apply_template(configuration_abc, grid.Sbase, grid.fBase, logger)
grid.add_line(obj=line_3ph)

z_cb = np.array([
    [0.3 + 1j * 1.0, 0.1 + 1j * 0.4],
    [0.1 + 1j * 0.4, 0.3 + 1j * 1.0]
], dtype=complex)  # Ω/km

y_cb = np.array([
    [1j * 6.0, -1j * 1.0],
    [-1j * 1.0, 1j * 6.0]
], dtype=complex) / (10 ** 6)  # S/km

configuration_cb = vge.create_known_abc_overhead_template(name='Two-phase line',
                                                          z_nabc=z_cb,
                                                          ysh_nabc=y_cb,
                                                          phases=np.array([2, 3]),
                                                          Vnom=10.0)
grid.add_overhead_line(configuration_cb)

line_2ph = vge.Line(bus_from=bus_middle,
                    bus_to=bus_load)
line_2ph.apply_template(configuration_cb, grid.Sbase, grid.fBase, logger)
grid.add_line(obj=line_2ph)

# -----------------------------------------------------------------------------------------------------------------
# Power Flow
# -----------------------------------------------------------------------------------------------------------------
res = vge.power_flow3ph(grid=grid, options=vge.PowerFlowOptions(solver_type=SolverType.NR,
                                                                retry_with_other_methods=False))
print(res.get_voltage_3ph_df())