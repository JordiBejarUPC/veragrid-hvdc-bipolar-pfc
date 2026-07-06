import VeraGridEngine.api as vge
from VeraGridEngine import ShuntConnectionType, SolverType

logger = vge.Logger()
grid = vge.MultiCircuit()

# ----------------------------------------------------------------------------------------------------------------------
# Buses
# ----------------------------------------------------------------------------------------------------------------------
bus_slack = vge.Bus(name="Slack Bus")
bus_slack.is_slack = True
grid.add_bus(bus_slack)

bus_load = vge.Bus(name="Load Bus")
grid.add_bus(bus_load)

# ----------------------------------------------------------------------------------------------------------------------
# Generator
# ----------------------------------------------------------------------------------------------------------------------
gen = vge.Generator()
grid.add_generator(bus=bus_slack, api_obj=gen)

# ----------------------------------------------------------------------------------------------------------------------
# Loads
# ----------------------------------------------------------------------------------------------------------------------
P = 10.0
Q = 1.0
load = vge.Load(P1=P/3,
                Q1=Q/3,
                P2=P/3,
                Q2=Q/3,
                P3=P/3,
                Q3=Q/3)
load.conn = ShuntConnectionType.GroundedStar
grid.add_load(bus=bus_load, api_obj=load)

# ----------------------------------------------------------------------------------------------------------------------
# Lines
# ----------------------------------------------------------------------------------------------------------------------
tower = vge.OverheadLineType(name="Tower", Vnom=10.0)

wire = vge.Wire(name="Panther 30/7 ACSR",
                diameter=21.0,
                diameter_internal=9.0,
                is_tube=True,
                r=0.1363,
                max_current=1)

tower.add_wire_relationship(wire=wire, xpos=-12.65, ypos=27.5, phase=1)
tower.add_wire_relationship(wire=wire, xpos=0.0, ypos=27.5, phase=2)
tower.add_wire_relationship(wire=wire, xpos=12.65, ypos=27.5, phase=3)

tower.compute()

line = vge.Line(name='Line Slack-Load',
                bus_from=bus_slack,
                bus_to=bus_load,
                rate=900.0)
line.apply_template(tower, grid.Sbase, grid.fBase, logger)
grid.add_line(obj=line)


# ----------------------------------------------------------------------------------------------------------------------
# Run power flow
# ----------------------------------------------------------------------------------------------------------------------
res = vge.power_flow3ph(grid=grid, options=vge.PowerFlowOptions(solver_type=SolverType.NR,
                                                                retry_with_other_methods=False))

print(res.get_voltage_3ph_df())
print()
print(res.get_bus_df())
print()
print(res.get_branch_df())