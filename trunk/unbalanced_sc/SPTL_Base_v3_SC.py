import VeraGridEngine.api as vge
from VeraGridEngine import PowerFlowOptions, ShortCircuitOptions
from VeraGridEngine.enumerations import ConverterControlType, MethodShortCircuit, ConverterFaultControlType
from VeraGridEngine.Simulations.PowerFlow.power_flow_options import SolverType
import numpy as np

grid = vge.open_file('SPTL_Base_v3_SC.dgs')

# ------------------------------------------------------------------------------------------------------------------
#   AC/DC Power Flow under healthy conditions
# ------------------------------------------------------------------------------------------------------------------
pf_options_1 = PowerFlowOptions(solver_type=SolverType.NR,
                                retry_with_other_methods=False,
                                limit_i_vsc=False,
                                verbose=1)
res_pf = vge.power_flow(grid=grid, options=pf_options_1)

# ------------------------------------------------------------------------------------------------------------------
#   AC/DC Short-Circuit with converter's current limitation
# ------------------------------------------------------------------------------------------------------------------
grid.add_short_circuit_event(
    vge.ShortCircuitEvent(
        device=grid.buses[2],
        method=MethodShortCircuit.sequences_vsc,
        r_fault=5/(33**2/100)
    )
)

pf_options_2 = PowerFlowOptions(solver_type=SolverType.NR,
                                retry_with_other_methods=False,
                                limit_i_vsc=False,
                                verbose=1,
                                max_iter=150,
                                tolerance=1e-6)

sc_driver = vge.ShortCircuitDriver(grid=grid,
                                   options=ShortCircuitOptions(),
                                   pf_options=pf_options_2,
                                   pf_results=res_pf,
                                   pf_results3ph=None)
sc_driver.run()
res_sc = sc_driver.results

print(np.abs(res_sc.voltage1[:, 0]))