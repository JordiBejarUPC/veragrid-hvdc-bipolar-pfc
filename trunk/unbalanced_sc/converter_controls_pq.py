import VeraGridEngine.api as vge
from VeraGridEngine.enumerations import ConverterControlType

logger = vge.Logger()
grid = vge.MultiCircuit()

# ----------------------------------------------------------------------------------------------------------------------
#   Buses
# ----------------------------------------------------------------------------------------------------------------------
bus_dc = vge.Bus(name='Bus DC', xpos=0, ypos=0, is_dc=True)
grid.add_bus(obj=bus_dc)

bus_ac = vge.Bus(name='Bus AC', xpos=0, ypos=200)
grid.add_bus(obj=bus_ac)

bus_slack = vge.Bus(name='Bus Slack', xpos=-200, ypos=400, is_slack=True)
grid.add_bus(obj=bus_slack)

bus_pq = vge.Bus(name='Bus PQ', xpos=200, ypos=400)
grid.add_bus(obj=bus_pq)

# ----------------------------------------------------------------------------------------------------------------------
#   Lines
# ----------------------------------------------------------------------------------------------------------------------
line_slack_ac = vge.Line(name='Slack - AC', bus_from=bus_slack, bus_to=bus_ac, r=0.1, x=1, rate=20.0)
grid.add_line(line_slack_ac)

line_slack_pq = vge.Line(name='Slack - PQ', bus_from=bus_slack, bus_to=bus_pq, r=0.1, x=1, rate=20.0)
grid.add_line(line_slack_pq)

line_ac_pq = vge.Line(name='AC - PQ', bus_from=bus_ac, bus_to=bus_pq, r=0.1, x=1, rate=20.0)
grid.add_line(line_ac_pq)

# ----------------------------------------------------------------------------------------------------------------------
#   VSC
# ----------------------------------------------------------------------------------------------------------------------
vsc = vge.VSC(bus_from=bus_dc,
              bus_to=bus_ac,
              rate=20.0,
              control1=ConverterControlType.Pac,
              control2=ConverterControlType.Qac,
              control1_val=10.0,
              control2_val=5.0)
grid.add_vsc(vsc)

# ----------------------------------------------------------------------------------------------------------------------
#   Load
# ----------------------------------------------------------------------------------------------------------------------
load = vge.Load(P=20.0, Q=10.0)
grid.add_load(bus_pq, load)

# ----------------------------------------------------------------------------------------------------------------------
#   Generators
# ----------------------------------------------------------------------------------------------------------------------
generator_slack = vge.Generator()
grid.add_generator(bus_slack, generator_slack)

generator_dc = vge.Generator()
grid.add_generator(bus_dc, generator_dc)

# ----------------------------------------------------------------------------------------------------------------------
#   Save Grid
# ----------------------------------------------------------------------------------------------------------------------
vge.save_file(grid=grid, filename='converter_controls_pq.veragrid')