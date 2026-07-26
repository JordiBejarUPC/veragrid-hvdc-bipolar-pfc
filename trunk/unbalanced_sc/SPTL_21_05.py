import VeraGridEngine.api as vge
from VeraGridEngine import PowerFlowOptions, ShortCircuitOptions
from VeraGridEngine.enumerations import ConverterControlType, MethodShortCircuit, ConverterFaultControlType
from VeraGridEngine.Simulations.PowerFlow.power_flow_options import SolverType
import numpy as np


grid = vge.open_file('SPTL_11_05.dgs')

# ------------------------------------------------------------------------------------------------------------------
#   AC/DC Power Flow under healthy conditions
# ------------------------------------------------------------------------------------------------------------------
pf_options = PowerFlowOptions(solver_type=SolverType.NR,
                              retry_with_other_methods=False,
                              limit_i_vsc=False,
                              control_taps_modules=False,  # keeps taps fixed → limited support behaves like basic
                              control_taps_phase=False,
                              use_stored_guess=True,
                              verbose=0)
res_pf = vge.power_flow(grid=grid, options=pf_options)

print(res_pf.get_voltage_df())