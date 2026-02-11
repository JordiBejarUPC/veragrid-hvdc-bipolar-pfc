import VeraGridEngine.api as vge
import numpy as np

logger = vge.Logger()
grid = vge.MultiCircuit()
grid.fBase = 60

# ----------------------------------------------------------------------------------------------------------------------
# Buses
# ----------------------------------------------------------------------------------------------------------------------
bus_slack = vge.Bus(name='Slack', Vnom=4.16, xpos=0, ypos=0)
bus_slack.is_slack = True
grid.add_bus(obj=bus_slack)
gen = vge.Generator()
grid.add_generator(bus=bus_slack, api_obj=gen)

bus_load = vge.Bus(name='Load', Vnom=4.16, xpos=400 * 5, ypos=0)
grid.add_bus(obj=bus_load)

# ----------------------------------------------------------------------------------------------------------------------
# Line
# ----------------------------------------------------------------------------------------------------------------------
Zbase = (4.16 * 4.16) / 100
z_nabc = np.array([
    [1j * (1 / 1), 1j * 0.0, 1j * 0.0, 1j * 0.0],
    [1j * 0.0, 1j * (1 / 2), 1j * 0.0, 1j * 0.0],
    [1j * 0.0, 1j * 0.0, 1j * (1 / 0.001), 1j * 0.0],
    [1j * 0.0, 1j * 0.0, 1j * 0.0, 1j * (1 / 3)]
], dtype=complex) * Zbase

Ybase = 1 / Zbase
y_nabc = np.array([
    [1j * 1.0, 0.0, 0.0, 0.0],
    [0.0, 1j * 2.0, 0.0, 0.0],
    [0.0, 0.0, 1j * 0.001, 0.0],
    [0.0, 0.0, 0.0, 1j * 3.0]
], dtype=complex) / 1e6 * Ybase

configuration = vge.create_known_abc_overhead_template(name='4 wire line',
                                                       z_nabc=z_nabc,
                                                       ysh_nabc=y_nabc,
                                                       phases=np.array([1, 2, 0, 3]),
                                                       Vnom=4.16,
                                                       frequency=60)
grid.add_overhead_line(configuration)

line = vge.Line(bus_from=bus_slack,
                bus_to=bus_load)
line.apply_template(configuration, grid.Sbase, grid.fBase, logger)
grid.add_line(obj=line)


ysh_ref = np.array([
    [1j * 0.001, 0.0, 0.0, 0.0],
    [0.0, 1j * 1, 0.0, 0.0],
    [0.0, 0.0, 1j * 2, 0.0],
    [0.0, 0.0, 0.0, 1j * 3]
], dtype=complex)

print(line.ys.values)
print(line.ysh.values)