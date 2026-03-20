import VeraGridEngine.api as vge
from VeraGridEngine import PowerFlowOptions, ShortCircuitOptions
from VeraGridEngine.enumerations import ConverterControlType, MethodShortCircuit, ConverterFaultControlType
from VeraGridEngine.Simulations.PowerFlow.power_flow_options import SolverType
import numpy as np

grid = vge.MultiCircuit()

# ------------------------------------------------------------------------------------------------------------------
#   Buses
# ------------------------------------------------------------------------------------------------------------------
bus_dc = vge.Bus(name='Bus DC', Vnom=20.0, xpos=0, ypos=0, is_dc=True, is_slack=True)
grid.add_bus(obj=bus_dc)

bus_wt = vge.Bus(name='Bus WT', Vnom=20.0, xpos=0, ypos=300)
grid.add_bus(obj=bus_wt)

bus_ac = vge.Bus(name='Bus AC', Vnom=20.0, xpos=0, ypos=600, r_fault=15)  # Rf = 60 ohm
grid.add_bus(obj=bus_ac)

bus_slack = vge.Bus(name='Bus Slack', Vnom=20.0, xpos=0, ypos=900, is_slack=True)
grid.add_bus(obj=bus_slack)

# ------------------------------------------------------------------------------------------------------------------
#   Line
# ------------------------------------------------------------------------------------------------------------------
line_wt_ac = vge.Line(name='Line WT-AC', bus_from=bus_wt, bus_to=bus_ac, r=1, x=10, rate=2.5)
grid.add_line(line_wt_ac)

line_slack_ac = vge.Line(name='Line AC-Slack', bus_from=bus_ac, bus_to=bus_slack, r=1, x=10, rate=2.5)
grid.add_line(line_slack_ac)

# ------------------------------------------------------------------------------------------------------------------
#   VSC
# ------------------------------------------------------------------------------------------------------------------
vsc = vge.VSC(bus_from=bus_dc,
              bus_to=bus_wt,
              rate=33.33333,
              alpha1=0.0,
              alpha2=0.0,
              alpha3=0.0,
              control1=ConverterControlType.Pac,
              control2=ConverterControlType.Qac,
              control1_val=-12.0,
              control2_val=-0.0,
              fault_control=ConverterFaultControlType.WECC_WT_Type_4B,
              kdp=3.0,
              u_setpoint_min=0.95,
              u_setpoint_max=1.05,
              u_setpoint=1.01,
              du_setpoint=0.0,
              Q_min=-100.0,
              Q_max=100.0
              )
grid.add_vsc(vsc)

# ------------------------------------------------------------------------------------------------------------------
#   Generators
# ------------------------------------------------------------------------------------------------------------------
generator_dc = vge.Generator()
grid.add_generator(bus_dc, generator_dc)

generator_ac = vge.Generator(r1=0.1, x1=1)
grid.add_generator(bus_slack, generator_ac)

# ------------------------------------------------------------------------------------------------------------------
#   AC/DC Power Flow under healthy conditions
# ------------------------------------------------------------------------------------------------------------------
vge.save_file(grid, 'droop_vsc.veragrid')
pf_options = PowerFlowOptions(solver_type=SolverType.NR,
                              retry_with_other_methods=False,
                              limit_i_vsc=False)
res_pf = vge.power_flow(grid=grid, options=pf_options)

print(res_pf.get_voltage_df())