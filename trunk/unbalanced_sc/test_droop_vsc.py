import VeraGridEngine.api as vge
from VeraGridEngine import PowerFlowOptions, ShortCircuitOptions
from VeraGridEngine.enumerations import ConverterControlType, MethodShortCircuit, ConverterFaultControlType
from VeraGridEngine.Simulations.PowerFlow.power_flow_options import SolverType
import numpy as np

grid = vge.open_file('trunk/unbalanced_sc/test_droop_vsc.dgs')

# ------------------------------------------------------------------------------------------------------------------
#   AC/DC Power Flow under healthy conditions
# ------------------------------------------------------------------------------------------------------------------
pf_options = PowerFlowOptions(solver_type=SolverType.NR,
                              retry_with_other_methods=False,
                              limit_i_vsc=False)
res_pf = vge.power_flow(grid=grid, options=pf_options)

# ------------------------------------------------------------------------------------------------------------------
#   AC/DC Short-Circuit with converter's current limitation
# ------------------------------------------------------------------------------------------------------------------
grid.buses[1].r_fault = 6.0 / (33**2/100)

grid.add_short_circuit_event(
    vge.ShortCircuitEvent(
        device=grid.buses[1],
        method=MethodShortCircuit.sequences_vsc,
    )
)

sc_driver = vge.ShortCircuitDriver(grid=grid,
                                   options=ShortCircuitOptions(),
                                   pf_options=pf_options,
                                   pf_results=res_pf,
                                   pf_results3ph=None)
sc_driver.run()
res_sc = sc_driver.results

print(np.abs(res_sc.voltage1))