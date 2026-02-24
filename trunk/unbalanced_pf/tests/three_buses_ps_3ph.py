import VeraGridEngine.api as vge

grid = vge.MultiCircuit()

# ----------------------------------------------------------------------------------------------------------------------
# Buses
# ----------------------------------------------------------------------------------------------------------------------
bus_slack = vge.Bus(name='Slack', xpos=0, ypos=0)
bus_slack.is_slack = True
grid.add_bus(obj=bus_slack)

bus_pv = vge.Bus(name='PV', xpos=0, ypos=200)
grid.add_bus(obj=bus_pv)

bus_pq = vge.Bus(name='PQ', xpos=0, ypos=200)
grid.add_bus(obj=bus_pq)

# ----------------------------------------------------------------------------------------------------------------------
# Generators
# ----------------------------------------------------------------------------------------------------------------------
gen_slack = vge.Generator()
grid.add_generator(bus=bus_slack, api_obj=gen_slack)

gen_pv = vge.Generator(P=5, is_controlled=True)
grid.add_generator(bus=bus_pv, api_obj=gen_pv)

# ----------------------------------------------------------------------------------------------------------------------
# Line
# ----------------------------------------------------------------------------------------------------------------------
line_slack_pv = vge.Line(bus_from=bus_slack,
                         bus_to=bus_pv,
                         name='Slack-PV',
                         r=0.1,
                         x=1.0,
                         b=0.1)
grid.add_line(obj=line_slack_pv)

line_slack_pq = vge.Line(bus_from=bus_slack,
                         bus_to=bus_pq,
                         name='Slack-PQ',
                         r=0.1,
                         x=1.0,
                         b=0.1)
grid.add_line(obj=line_slack_pq)

line_pv_pq = vge.Line(bus_from=bus_pv,
                      bus_to=bus_pq,
                      name='PV-PQ',
                      r=0.1,
                      x=1.0,
                      b=0.1)
grid.add_line(obj=line_pv_pq)

# ----------------------------------------------------------------------------------------------------------------------
# Load
# ----------------------------------------------------------------------------------------------------------------------
load = vge.Load(P=10.0,
                Q=5.0)
grid.add_load(bus=bus_pq, api_obj=load)

# ----------------------------------------------------------------------------------------------------------------------
# Run power flow
# ----------------------------------------------------------------------------------------------------------------------
res = vge.power_flow(grid=grid, options=vge.PowerFlowOptions())

print("\nPositive-sequence power flow results:")
print(res.get_voltage_df())
print(res.converged)
print(res.iterations)

# ----------------------------------------------------------------------------------------------------------------------
# Run three-phase power flow
# ----------------------------------------------------------------------------------------------------------------------
res_3ph = vge.power_flow3ph(grid=grid, options=vge.PowerFlowOptions())

print("\nThree-phase power flow results:")
print(res_3ph.get_voltage_3ph_df())
print(res_3ph.converged)
print(res_3ph.iterations)