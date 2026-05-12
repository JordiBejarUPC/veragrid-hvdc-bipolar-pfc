import VeraGridEngine.api as vge
from VeraGridEngine import PowerFlowOptions, ShortCircuitOptions
from VeraGridEngine.enumerations import ConverterControlType, MethodShortCircuit, ConverterFaultControlType
from VeraGridEngine.Simulations.PowerFlow.power_flow_options import SolverType
import numpy as np

logger = vge.Logger()
grid = vge.MultiCircuit()

# ----------------------------------------------------------------------------------------------------------------------
#   Buses
# ----------------------------------------------------------------------------------------------------------------------
bus_dc = vge.Bus(name='Bus DC', Vnom=20.0, xpos=0, ypos=0, is_dc=True, is_slack=True)
grid.add_bus(obj=bus_dc)

bus_wt = vge.Bus(name='Bus WT', Vnom=20.0, xpos=0, ypos=300)
grid.add_bus(obj=bus_wt)

bus_ac = vge.Bus(name='Bus AC', Vnom=20.0, xpos=0, ypos=600, r_fault=15) # Rf = 60
# bus_ac = vge.Bus(name='Bus AC', Vnom=20.0, xpos=0, ypos=600, r_fault=7.5) # Rf = 30
# bus_ac = vge.Bus(name='Bus AC', Vnom=20.0, xpos=0, ypos=600, r_fault=3.75) # Rf = 15
grid.add_bus(obj=bus_ac)

bus_slack = vge.Bus(name='Bus Slack', Vnom=20.0, xpos=0, ypos=1200, is_slack=True)
grid.add_bus(obj=bus_slack)

# ----------------------------------------------------------------------------------------------------------------------
#   Line
# ----------------------------------------------------------------------------------------------------------------------
line_wt_ac = vge.Line(name='Line WT-AC', bus_from=bus_wt, bus_to=bus_ac, r=1, x=10, rate=2.5)
grid.add_line(line_wt_ac)

line_slack_ac = vge.Line(name='Line AC-Slack', bus_from=bus_ac, bus_to=bus_slack, r=1, x=10, rate=2.5)
grid.add_line(line_slack_ac)

# ----------------------------------------------------------------------------------------------------------------------
#   VSC
# ----------------------------------------------------------------------------------------------------------------------
vsc = vge.VSC(bus_from=bus_dc,
              bus_to=bus_wt,
              rate=33.33333,
              alpha1=0.0,
              alpha2=0.0,
              alpha3=0.0,
              control1=ConverterControlType.Pac,
              control2=ConverterControlType.Qac,
              control1_val=-12.0,
              control2_val=-1.0,
              fault_control=ConverterFaultControlType.WECC_WT_Type_4B,
              kdp=3.0,
              u_setpoint_min=0.95,
              u_setpoint_max=1.05,
              u_setpoint=1.01,
              du_setpoint=0.0,
              Q_min=-7.41,
              Q_max=11.87
              )
grid.add_vsc(vsc)

# ----------------------------------------------------------------------------------------------------------------------
#   Generators
# ----------------------------------------------------------------------------------------------------------------------
generator_dc = vge.Generator()
grid.add_generator(bus_dc, generator_dc)

generator_ac = vge.Generator(r1=0.1, x1=1)
grid.add_generator(bus_slack, generator_ac)

# ----------------------------------------------------------------------------------------------------------------------
#   Save Grid
# ----------------------------------------------------------------------------------------------------------------------
# vge.save_file(grid=grid, filename='3bus_powerfactory.veragrid')

# ----------------------------------------------------------------------------------------------------------------------
#   AC/DC Power Flow under healthy conditions
# ----------------------------------------------------------------------------------------------------------------------
pf_options = PowerFlowOptions(solver_type=SolverType.NR,
                                retry_with_other_methods=False,
                                limit_i_vsc=False)
res_pf = vge.power_flow(grid=grid, options=pf_options)

# ----------------------------------------------------------------------------------------------------------------------
#   AC/DC Short-Circuit with converter's current limitation
# ----------------------------------------------------------------------------------------------------------------------
# grid.add_short_circuit_event(
#     vge.ShortCircuitEvent(
#         device=grid.buses[2],
#         method=MethodShortCircuit.sequences_vsc,
#     )
# )
#
# sc_driver = vge.ShortCircuitDriver(grid=grid,
#                                    options=ShortCircuitOptions(),
#                                    pf_options=pf_options,
#                                    pf_results=res_pf,
#                                    pf_results3ph=None)
# sc_driver.run()
#
# res_sc = sc_driver.results
#
# print('\n --- Short-circuit Results --- ')
# print('\n Faulted Voltage =', np.round(np.abs(res_sc.voltage1[2]), 4))
# Sbase = 100e6
# Ubase = 20e3
# Ibase = Sbase / (np.sqrt(3) * Ubase)
# Sbase_pf = 2e6
# Ubase_pf = 20e3
# Ibase_pf = Sbase_pf / (np.sqrt(3) * Ubase_pf)
# print('\n VSC Current =', np.round(np.abs(res_sc.vsc_It[0]) * Ibase / Ibase_pf, 4))
# print('\n VSC Power =', np.round(res_sc.vsc_St[0], 4))
#
# print()
# print(abs(res_sc.voltage1[:, 0]))