# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import sys
from pathlib import Path

import numpy as np
import pandas as pd


def main() -> None:
    """
    Check whether DPRHEM benefits from a non-classical voltage starting point.

    The check solves a light-load case first, then uses that voltage as the
    dynamic-restart germ for the full-load case.  That is the paper's core
    claim: start from a physical state and embed towards the target power state.

    :return: None.
    """

    # Make local imports work when this script is run directly from the checkout.
    root: Path = Path(__file__).resolve().parents[2]
    src_path: str = str(root / "src")

    if src_path in sys.path:
        src_path = src_path
    else:
        sys.path.insert(0, src_path)

    from VeraGridEngine.IO.file_open import FileOpen
    from VeraGridEngine.Compilers.circuit_to_data import compile_numerical_circuit_at
    from VeraGridEngine.Simulations.PowerFlow.NumericalMethods.helm_power_flow import helm_josep
    from VeraGridEngine.Simulations.PowerFlow.NumericalMethods.helm_dpr import helm_dpr
    from VeraGridEngine.basic_structures import Logger

    grid_dir: Path = root / "src" / "tests" / "data" / "grids" / "Matpower"
    cases: list[str] = list()
    cases.append("case9.matpower")
    cases.append("case14.matpower")
    cases.append("case_ieee30.matpower")
    cases.append("case24_ieee_rts.matpower")
    cases.append("case89pegase.matpower")
    cases.append("case1354pegase.matpower")
    cases.append("case2869pegase.matpower")
    cases.append("case8387pegase.matpower")
    cases.append("case9241pegase.matpower")
    cases.append("case13659pegase.matpower")

    tolerance: float = 1e-8
    max_coefficients: int = 40
    light_load_factor: float = 0.5
    logger: Logger = Logger()

    rows: list[dict[str, object]] = list()

    for case_name in cases:
        # Compile one grid and reuse the exact same island matrices for all calls.
        grid = FileOpen(file_name=str(grid_dir / case_name)).open()
        nc = compile_numerical_circuit_at(circuit=grid, t_idx=None)
        islands = nc.split_into_islands(ignore_single_node_islands=True,
                                        consider_hvdc_as_island_links=True,
                                        logger=logger)

        for island_idx, island in enumerate(islands):
            S_full: np.ndarray = island.get_power_injections_pu()
            indices = island.get_simulation_indices(Sbus=S_full)

            if len(indices.vd) > 0 and len(indices.no_slack) > 0:
                adm = island.get_admittance_matrices()
                adms = island.get_series_admittance_matrices()
                V_grid: np.ndarray = island.bus_data.Vbus.copy()
                S_light: np.ndarray = light_load_factor * S_full

                # Full-load base HELM is the reference direct call.
                helm_full = helm_josep(nc=island,
                                       Ybus=adm.Ybus,
                                       Yf=adm.Yf,
                                       Yt=adm.Yt,
                                       Yshunt_bus=adm.Yshunt_bus,
                                       Yseries=adms.Yseries,
                                       V0=V_grid,
                                       S0=S_full,
                                       Ysh0=adms.Yshunt,
                                       pq=indices.pq,
                                       pv=indices.pv,
                                       vd=indices.vd,
                                       no_slack=indices.no_slack,
                                       tolerance=tolerance,
                                       max_coefficients=max_coefficients,
                                       use_pade=False,
                                       verbose=0,
                                       logger=None)

                # Light-load HELM generates a physical warm germ for DPRHEM.
                light = helm_josep(nc=island,
                                   Ybus=adm.Ybus,
                                   Yf=adm.Yf,
                                   Yt=adm.Yt,
                                   Yshunt_bus=adm.Yshunt_bus,
                                   Yseries=adms.Yseries,
                                   V0=V_grid,
                                   S0=S_light,
                                   Ysh0=adms.Yshunt,
                                   pq=indices.pq,
                                   pv=indices.pv,
                                   vd=indices.vd,
                                   no_slack=indices.no_slack,
                                   tolerance=tolerance,
                                   max_coefficients=max_coefficients,
                                   use_pade=False,
                                   verbose=0,
                                   logger=None)

                # DPRHEM from the normal compiled voltage.
                dpr_flat = helm_dpr(nc=island,
                                    Ybus=adm.Ybus,
                                    Yf=adm.Yf,
                                    Yt=adm.Yt,
                                    Yshunt_bus=adm.Yshunt_bus,
                                    Yseries=adms.Yseries,
                                    V0=light.V,
                                    S0=S_full,
                                    Ysh0=adms.Yshunt,
                                    pq=indices.pq,
                                    pv=indices.pv,
                                    vd=indices.vd,
                                    no_slack=indices.no_slack,
                                    tolerance=tolerance,
                                    max_coefficients=max_coefficients,
                                    use_pade=False,
                                    restart_order=6,
                                    max_restarts=20,
                                    use_classical_germ=True,
                                    verbose=0,
                                    logger=None)

                # DPRHEM from the light-load physical voltage germ.
                dpr_warm = helm_dpr(nc=island,
                                    Ybus=adm.Ybus,
                                    Yf=adm.Yf,
                                    Yt=adm.Yt,
                                    Yshunt_bus=adm.Yshunt_bus,
                                    Yseries=adms.Yseries,
                                    V0=light.V,
                                    S0=S_full,
                                    Ysh0=adms.Yshunt,
                                    pq=indices.pq,
                                    pv=indices.pv,
                                    vd=indices.vd,
                                    no_slack=indices.no_slack,
                                    tolerance=tolerance,
                                    max_coefficients=max_coefficients,
                                    use_pade=False,
                                    restart_order=6,
                                    max_restarts=20,
                                    use_classical_germ=False,
                                    verbose=0,
                                    logger=None)

                path_voltage: np.ndarray | None = None
                path_norm: float = np.inf
                path_iterations: int = 0
                path_stage: float = 0.0
                path_converged: bool = False
                path_alive: bool = True

                # Staged DPRHEM: solve local target-power increments and pass
                # each accepted voltage as the next germ. Failed local jumps are
                # retried with half the step because the DPR segment is local.
                path_step: float = 0.05
                path_attempts: int = 0

                while path_alive and not path_converged and path_attempts < 100:
                    load_factor: float = min(1.0, path_stage + path_step)
                    path_attempts += 1
                    path_result = helm_dpr(nc=island,
                                           Ybus=adm.Ybus,
                                           Yf=adm.Yf,
                                           Yt=adm.Yt,
                                           Yshunt_bus=adm.Yshunt_bus,
                                           Yseries=adms.Yseries,
                                           V0=path_voltage,
                                           S0=load_factor * S_full,
                                           Ysh0=adms.Yshunt,
                                           pq=indices.pq,
                                           pv=indices.pv,
                                           vd=indices.vd,
                                           no_slack=indices.no_slack,
                                           tolerance=tolerance,
                                           max_coefficients=max_coefficients,
                                           use_pade=False,
                                           restart_order=6,
                                           max_restarts=20,
                                           use_classical_germ=path_voltage is None,
                                           verbose=0,
                                           logger=None)
                    path_iterations += path_result.iterations
                    path_norm = path_result.norm_f

                    if path_result.converged:
                        path_voltage = path_result.V
                        path_stage = float(load_factor)
                        path_converged = bool(load_factor >= 1.0)
                        path_step = min(0.1, path_step * 1.5)
                    else:
                        path_step *= 0.5
                        if path_step < 1e-4:
                            path_stage = float(load_factor)
                            path_alive = False

                flat_vs_warm_dv: float = float(np.max(np.abs(dpr_flat.V - dpr_warm.V)))

                rows.append({
                    "grid": case_name,
                    "island": island_idx,
                    "nbus": island.nbus,
                    "helm_ok": helm_full.converged,
                    "helm_norm": helm_full.norm_f,
                    "helm_it": helm_full.iterations,
                    "light_ok": light.converged,
                    "light_norm": light.norm_f,
                    "light_it": light.iterations,
                    "dpr_flat_ok": dpr_flat.converged,
                    "dpr_flat_norm": dpr_flat.norm_f,
                    "dpr_flat_it": dpr_flat.iterations,
                    "dpr_warm_ok": dpr_warm.converged,
                    "dpr_warm_norm": dpr_warm.norm_f,
                    "dpr_warm_it": dpr_warm.iterations,
                    "dpr_path_ok": path_converged,
                    "dpr_path_norm": path_norm,
                    "dpr_path_it": path_iterations,
                    "dpr_path_stage": path_stage,
                    "flat_vs_warm_dv": flat_vs_warm_dv,
                })
            else:
                rows.append({
                    "grid": case_name,
                    "island": island_idx,
                    "nbus": island.nbus,
                    "helm_ok": False,
                    "helm_norm": np.nan,
                    "helm_it": 0,
                    "light_ok": False,
                    "light_norm": np.nan,
                    "light_it": 0,
                    "dpr_flat_ok": False,
                    "dpr_flat_norm": np.nan,
                    "dpr_flat_it": 0,
                    "dpr_warm_ok": False,
                    "dpr_warm_norm": np.nan,
                    "dpr_warm_it": 0,
                    "dpr_path_ok": False,
                    "dpr_path_norm": np.nan,
                    "dpr_path_it": 0,
                    "dpr_path_stage": np.nan,
                    "flat_vs_warm_dv": np.nan,
                })

    df: pd.DataFrame = pd.DataFrame(rows)
    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", 220)
    pd.set_option("display.float_format", "{:.3e}".format)
    print(df.to_string(index=False))


if __name__ == "__main__":
    main()
