# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import argparse
import os
import sys
import traceback
from typing import Callable

import numpy as np


ROOT_DIR: str = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SRC_DIR: str = os.path.join(ROOT_DIR, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)
else:
    pass

import VeraGridEngine.api as gce
from VeraGridEngine.Simulations.Rms.rms_driver import RmsSimulationDriver
from VeraGridEngine.Simulations.Rms.numerical import pseudo_transient as pseudo_transient_module
from VeraGridEngine.enumerations import RmsInitializationMethod

from trunk.dynamics.scripting_pseudo_transient import build_grid


FOCUSED_NAMES: tuple[str, ...] = (
    "delta",
    "omega",
    "Eq_prime",
    "Ed_prime",
    "Psiq_prime",
    "Psid_prime",
    "Id",
    "Iq",
    "Id_sat",
    "Iq_sat",
    "Vd",
    "Vq",
    "Eq1",
    "Ed1",
    "Vf",
    "IRPu",
    "f_input",
    "f_output",
    "Efe",
    "y_subexciter1",
    "u_aux",
    "UsRefPu",
    "u_exciter3",
    "y_exciter3",
    "Pm_ref",
)


class PseudoTransientSnapshot:
    """
    Store focused pseudo-transient values captured from one solver call.

    :param call_index: Pseudo-transient solver call number in the current run.
    :param initial_values: Focused values at the random/seeded initial point.
    :param final_values: Focused values at the pseudo-transient returned point.
    """

    __slots__ = (
        "call_index",
        "initial_values",
        "final_values",
    )

    def __init__(self, call_index: int, initial_values: dict[str, float], final_values: dict[str, float]) -> None:
        """
        Initialize the snapshot container.

        :param call_index: Pseudo-transient solver call number in the current run.
        :param initial_values: Focused values at the random/seeded initial point.
        :param final_values: Focused values at the pseudo-transient returned point.
        :return: None.
        """
        self.call_index: int = call_index
        self.initial_values: dict[str, float] = initial_values
        self.final_values: dict[str, float] = final_values


def _focused_values(problem: object, x_values: np.ndarray) -> dict[str, float]:
    """
    Extract focused variable values from a local pseudo-transient vector.

    :param problem: Local pseudo-transient initialization problem.
    :param x_values: Local variable vector.
    :return: Focused value map keyed by variable name.
    """
    values: dict[str, float] = dict()
    state_vars: list[object] = list(getattr(problem, "_state_vars", list()))
    algebraic_vars: list[object] = list(getattr(problem, "_algebraic_vars", list()))
    local_vars: list[object] = state_vars + algebraic_vars
    focused_names: set[str] = set(FOCUSED_NAMES)

    for index, var in enumerate(local_vars):
        if index < x_values.size:
            var_name: str = str(getattr(var, "name", ""))
            if var_name in focused_names:
                values[var_name] = float(x_values[index])
            else:
                pass
        else:
            pass

    return values


def _print_values(title: str, values: dict[str, float]) -> None:
    """
    Print focused values in stable order.

    :param title: Section title.
    :param values: Focused value map keyed by variable name.
    :return: None.
    """
    print(title)
    for name in FOCUSED_NAMES:
        value: float | None = values.get(name, None)
        if value is not None:
            print(f"  {name:16s} {value:+.12e}")
        else:
            pass


def _make_wrapped_simulate(
        original_simulate: Callable,
        snapshots: list[PseudoTransientSnapshot],
) -> Callable:
    """
    Build a wrapper that records focused pseudo-transient values.

    :param original_simulate: Original ``PseudoTransient.simulate`` method.
    :param snapshots: Snapshot list to fill.
    :return: Wrapped simulate method.
    """

    def wrapped_simulate(self: object, plot: bool = True, x0: np.ndarray | None = None) -> tuple[np.ndarray, dict]:
        """
        Run pseudo-transient while recording focused initial/final local values.

        :param self: PseudoTransient solver instance.
        :param plot: Whether the solver should plot diagnostics.
        :param x0: Initial local vector.
        :return: Original solver return value.
        """
        call_index: int = len(snapshots) + 1
        if x0 is None:
            initial_values: dict[str, float] = dict()
        else:
            initial_values = _focused_values(problem=self.problem, x_values=np.asarray(x0, dtype=float))

        result: tuple[np.ndarray, dict] = original_simulate(self, plot=False, x0=x0)
        final_values: dict[str, float] = _focused_values(problem=self.problem, x_values=np.asarray(result[0], dtype=float))
        snapshots.append(PseudoTransientSnapshot(
            call_index=call_index,
            initial_values=initial_values,
            final_values=final_values,
        ))

        return result

    return wrapped_simulate


