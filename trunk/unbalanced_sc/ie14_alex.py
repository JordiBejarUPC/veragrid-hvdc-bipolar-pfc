import VeraGridEngine.api as vge
from VeraGridEngine import PowerFlowOptions, ShortCircuitOptions
from VeraGridEngine.enumerations import ConverterControlType, MethodShortCircuit, ConverterFaultControlType
from VeraGridEngine.Simulations.PowerFlow.power_flow_options import SolverType
import numpy as np

grid = vge.open_file('trunk/unbalanced_sc/ieee14_voltage_disconnection.veragrid')

for i, v in enumerate(grid.vsc_devices):
    grid.vsc_devices[i].kdp = 1.0

pf_options_1 = PowerFlowOptions(solver_type=SolverType.NR,
                                retry_with_other_methods=False,
                                limit_i_vsc=False,
                                verbose=1)
res_pf = vge.power_flow(grid=grid, options=pf_options_1)
