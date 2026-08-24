# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""
Compare HELM-DPR power flow and DPR sigma convergence on the ESPT grid.

The diagnostic is intentionally island-level because the reported mismatch is that DPR power flow converges while
sigma analysis reports non-convergence. This separates the controlled DPR power-flow solve from the extra
non-restarting continuation currently used to obtain DPR sigma coefficients.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd


def main() -> None:
    """
    Run island-level HELM-DPR power-flow and DPR sigma diagnostics.

    :return: None.
    """

    # Make the checkout ``src`` directory importable when the script is executed directly.
    root: Path = Path(__file__).resolve().parents[2]
    src_path: str = str(root / "src")

    if src_path in sys.path:
        src_path = src_path
    else:
        sys.path.insert(0, src_path)

    from VeraGridEngine.IO.file_open import FileOpen
    from VeraGridEngine.Compilers.circuit_to_data import compile_numerical_circuit_at
    from VeraGridEngine.Simulations.PowerFlow.NumericalMethods.helm_dpr import helm_dpr
    from VeraGridEngine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions
    from VeraGridEngine.Simulations.SigmaAnalysis.sigma_dpr import sigma_dpr
    from VeraGridEngine.enumerations import GeneratorControlMode, ShuntControlMode
    from VeraGridEngine.basic_structures import Logger

    grid_path: Path = Path("/home/santi/Escritorio/espt_PDBF_20250101_20251231.veragrid")
    options: PowerFlowOptions = PowerFlowOptions(tolerance=1e-8,
                                                 max_iter=40,
                                                 control_q=True,
                                                 distributed_slack=False)
    logger: Logger = Logger()
    grid = FileOpen(file_name=str(grid_path)).open()
    nc = compile_numerical_circuit_at(circuit=grid,
                                      apply_temperature=options.apply_temperature_correction,
                                      branch_tolerance_mode=options.branch_impedance_tolerance_mode,
                                      opf_results=None,
                                      logger=logger)
    islands = nc.split_into_islands(ignore_single_node_islands=options.ignore_single_node_islands,
                                    consider_hvdc_as_island_links=False,
                                    logger=logger)
    rows: list[dict[str, object]] = list()

    for island_idx, island in enumerate(islands):
        S0: np.ndarray = island.get_power_injections_pu()
        indices = island.get_simulation_indices(Sbus=S0, force_only_pq_pv_vd_types=False)

        if len(indices.vd) > 0:
            adm = island.get_admittance_matrices()
            adms = island.get_series_admittance_matrices()
            Qmax, Qmin = island.get_reactive_power_limits()
            control_discrete_shunts: bool = bool(np.any(
                island.shunt_data.control_mode_int == ShuntControlMode.Discrete.idx()))
            control_qv_droop: bool = bool(np.any(
                island.generator_data.control_mode_int == GeneratorControlMode.QVDroop.idx()))

            pf_result = helm_dpr(nc=island,
                                 Ybus=adm.Ybus,
                                 Yf=adm.Yf,
                                 Yt=adm.Yt,
                                 Yshunt_bus=adm.Yshunt_bus,
                                 Yseries=adms.Yseries,
                                 V0=island.bus_data.Vbus,
                                 S0=S0,
                                 Ysh0=adms.Yshunt,
                                 pq=indices.pq,
                                 pv=indices.pv,
                                 vd=indices.vd,
                                 no_slack=indices.no_slack,
                                 tolerance=options.tolerance,
                                 max_coefficients=options.max_iter,
                                 use_pade=False,
                                 restart_order=6,
                                 max_restarts=20,
                                 use_classical_germ=False,
                                 control_q=options.control_Q,
                                 pqv=indices.pqv,
                                 p=indices.p,
                                 Qmin=Qmin,
                                 Qmax=Qmax,
                                 control_discrete_shunts=control_discrete_shunts,
                                 control_qv_droop=control_qv_droop,
                                 distributed_slack=options.distributed_slack,
                                 bus_installed_power=island.bus_data.installed_power,
                                 controls_tol=options.controls_start_tolerance,
                                 verbose=0,
                                 logger=logger)

            sigma_result = sigma_dpr(nc=island,
                                     Ybus=adm.Ybus,
                                     Yshunt_bus=adm.Yshunt_bus,
                                     Yseries=adms.Yseries,
                                     V0=island.bus_data.Vbus,
                                     S0=S0,
                                     Ysh0=adms.Yshunt,
                                     pq=indices.pq,
                                     pv=indices.pv,
                                     vd=indices.vd,
                                     no_slack=indices.no_slack,
                                     tolerance=options.tolerance,
                                     max_coefficients=options.max_iter,
                                     restart_order=6,
                                     max_restarts=20,
                                     use_classical_germ=False,
                                     control_q=options.control_Q,
                                     pqv=indices.pqv,
                                     p=indices.p,
                                     Qmin=Qmin,
                                     Qmax=Qmax,
                                     control_discrete_shunts=control_discrete_shunts,
                                     control_qv_droop=control_qv_droop,
                                     distributed_slack=options.distributed_slack,
                                     bus_installed_power=island.bus_data.installed_power,
                                     controls_tol=options.controls_start_tolerance,
                                     verbose=0,
                                     logger=logger)

            rows.append({
                "island": island_idx,
                "nbus": island.nbus,
                "npq": len(indices.pq),
                "npv": len(indices.pv),
                "npqv": len(indices.pqv),
                "np": len(indices.p),
                "disc_sh": control_discrete_shunts,
                "qv_droop": control_qv_droop,
                "pf_ok": bool(pf_result.converged),
                "pf_norm": float(pf_result.norm_f),
                "pf_it": int(pf_result.iterations),
                "sigma_ok": bool(sigma_result.converged),
                "sigma_norm": float(sigma_result.norm_f),
                "sigma_it": int(sigma_result.iterations),
                "sigma_control_restarts": int(sigma_result.control_restarts),
                "max_dv_pf_sigma": float(np.max(np.abs(pf_result.V - sigma_result.V))),
                "min_sigma_distance": float(np.min(sigma_result.distances)),
            })
        else:
            rows.append({
                "island": island_idx,
                "nbus": island.nbus,
                "npq": len(indices.pq),
                "npv": len(indices.pv),
                "npqv": len(indices.pqv),
                "np": len(indices.p),
                "disc_sh": False,
                "qv_droop": False,
                "pf_ok": False,
                "pf_norm": np.inf,
                "pf_it": 0,
                "sigma_ok": False,
                "sigma_norm": np.inf,
                "sigma_it": 0,
                "sigma_control_restarts": 0,
                "max_dv_pf_sigma": np.inf,
                "min_sigma_distance": np.inf,
            })

    report: pd.DataFrame = pd.DataFrame(rows)
    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", 240)
    pd.set_option("display.float_format", "{:.3e}".format)
    print(report.to_string(index=False))


if __name__ == "__main__":
    main()
