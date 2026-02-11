import os
import numpy as np
import pandas as pd
import VeraGridEngine.api as vge
from VeraGridEngine.IO.file_handler import FileOpen
from VeraGridEngine.Simulations.PowerFlow.power_flow_worker import PowerFlowOptions

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# def test_ieee_grids_3ph():
#     """
#     Checks the .RAW files of IEEE grids against the PSS/e results
#     This test checks 2 things:
#     - PSS/e import fidelity
#     - PSS/e vs VeraGrid results
#     :return: Nothing if ok, fails if not
#     """
#
#     files = [
#         ('IEEE 14 bus.raw', 'IEEE 14 bus.sav.xlsx'),
#         ('IEEE 30 bus.raw', 'IEEE 30 bus.sav.xlsx'),
#         ('IEEE 118 Bus v2.raw', 'IEEE 118 Bus.sav.xlsx'),
#     ]
#
#     options = PowerFlowOptions(verbose=0,
#                                control_q=False,
#                                retry_with_other_methods=False)
#
#     for f1, f2 in files:
#         print(f1, end=' ')
#
#         fname = os.path.join(SCRIPT_DIR, 'data', 'grids', 'RAW', f1)
#         main_circuit = FileOpen(fname).open()
#
#         vge.save_file(grid=main_circuit, filename='positive_sequence_3ph_pf.veragrid')
#
#         # Positive-sequence power flow
#         res_ps = vge.power_flow(grid=main_circuit, options=options)
#         v_ps = np.abs(res_ps.voltage)
#         p_ps = np.real(res_ps.Sf)
#
#         # Three-phase power flow
#         res_3ph = vge.power_flow3ph(grid=main_circuit, options=options)
#         v_3ph_a = np.abs(res_3ph.voltage_A)
#         p_3ph_a = np.real(res_3ph.Sf_A)
#         v_3ph_b = np.abs(res_3ph.voltage_B)
#         p_3ph_b = np.real(res_3ph.Sf_B)
#         v_3ph_c = np.abs(res_3ph.voltage_C)
#         p_3ph_c = np.real(res_3ph.Sf_C)
#
#         # load the associated results file
#         df_v = pd.read_excel(os.path.join(SCRIPT_DIR, 'data', 'results', f2), sheet_name='Vabs', index_col=0)
#         df_p = pd.read_excel(os.path.join(SCRIPT_DIR, 'data', 'results', f2), sheet_name='Pbranch', index_col=0)
#         v_psse = df_v.values[:, 0]
#         p_psse = df_p.values[:, 0]
#
#         # comparison
#         v_arrays = [v_ps, v_3ph_a, v_3ph_b, v_3ph_c, v_psse]
#         p_arrays = [p_ps, p_3ph_a, p_3ph_b, p_3ph_c, p_psse]
#         v_ok = all(np.allclose(v_arrays[0], arr, atol=1e-4) for arr in v_arrays[1:])
#         flow_ok = all(np.allclose(p_arrays[0], arr, atol=1e-2) for arr in p_arrays[1:])
#
#         if not v_ok:
#             print('power flow voltages test for {} failed'.format(fname))
#         if not flow_ok:
#             print('power flow flows test for {} failed'.format(fname))
#
#         assert v_ok
#         assert flow_ok