def _run_one_seed(seed: int, use_algebraic_mass: bool, mass_value: float, summary_only: bool) -> bool:
    """
    Run one deterministic pseudo-transient initialization diagnostic.

    :param seed: NumPy global random seed used before initialization.
    :param use_algebraic_mass: Whether to enable the experimental algebraic mass shift.
    :param mass_value: Algebraic mass value when enabled.
    :param summary_only: Print only the seed outcome without focused values.
    :return: ``True`` when initialization succeeds, otherwise ``False``.
    """
    snapshots: list[PseudoTransientSnapshot] = list()
    original_simulate: Callable = pseudo_transient_module.PseudoTransient.simulate
    pseudo_transient_module.PseudoTransient.simulate = _make_wrapped_simulate(
        original_simulate=original_simulate,
        snapshots=snapshots,
    )

    if use_algebraic_mass:
        os.environ["VERAGRID_PSEUDO_ALGEBRAIC_MASS"] = repr(float(mass_value))
        os.environ["VERAGRID_PSEUDO_ALGEBRAIC_MASS_NAMES"] = "UsRefPu,u_exciter3,y_exciter3"
    else:
        os.environ.pop("VERAGRID_PSEUDO_ALGEBRAIC_MASS", None)
        os.environ.pop("VERAGRID_PSEUDO_ALGEBRAIC_MASS_NAMES", None)

    np.random.seed(seed)
    ok: bool = False
    error_text: str = ""

    try:
        grid: gce.MultiCircuit = build_grid()
        pf_options: gce.PowerFlowOptions = gce.PowerFlowOptions(
            solver_type=gce.SolverType.NR,
            retry_with_other_methods=False,
            verbose=0,
            tolerance=1e-6,
            max_iter=25,
            control_q=False,
            distributed_slack=False,
        )
        pf_results = gce.power_flow(grid, options=pf_options)
        rms_options: gce.RmsOptions = gce.RmsOptions(
            time_step=0.01,
            simulation_time=1.0,
            integration_method=gce.DynamicIntegrationMethod.DaeBackEuler,
            initialization_method=RmsInitializationMethod.PseudoTransient,
            max_iter=1000,
            tolerance=1e-8,
            verbose=False,
        )
        rms_driver: RmsSimulationDriver = RmsSimulationDriver(
            grid=grid,
            options=rms_options,
            pf_results=pf_results,
        )
        rms_driver.run()
        ok = True
    except Exception as exc:
        error_text = f"{type(exc).__name__}: {exc}"
    finally:
        pseudo_transient_module.PseudoTransient.simulate = original_simulate

    print(f"seed={seed} ok={ok} mass_enabled={use_algebraic_mass} mass={mass_value:.6g}")
    if not ok:
        print(f"error={error_text}")
    else:
        pass

    if summary_only:
        pass
    else:
        for snapshot in snapshots:
            print(f"pseudo_call={snapshot.call_index}")
            _print_values("initial focused values:", snapshot.initial_values)
            _print_values("final pseudo focused values:", snapshot.final_values)

    if len(snapshots) == 0 and not ok:
        traceback.print_exc()
    else:
        pass

    return ok


def main() -> None:
    """
    Run deterministic pseudo-transient seed diagnostics.

    :return: None.
    """
    parser: argparse.ArgumentParser = argparse.ArgumentParser()
    parser.add_argument("--seeds", nargs="+", type=int, default=[1, 2, 3, 4, 5])
    parser.add_argument("--mass", action="store_true")
    parser.add_argument("--mass-value", type=float, default=10.0)
    parser.add_argument("--summary-only", action="store_true")
    args: argparse.Namespace = parser.parse_args()

    passed: int = 0
    failed: int = 0
    for seed in args.seeds:
        ok: bool = _run_one_seed(
            seed=seed,
            use_algebraic_mass=bool(args.mass),
            mass_value=float(args.mass_value),
            summary_only=bool(args.summary_only),
        )
        if ok:
            passed += 1
        else:
            failed += 1
        print("")

    print(f"summary passed={passed} failed={failed}")


if __name__ == "__main__":
    main()
