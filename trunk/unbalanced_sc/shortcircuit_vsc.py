import VeraGridEngine.api as vge
from VeraGridEngine import PowerFlowOptions, ShortCircuitOptions
from VeraGridEngine.enumerations import ConverterControlType, MethodShortCircuit
from VeraGridEngine.Simulations.PowerFlow.power_flow_options import SolverType

logger = vge.Logger()
grid = vge.MultiCircuit()

# ----------------------------------------------------------------------------------------------------------------------
#   Buses
# ----------------------------------------------------------------------------------------------------------------------
bus_dc = vge.Bus(name='Bus DC', xpos=0, ypos=0, is_dc=True)
grid.add_bus(obj=bus_dc)

bus_ac = vge.Bus(name='Bus AC', xpos=0, ypos=300)
grid.add_bus(obj=bus_ac)

bus_slack = vge.Bus(name='Bus Slack', xpos=-300, ypos=600, is_slack=True)
grid.add_bus(obj=bus_slack)

bus_pq = vge.Bus(name='Bus PQ', xpos=300, ypos=600, r_fault=1.0)
grid.add_bus(obj=bus_pq)

# ----------------------------------------------------------------------------------------------------------------------
#   Lines
# ----------------------------------------------------------------------------------------------------------------------
line_slack_ac = vge.Line(name='Slack - AC', bus_from=bus_slack, bus_to=bus_ac, r=0.001, x=1, rate=20.0)
grid.add_line(line_slack_ac)

line_slack_pq = vge.Line(name='Slack - PQ', bus_from=bus_slack, bus_to=bus_pq, r=0.001, x=1, rate=20.0)
grid.add_line(line_slack_pq)

line_ac_pq = vge.Line(name='AC - PQ', bus_from=bus_ac, bus_to=bus_pq, r=0.001, x=1, rate=20.0)
grid.add_line(line_ac_pq)

# ----------------------------------------------------------------------------------------------------------------------
#   VSC
# ----------------------------------------------------------------------------------------------------------------------
vsc = vge.VSC(bus_from=bus_dc,
              bus_to=bus_ac,
              rate=15.0,
              alpha1=0.0,
              alpha2=0.0,
              alpha3=0.0,
              control1=ConverterControlType.Vm_dc,
              control2=ConverterControlType.Qac,
              control1_val=1.0,
              control2_val=-5.0)
grid.add_vsc(vsc)

# ----------------------------------------------------------------------------------------------------------------------
#   Load
# ----------------------------------------------------------------------------------------------------------------------
load_ac = vge.Load(P=20.0, Q=10.0)
grid.add_load(bus_pq, load_ac)

# ----------------------------------------------------------------------------------------------------------------------
#   Generators
# ----------------------------------------------------------------------------------------------------------------------
generator_slack = vge.Generator(r1=0.005, x1=1.8)
grid.add_generator(bus_slack, generator_slack)

generator_dc = vge.Generator(P=10.0, r1=1e-6, x1=1e-4)
grid.add_generator(bus_dc, generator_dc)

# ----------------------------------------------------------------------------------------------------------------------
#   Save Grid
# ----------------------------------------------------------------------------------------------------------------------
vge.save_file(grid=grid, filename='shortcircuit_vsc.veragrid')

# ----------------------------------------------------------------------------------------------------------------------
#   AC/DC Power Flow under healthy conditions
# ----------------------------------------------------------------------------------------------------------------------
pf_options_1 = PowerFlowOptions(solver_type=SolverType.NR,
                                retry_with_other_methods=False,
                                limit_i_vsc=False)
res_pf = vge.power_flow(grid=grid, options=pf_options_1)

# ----------------------------------------------------------------------------------------------------------------------
#   AC/DC Short-Circuit with converter's current limitation
# ----------------------------------------------------------------------------------------------------------------------
pf_options_2 = PowerFlowOptions(solver_type=SolverType.NR,
                                retry_with_other_methods=False,
                                limit_i_vsc=True)

sc_options = ShortCircuitOptions()

grid.add_short_circuit_definition(
    vge.ShortCircuitEvent(
        device=grid.buses[3],
        method=MethodShortCircuit.sequences_vsc
    )
)

sc_driver = vge.ShortCircuitDriver(grid=grid,
                                   options=sc_options,
                                   pf_options=pf_options_2,
                                   pf_results=res_pf,
                                   pf_results3ph=None)

sc_driver.run()

res_sc = sc_driver.results

print()