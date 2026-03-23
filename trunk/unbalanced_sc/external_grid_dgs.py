import VeraGridEngine.api as vge
from VeraGridEngine import PowerFlowOptions, ShortCircuitOptions
from VeraGridEngine.enumerations import MethodShortCircuit
from VeraGridEngine.Simulations.PowerFlow.power_flow_options import SolverType
import numpy as np

grid = vge.open_file('trunk/unbalanced_sc/ieee14_external_grid.dgs')

print()