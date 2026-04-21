import VeraGridEngine.api as vge
from VeraGridEngine import ShuntConnectionType, SolverType
import numpy as np

logger = vge.Logger()
grid = vge.MultiCircuit()

# ----------------------------------------------------------------------------------------------------------------------
# Buses
# ----------------------------------------------------------------------------------------------------------------------
bus_slack = vge.Bus(name='Slack ABC', xpos=0, ypos=0)
bus_slack.is_slack = True
grid.add_bus(obj=bus_slack)

bus_3ph = vge.Bus(name='Three-phase ABC', xpos=500, ypos=0)
grid.add_bus(obj=bus_3ph)

bus_2ph = vge.Bus(name='Two-phase AB', xpos=1000, ypos=0)
grid.add_bus(obj=bus_2ph)

bus_slack_2 = vge.Bus(name='Slack ABC 2', xpos=0, ypos=0)
bus_slack_2.is_slack = True
grid.add_bus(obj=bus_slack_2)

bus_3ph_2 = vge.Bus(name='Three-phase ABC 2', xpos=500, ypos=0)
grid.add_bus(obj=bus_3ph_2)

bus_2ph_2 = vge.Bus(name='Two-phase AB 2', xpos=1000, ypos=0)
grid.add_bus(obj=bus_2ph_2)

# ----------------------------------------------------------------------------------------------------------------------
# Generator
# ----------------------------------------------------------------------------------------------------------------------
gen = vge.Generator()
grid.add_generator(bus=bus_slack, api_obj=gen)

gen_2 = vge.Generator()
grid.add_generator(bus=bus_slack_2, api_obj=gen_2)

# ----------------------------------------------------------------------------------------------------------------------
# Loads
# ----------------------------------------------------------------------------------------------------------------------
load_3ph = vge.Load(P1=1.0,
                    Q1=0.5,
                    P2=1.0,
                    Q2=0.5,
                    P3=1.0,
                    Q3=0.5)
load_3ph.conn = ShuntConnectionType.GroundedStar
grid.add_load(bus=bus_3ph, api_obj=load_3ph)

load_2ph = vge.Load(P1=1.0,
                    Q1=0.5)
load_2ph.conn = ShuntConnectionType.Delta
grid.add_load(bus=bus_2ph, api_obj=load_2ph)

load_3ph_2 = vge.Load(P1=1.0,
                      Q1=0.5,
                      P2=1.0,
                      Q2=0.5,
                      P3=1.0,
                      Q3=0.5)
load_3ph_2.conn = ShuntConnectionType.GroundedStar
grid.add_load(bus=bus_3ph_2, api_obj=load_3ph_2)

load_2ph_2 = vge.Load(P1=1.0,
                      Q1=0.5)
load_2ph_2.conn = ShuntConnectionType.Delta
grid.add_load(bus=bus_2ph_2, api_obj=load_2ph_2)

# ----------------------------------------------------------------------------------------------------------------------
# Lines
# ----------------------------------------------------------------------------------------------------------------------
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
                    bus_to=bus_3ph)
line_3ph.apply_template(configuration_abc, grid.Sbase, grid.fBase, logger)
grid.add_line(obj=line_3ph)

line_3ph_2 = vge.Line(bus_from=bus_slack_2,
                      bus_to=bus_3ph_2)
line_3ph_2.apply_template(configuration_abc, grid.Sbase, grid.fBase, logger)
grid.add_line(obj=line_3ph_2)

z_ab = np.array([
    [0.3 + 1j * 1.0, 0.1 + 1j * 0.4],
    [0.1 + 1j * 0.4, 0.3 + 1j * 1.0]
], dtype=complex)  # Ω/km

y_ab = np.array([
    [1j * 6.0, -1j * 1.0],
    [-1j * 1.0, 1j * 6.0]
], dtype=complex) / (10 ** 6)  # S/km

configuration_ab = vge.create_known_abc_overhead_template(name='Two-phase line',
                                                           z_nabc=z_ab,
                                                           ysh_nabc=y_ab,
                                                           phases=np.array([1, 2]),
                                                           Vnom=10.0)
grid.add_overhead_line(configuration_ab)

line_2ph = vge.Line(bus_from=bus_3ph,
                    bus_to=bus_2ph)
line_2ph.apply_template(configuration_ab, grid.Sbase, grid.fBase, logger)
grid.add_line(obj=line_2ph)

line_2ph_2 = vge.Line(bus_from=bus_3ph_2,
                      bus_to=bus_2ph_2)
line_2ph_2.apply_template(configuration_ab, grid.Sbase, grid.fBase, logger)
grid.add_line(obj=line_2ph_2)

# ----------------------------------------------------------------------------------------------------------------------
# Run power flow
# ----------------------------------------------------------------------------------------------------------------------
vge.save_file(grid, 'unconnected_phases.veragrid')

res = vge.power_flow3ph(grid=grid, options=vge.PowerFlowOptions(solver_type=SolverType.NR,
                                                                retry_with_other_methods=False))

print(res.get_voltage_3ph_df())
