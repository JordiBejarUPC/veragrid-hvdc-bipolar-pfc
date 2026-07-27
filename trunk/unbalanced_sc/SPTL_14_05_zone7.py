import VeraGridEngine.api as vge
from VeraGridEngine import PowerFlowOptions, ShortCircuitOptions
from VeraGridEngine.enumerations import ConverterControlType, MethodShortCircuit, ConverterFaultControlType
from VeraGridEngine.Simulations.PowerFlow.power_flow_options import SolverType
import numpy as np

grid = vge.open_file('SPTL_14_05_zone7.dgs')

bus_dc = vge.Bus(name='Bus DC', Vnom=132.0, xpos=0, ypos=0, is_dc=True, is_slack=True, is_grounded=False)
grid.add_bus(obj=bus_dc)

vsc = vge.VSC(bus_from=bus_dc,
              bus_to=grid.buses[7],
              alpha1=0.0,
              alpha2=0.0,
              alpha3=0.0,
              control1=ConverterControlType.Pac,
              control2=ConverterControlType.Qac,
              control1_val=0.0,
              control2_val=-0.0,
              fault_control=ConverterFaultControlType.WECC_WT_Type_4B)
grid.add_vsc(vsc)

vge.save_file(grid, 'zone7_with_vsc.veragrid')

# ------------------------------------------------------------------------------------------------------------------
#   AC/DC Power Flow under healthy conditions
# ------------------------------------------------------------------------------------------------------------------
pf_options = PowerFlowOptions(solver_type=SolverType.NR,
                              retry_with_other_methods=False,
                              limit_i_vsc=False,
                              control_taps_modules=False,  # keeps taps fixed → limited support behaves like basic
                              control_taps_phase=False,
                              verbose=0)
res_pf = vge.power_flow(grid=grid, options=pf_options)

