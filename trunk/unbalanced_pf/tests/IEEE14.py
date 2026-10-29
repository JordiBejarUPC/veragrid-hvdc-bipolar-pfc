import os
import numpy as np
import pandas as pd
import VeraGridEngine.api as vge
from VeraGridEngine.IO.file_handler import FileOpen
from VeraGridEngine.Simulations.PowerFlow.power_flow_worker import PowerFlowOptions

grid = FileOpen('IEEE 14 bus.raw').open()

# for i in (1, 2, 3, 4):
#     grid.generators[i].active = False

options = PowerFlowOptions(verbose=0,
                           control_q=False,
                           retry_with_other_methods=False)

# Positive-sequence power flow
res_ps = vge.power_flow(grid=grid, options=options)
v_ps = np.abs(res_ps.voltage)
p_ps = np.real(res_ps.Sf)

# Three-phase power flow
res_3ph = vge.power_flow3ph(grid=grid, options=options)
v_3ph_a = np.abs(res_3ph.voltage_A)
p_3ph_a = np.real(res_3ph.Sf_A)
v_3ph_b = np.abs(res_3ph.voltage_B)
p_3ph_b = np.real(res_3ph.Sf_B)
v_3ph_c = np.abs(res_3ph.voltage_C)
p_3ph_c = np.real(res_3ph.Sf_C)

# for line in range(len(grid.lines)):
#     print()
#     print(grid.lines[line].ysh.values)
#
# print()

print()
print(v_3ph_a)
print(v_3ph_b)
print(v_3ph_c)
print()