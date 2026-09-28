# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""Point-to-point HVDC EMT demo with two switching GFL converters."""

from __future__ import annotations

from pathlib import Path
import sys

import matplotlib.pyplot as plt
import numpy as np


REPO_ROOT: Path = Path(__file__).resolve().parents[2]
SRC_ROOT: Path = REPO_ROOT / "src"
for import_root in (SRC_ROOT, REPO_ROOT):
    import_root_text: str = str(import_root)
    if import_root_text not in sys.path:
        sys.path.insert(0, import_root_text)
    else:
        pass

from VeraGridEngine.Templates.Emt.converter_switched_emt_template import get_switched_emt_converter
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Devices.Dynamic.static_parameter_mapping import converter_control_code
from VeraGridEngine.enumerations import (
    ConverterControlType,
    DynamicIntegrationMethod,
    DeviceType,
    EmtInitializationMethod,
    EmtSolverTypes,
)
from dynamics_emt import scripting_hvdc_vdc_control as hvdc_case


SWITCHING_HANDOVER_TIME_S: float = 0.020


def add_control_diagnostics(results: dict[str, object], plot: bool) -> None:
    """Expose the switched converters' internal tracking signals."""
    grid = results["grid"]
    problem = results["problem"]
    trajectory = results["trajectory"]
    time_s = results["time"]
    signals = results["signals"]
    diagnostic_names = (
        "i_d_ref",
        "i_d_meas_f",
        "i_q_ref",
        "i_q_meas_f",
        "P_f",
        "v_cmd_d",
        "v_cmd_q",
        "v_conv_d",
        "v_conv_q",
        "v_d_meas_f",
        "v_q_meas_f",
        "k_v_conv",
        "switching_blend",
    )
    for converter_index, converter in enumerate(grid.vsc_devices, start=1):
        for variable_name in diagnostic_names:
            signals[f"vsc{converter_index}_{variable_name}"] = hvdc_case.get_signal(
                problem,
                converter.emt_model,
                variable_name,
                trajectory,
            )

    if not plot:
        return

    figure, axes = plt.subplots(4, 2, figsize=(13, 11), sharex=True)
    for converter_index in (1, 2):
        axis_index = converter_index - 1
        axes[0, axis_index].plot(time_s, signals[f"vsc{converter_index}_i_d_ref"], "--", label="id ref")
        axes[0, axis_index].plot(time_s, signals[f"vsc{converter_index}_i_d_meas_f"], label="id measured")
        axes[0, axis_index].set_title(f"VSC{converter_index} d-axis tracking")
        axes[0, axis_index].set_ylabel("Current [pu]")
        axes[0, axis_index].legend(loc="best")

        axes[1, axis_index].plot(time_s, signals[f"vsc{converter_index}_i_q_ref"], "--", label="iq ref")
        axes[1, axis_index].plot(time_s, signals[f"vsc{converter_index}_i_q_meas_f"], label="iq measured")
        axes[1, axis_index].set_ylabel("Current [pu]")
        axes[1, axis_index].legend(loc="best")

        axes[2, axis_index].plot(time_s, signals[f"vsc{converter_index}_v_cmd_d"], label="vd command")
        axes[2, axis_index].plot(time_s, signals[f"vsc{converter_index}_v_conv_d"], alpha=0.7, label="vd switched")
        axes[2, axis_index].plot(time_s, signals[f"vsc{converter_index}_v_d_meas_f"], ":", label="vd bus")
        axes[2, axis_index].set_ylabel("Voltage [pu]")
        axes[2, axis_index].legend(loc="best")

        axes[3, axis_index].plot(time_s, signals[f"vsc{converter_index}_v_cmd_q"], label="vq command")
        axes[3, axis_index].plot(time_s, signals[f"vsc{converter_index}_v_conv_q"], alpha=0.7, label="vq switched")
        axes[3, axis_index].plot(time_s, signals[f"vsc{converter_index}_v_q_meas_f"], ":", label="vq bus")
        axes[3, axis_index].set_xlabel("Time [s]")
        axes[3, axis_index].set_ylabel("Voltage [pu]")
        axes[3, axis_index].legend(loc="best")

    for axis in axes.flat:
        axis.axvline(SWITCHING_HANDOVER_TIME_S, color="black", alpha=0.25, linewidth=1.0)
        axis.grid(True)
    figure.tight_layout()
    output_path = Path(__file__).with_name("hvdc_vdc_control_plots") / "hvdc_switching_control_diagnostics.png"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_path, dpi=150)
    plt.close(figure)


