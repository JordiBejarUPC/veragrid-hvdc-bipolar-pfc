import numpy as np
import pandas as pd
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.EMT.emt_results import EmtResults
from VeraGridEngine.Simulations.EMT.Devices.emt_compiler import compile_emt
from VeraGridEngine.Simulations.PowerFlow.power_flow_results_3ph import PowerFlowResults3Ph
from VeraGridEngine.basic_structures import Logger


def run_time_simulation(grid: MultiCircuit,
                        emt_options: EmtOptions,
                        res_pf: PowerFlowResults3Ph,
                        logger: Logger) -> EmtResults:
    """
    Performs the EMTP loop using the MNA.
    :return:
    """
    emt_circuit = compile_emt(
        grid=grid,
        emt_options=emt_options,
        res_pf=res_pf,
        logger=logger
    )

    pass

    # # Inicializar estados internos para líneas
    # for branch in self.grid.get_branches_iter():
    #     if branch.device_type.value == 'Line':
    #         self.line_states[branch.name] = {
    #             'i_prev': None,  # Para modelo Pi
    #             'x_states': None  # Para modelo J-Marti
    #         }
    #
    # # simulate
    # t, V, hist, Ibranches, hist_branches, Is, x, dx = self.simulate_emt(
    #     t=t,
    #     simulation_time=self.options.simulation_time,
    #     grid=self.grid,
    #     nc=nc,
    #     syst_blocks=syst_blocks,
    #     init_guesses=init_guesses,
    #     time_step=h,
    #     N_delay=N_delay,
    #     G0=G0,
    #     binary_bus_mask=binary_bus_mask,
    #     branch_lookup=branch_lookup,
    #     bus_idx_lookup=bus_idx_lookup,
    #     alter_params_mappings=alter_params_mappings,
    #     uid2idx_alterparams=uid2idx_alterparams
    # )
    #
    # # self.results = EmtResults(values=y,
    # #                           time_array=pd.DatetimeIndex(pd.to_datetime(t)),
    # #                           uid2idx=slv.uid2idx_vars,
    # #                           vars_glob_name2uid=slv.v_glob_name2uid,
    # #                           devices = devices)
    #
    #
    # return t, V, hist, Ibranches, hist_branches, Is, x, dx
