import VeraGridEngine.api as vge
from VeraGridEngine import PowerFlowOptions, ShortCircuitOptions
from VeraGridEngine.enumerations import ConverterControlType, MethodShortCircuit, ConverterFaultControlType
from VeraGridEngine.Simulations.PowerFlow.power_flow_options import SolverType
import numpy as np

logger = vge.Logger()
grid = vge.open_file('ieee_14_1VSC.veragrid')

Ubase = 33e3
Sbase = 100e6
Zbase = Ubase**2 / Sbase
grid.buses[9].r_fault = 10 / Zbase

grid.vsc_devices[0].control1_val = -9.0
grid.vsc_devices[0].control2_val = -0.0
grid.vsc_devices[0].fault_control = ConverterFaultControlType.WECC_WT_Type_4B
grid.vsc_devices[0].rate = 9.0

vge.save_file(grid, 'ieee_14_1VSC_modified.veragrid')

# ----------------------------------------------------------------------------------------------------------------------
#   AC/DC Power Flow under healthy conditions
# ----------------------------------------------------------------------------------------------------------------------
pf_options_1 = PowerFlowOptions(solver_type=SolverType.NR,
                                retry_with_other_methods=False,
                                limit_i_vsc=False,
                                verbose=1)
res_pf = vge.power_flow(grid=grid, options=pf_options_1)

print(res_pf.get_voltage_df())

# ----------------------------------------------------------------------------------------------------------------------
#   AC/DC Short-Circuit with converter's current limitation
# ----------------------------------------------------------------------------------------------------------------------
pf_options_2 = PowerFlowOptions(solver_type=SolverType.NR,
                                retry_with_other_methods=False,
                                limit_i_vsc=True,
                                verbose=1,
                                max_iter=150,
                                tolerance=1e-12)

grid.add_short_circuit_event(
    vge.ShortCircuitEvent(
        device=grid.buses[9],
        method=MethodShortCircuit.sequences_vsc,
    )
)

sc_driver = vge.ShortCircuitDriver(grid=grid,
                                   options=ShortCircuitOptions(),
                                   pf_options=pf_options_2,
                                   pf_results=res_pf,
                                   pf_results3ph=None)
sc_driver.run()

res_sc = sc_driver.results

print('\n --- Short-circuit Results --- ')
print('\n Faulted Voltage =', np.round(np.abs(res_sc.voltage1[9]), 4))
print()
print(res_sc.get_voltage_df())
# print(res_sc.get_current_df())
print('\n VSC Power =', np.round(res_sc.vsc_St[0], 6))