def build_uniquely_named_switched_converter(vf: VarFactory, name: str) -> EmtModelTemplate:
    """Build one switched converter with a delayed, system-unique PWM handover."""
    local_factory = VarFactory()
    template: EmtModelTemplate = get_switched_emt_converter(vf=local_factory, name=name)
    control1 = ConverterControlType.Vm_dc if name.startswith("vsc1") else ConverterControlType.Pdc
    control1_value = 1.0 if control1 == ConverterControlType.Vm_dc else 1.0e-6
    for parameter_name, value in (
            ("sbase", 1.0),
            ("omega_base", 2.0 * np.pi * 50.0),
            ("control1", converter_control_code(control1)),
            ("control2", converter_control_code(ConverterControlType.Qac)),
            ("control1_val", control1_value),
            ("control2_val", 0.0),
            ("R_eq", 0.04),
            ("L_eq", 1.5),
            ("t_enable_sw", SWITCHING_HANDOVER_TIME_S),
    ):
        template.block.set_parameter_in_model(parameter_name, value)
    procedural_variable_names: set[str] = set()
    for block in template.block.get_all_blocks():
        for logic in block.procedural_logic:
            for attribute_name in logic.__slots__:
                if attribute_name.endswith("_var_name"):
                    procedural_variable_names.add(getattr(logic, attribute_name))
                else:
                    pass
    renamed_variables: dict[str, str] = {}
    for variable in list(local_factory.get_vars_dict().values()) + list(local_factory.get_diff_var_dict().values()):
        old_name: str = variable.name
        if old_name in procedural_variable_names:
            new_name: str = f"{old_name}_{name}"
            renamed_variables[old_name] = new_name
            variable.set_name(new_name)
        else:
            pass
    for block in template.block.get_all_blocks():
        for logic in block.procedural_logic:
            for attribute_name in logic.__slots__:
                if attribute_name.endswith("_var_name"):
                    old_name = getattr(logic, attribute_name)
                    setattr(logic, attribute_name, renamed_variables.get(old_name, old_name))
                else:
                    pass
    vf.get_vars_dict().update(local_factory.get_vars_dict())
    vf.get_diff_var_dict().update(local_factory.get_diff_var_dict())
    vf.get_const_dict().update(local_factory.get_const_dict())
    vf.get_connections_dict().update(local_factory.get_connections_dict())
    return template


def run_emt_demo_upc(
        simulation_time_s: float = 0.09,
        time_step_s: float = 5.0e-5,
        plot: bool = True,
        integration_method: DynamicIntegrationMethod = DynamicIntegrationMethod.DaeTrapezoidal,
) -> dict[str, object]:
    """Run the two-terminal switched-GFL HVDC demonstration."""
    original_builder = hvdc_case.get_full_pseudo_emt_converter
    original_options_type = hvdc_case.EmtOptions
    original_set_emt_model = hvdc_case.set_emt_model
    original_solver_builder = hvdc_case.build_emt_solver
    built_solvers: list[object] = []

    def attach_per_unit_switched_model(device, model, var_factory):
        """Restore the filter and controller tuning designed for the switched plant."""
        if device.device_type == DeviceType.VscDevice:
            model.set_parameter_in_model("R_eq", 0.04)
            model.set_parameter_in_model("L_eq", 1.5)
            model.set_parameter_in_model("i_kp", 2.0)
            model.set_parameter_in_model("i_ki", 80.0)
        return original_set_emt_model(device, model, var_factory)

    def build_emt_options_with_robust_newton(**kwargs):
        kwargs["initialization_method"] = EmtInitializationMethod.Explicit
        options = original_options_type(**kwargs)
        options.init_newton_max_iter = 40
        options.init_newton_backtracking = True
        options.init_allow_state_equilibrium = True
        options.newton_max_iter = 40
        options.newton_enable_backtracking = True
        options.newton_enable_fallback = True
        return options

    def build_traced_solver(**kwargs):
        """Retain the solver so the demo can report failed switching substeps."""
        solver = original_solver_builder(**kwargs)
        built_solvers.append(solver)
        return solver

    hvdc_case.get_full_pseudo_emt_converter = build_uniquely_named_switched_converter
    hvdc_case.EmtOptions = build_emt_options_with_robust_newton
    hvdc_case.set_emt_model = attach_per_unit_switched_model
    hvdc_case.build_emt_solver = build_traced_solver
    try:
        results: dict[str, object] = hvdc_case.run_hvdc_vdc_control_simulation(
            simulation_time_s=simulation_time_s,
            time_step_s=time_step_s,
            solver_type=EmtSolverTypes.Symbolic,
            integration_method=integration_method,
            enable_vdc_reference_event=True,
            plot=plot,
            save_grid_filename=str(Path(__file__).with_name("emt_demo_upc.veragrid")),
        )
    finally:
        hvdc_case.get_full_pseudo_emt_converter = original_builder
        hvdc_case.EmtOptions = original_options_type
        hvdc_case.set_emt_model = original_set_emt_model
        hvdc_case.build_emt_solver = original_solver_builder
    trajectory = results["trajectory"]
    if not isinstance(trajectory, np.ndarray) or not np.all(np.isfinite(trajectory)):
        raise RuntimeError("The switched-GFL HVDC simulation produced a non-finite trajectory.")
    if built_solvers and hasattr(built_solvers[-1], "get_last_runtime_stats"):
        results["runtime_stats"] = built_solvers[-1].get_last_runtime_stats()
    else:
        results["runtime_stats"] = {}
    add_control_diagnostics(results=results, plot=plot)
    return results


def main() -> None:
    """Run the demo and print its basic solver status."""
    results: dict[str, object] = run_emt_demo_upc()
    print("UPC two-terminal switched-GFL HVDC EMT demo")
    print(f"power flow converged = {results['pf_results'].converged}")
    print(f"well initialized     = {results['well_initialized']}")
    print(f"EMT converged        = {results['converged']}")
    print(f"finite trajectory    = {bool(np.all(np.isfinite(results['trajectory'])))}")


if __name__ == "__main__":
    main()
