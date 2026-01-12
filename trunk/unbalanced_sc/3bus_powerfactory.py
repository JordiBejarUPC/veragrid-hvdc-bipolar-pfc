import VeraGridEngine.api as vge
from VeraGridEngine import PowerFlowOptions, ShortCircuitOptions
from VeraGridEngine.enumerations import ConverterControlType, MethodShortCircuit
from VeraGridEngine.Simulations.PowerFlow.power_flow_options import SolverType

logger = vge.Logger()
grid = vge.MultiCircuit()

# ----------------------------------------------------------------------------------------------------------------------
#   Buses
# ----------------------------------------------------------------------------------------------------------------------
bus_slack = vge.Bus(name='Bus Slack', Vnom=20.0, xpos=0, ypos=900, is_slack=True)
grid.add_bus(obj=bus_slack)

bus_ac = vge.Bus(name='Bus AC', Vnom=20.0, xpos=0, ypos=600, r_fault=12.5)
grid.add_bus(obj=bus_ac)

bus_wt = vge.Bus(name='Bus WT', Vnom=0.69, xpos=0, ypos=300)
grid.add_bus(obj=bus_wt)

bus_dc = vge.Bus(name='Bus DC', Vnom=0.69, xpos=0, ypos=0, is_dc=True, is_slack=True)
grid.add_bus(obj=bus_dc)

# ----------------------------------------------------------------------------------------------------------------------
#   Transformer
# ----------------------------------------------------------------------------------------------------------------------
trafo_wt_ac = vge.Transformer2W(name='Trafo WT-AC',
                                bus_from=bus_wt, bus_to=bus_ac,
                                nominal_power=2.5)
trafo_wt_ac.fill_design_properties(Pcu=22.0,
                                   Pfe=0.0,
                                   I0=0.1,
                                   Vsc=6.0,
                                   Sbase=grid.Sbase)
grid.add_transformer2w(obj=trafo_wt_ac)

# ----------------------------------------------------------------------------------------------------------------------
#   Line
# ----------------------------------------------------------------------------------------------------------------------
line_slack_ac = vge.Line(name='Line AC-Slack', bus_from=bus_ac, bus_to=bus_slack, r=0.01, x=0.1, rate=2.5)
grid.add_line(line_slack_ac)

# ----------------------------------------------------------------------------------------------------------------------
#   VSC
# ----------------------------------------------------------------------------------------------------------------------
vsc = vge.VSC(bus_from=bus_dc,
              bus_to=bus_wt,
              rate=2.5,
              alpha1=0.0,
              alpha2=0.0,
              alpha3=0.0,
              control1=ConverterControlType.Vm_dc,
              control2=ConverterControlType.Qac,
              control1_val=1.0,
              control2_val=0.0)
grid.add_vsc(vsc)

# ----------------------------------------------------------------------------------------------------------------------
#   Generators
# ----------------------------------------------------------------------------------------------------------------------
generator_dc = vge.Generator(P=2.0, power_factor=1.0, r1=0.005)
grid.add_generator(bus_dc, generator_dc)

generator_ac = vge.Generator(r1=0.005, x1=0.05)
grid.add_generator(bus_slack, generator_ac)

# ----------------------------------------------------------------------------------------------------------------------
#   Save Grid
# ----------------------------------------------------------------------------------------------------------------------
vge.save_file(grid=grid, filename='3bus_powerfactory.veragrid')

# ----------------------------------------------------------------------------------------------------------------------
#   AC/DC Power Flow under healthy conditions
# ----------------------------------------------------------------------------------------------------------------------
pf_options_1 = PowerFlowOptions(solver_type=SolverType.NR,
                                retry_with_other_methods=False,
                                limit_i_vsc=False,
                                verbose=1)
res_pf = vge.power_flow(grid=grid, options=pf_options_1)

print('Power flow results:')
print(abs(res_pf.voltage))

# ----------------------------------------------------------------------------------------------------------------------
#   AC/DC Short-Circuit with converter's current limitation
# ----------------------------------------------------------------------------------------------------------------------
pf_options_2 = PowerFlowOptions(solver_type=SolverType.NR,
                                retry_with_other_methods=False,
                                limit_i_vsc=True,
                                verbose=1)

grid.add_short_circuit_definition(
    vge.ShortCircuitEvent(
        device=grid.buses[1],
        method=MethodShortCircuit.sequences_vsc
    )
)

sc_driver = vge.ShortCircuitDriver(grid=grid,
                                   options=ShortCircuitOptions(),
                                   pf_options=pf_options_2,
                                   pf_results=res_pf,
                                   pf_results3ph=None)
sc_driver.run()

res_sc = sc_driver.results

print('Short-circuit results:')
print(abs(res_sc.voltage1))

print('\nPower flow St_vsc =', res_pf.St_vsc)
print('\nPower flow St_line =', res_pf.Sf)

print('\nShort-circuit St_vsc =', res_sc.vsc_St)
print('\nShort-circuit St_line =', res_sc.Sf1)