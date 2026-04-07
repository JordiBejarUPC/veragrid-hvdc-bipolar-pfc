from __future__ import annotations

from pathlib import Path
import json
import os
import shutil
import subprocess
import tempfile

from .config import ExportConfig, TargetPlatform
from .diff_to_c import render_discrete_derivative
from .expr_to_c import ExprToCVisitor
from .export_ir import EquationGroup, ExportModel, StorageSegment, VariableCategory
from .procedural_to_c import render_procedural_c
from .variable_map import CVariableResolver


def _template_root() -> Path:
    return Path(__file__).parent / "c_runtime" / "fmi2_template"


def ensure_build_layout(cfg: ExportConfig) -> tuple[Path, Path, Path]:
    root = cfg.build_dir or Path(tempfile.mkdtemp(prefix="veragrid_fmu_build_"))
    root.mkdir(parents=True, exist_ok=True)
    return root / "source", root / "build", (cfg.staging_dir or root / "staging")


def _copy_template_tree(destination: Path) -> None:
    shutil.copytree(_template_root(), destination, dirs_exist_ok=True)


def _detect_tool_bin_dir() -> Path | None:
    candidates = [
        shutil.which("cmake"),
        os.environ.get("CMAKE_ROOT"),
    ]
    for candidate in candidates:
        if candidate:
            path = Path(candidate)
            if path.is_file():
                return path.parent
            if path.is_dir() and (path / "cmake.exe").exists():
                return path

    known_dirs = [
        Path("C:/Program Files/DIgSILENT/PowerFactory 2025 SP4/MinGW/bin"),
        Path("C:/Program Files/CMake/bin"),
        Path("C:/msys64/mingw64/bin"),
        Path("C:/msys64/ucrt64/bin"),
    ]
    for directory in known_dirs:
        if (directory / "cmake.exe").exists() or (directory / "cmake").exists():
            return directory
    return None


def _toolchain_env() -> tuple[str, dict[str, str]]:
    env = os.environ.copy()

    # Optional explicit override
    cmake_override = os.environ.get("VG_CMAKE")
    if cmake_override:
        return cmake_override, env

    # Prefer the system installation already visible in PATH
    cmake_cmd = shutil.which("cmake")
    if cmake_cmd:
        return cmake_cmd, env

    # Fallback only if PATH does not provide cmake
    tool_dir = _detect_tool_bin_dir()
    if tool_dir is not None:
        if (tool_dir / "cmake.exe").exists():
            return str(tool_dir / "cmake.exe"), env
        if (tool_dir / "cmake").exists():
            return str(tool_dir / "cmake"), env

    return "cmake", env

def _detect_gcc() -> tuple[str | None, dict[str, str]]:
    env = os.environ.copy()

    # 1) Explicit override wins
    gcc_override = os.environ.get("VG_GCC")
    if gcc_override:
        return gcc_override, env

    # 2) Prefer the compiler already available in the system PATH
    gcc_cmd = shutil.which("gcc")
    if gcc_cmd:
        return gcc_cmd, env

    # 3) Explicit optional toolchain bin directory
    toolchain_bin = os.environ.get("VG_TOOLCHAIN_BIN")
    if toolchain_bin:
        tool_dir = Path(toolchain_bin)
        if (tool_dir / "gcc.exe").exists():
            return str(tool_dir / "gcc.exe"), env
        if (tool_dir / "gcc").exists():
            return str(tool_dir / "gcc"), env

    # 4) Fallback search only if nothing else was found
    candidate_dirs = [
        Path("C:/msys64/mingw64/bin"),
        Path("C:/msys64/ucrt64/bin"),
        Path("C:/Program Files/DIgSILENT/PowerFactory 2025 SP4/MinGW/bin"),
    ]
    for tool_dir in candidate_dirs:
        if (tool_dir / "gcc.exe").exists():
            return str(tool_dir / "gcc.exe"), env
        if (tool_dir / "gcc").exists():
            return str(tool_dir / "gcc"), env

    return None, env

def _direct_gcc_build(cfg: ExportConfig, source_dir: Path, build_dir: Path) -> Path:
    gcc_cmd, env = _detect_gcc()
    if gcc_cmd is None:
        raise FileNotFoundError("No usable gcc compiler was found for direct FMU runtime compilation")

    output_path = build_dir / cfg.library_name
    cmd = [
        gcc_cmd,
        "-shared",
        "-std=c99",
        "-O2",
        "-I",
        str(source_dir / "include"),
        "-I",
        str(source_dir / "src"),
        "-o",
        str(output_path),
        str(source_dir / "src" / "runtime_fmi2.c"),
        str(source_dir / "src" / "model_instance.c"),
        str(source_dir / "src" / "solver.c"),
        str(source_dir / "src" / "generated_model.c"),
        str(source_dir / "src" / "generated_procedural.c"),
        "-lm",
    ]
    subprocess.run(cmd, check=True, capture_output=True, text=True, env=env)
    if not output_path.exists():
        raise FileNotFoundError(f"Direct gcc build did not produce {output_path}")
    return output_path


def _write_text(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _json_compatible(value):
    if isinstance(value, dict):
        return {str(key): _json_compatible(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_compatible(item) for item in value]
    return value


def _sorted_variables(export_model: ExportModel, category: VariableCategory) -> list:
    return sorted(
        [variable for variable in export_model.variables if variable.category == category],
        key=lambda variable: variable.storage_index,
    )


def _storage_expr(segment: StorageSegment, index: int) -> str:
    if segment == StorageSegment.STATES:
        return f"instance->states[{index}]"
    if segment == StorageSegment.ALGEBRAICS:
        return f"instance->algebraics[{index}]"
    if segment == StorageSegment.INPUTS:
        return f"instance->inputs[{index}]"
    if segment == StorageSegment.CONST_PARAMS:
        return f"instance->const_params[{index}]"
    if segment == StorageSegment.RUNTIME_PARAMS:
        return f"instance->runtime_params[{index}]"
    raise ValueError(f"Unsupported storage segment: {segment}")


def render_generated_metadata_h(export_model: ExportModel, cfg: ExportConfig) -> str:
    logic_count = len(export_model.logic_entries)
    lines = [
        "#ifndef GENERATED_METADATA_H",
        "#define GENERATED_METADATA_H",
        "",
        f"#define VG_MODEL_NAME \"{export_model.model_name}\"",
        f"#define VG_MODEL_IDENTIFIER \"{export_model.model_identifier}\"",
        f"#define VG_MODEL_GUID \"{export_model.guid}\"",
        f"#define VG_NUM_STATES {export_model.counts.get('states', 0)}",
        f"#define VG_NUM_ALGEBRAICS {export_model.counts.get('algebraics', 0)}",
        f"#define VG_NUM_CONTINUOUS_VARS {export_model.counts.get('states', 0) + export_model.counts.get('algebraics', 0)}",
        f"#define VG_NUM_INPUTS {export_model.counts.get('inputs', 0)}",
        f"#define VG_NUM_CONST_PARAMS {export_model.counts.get('const_params', 0)}",
        f"#define VG_NUM_RUNTIME_PARAMS {export_model.counts.get('runtime_params', 0)}",
        f"#define VG_NUM_RESIDUALS {export_model.counts.get('states', 0) + export_model.counts.get('algebraics', 0)}",
        f"#define VG_FIXED_STEP {cfg.fixed_step:.17g}",
        f"#define VG_NEWTON_TOLERANCE {cfg.newton_tolerance:.17g}",
        f"#define VG_MAX_NEWTON_ITERATIONS {cfg.max_newton_iterations}",
        f"#define VG_LOGIC_ENTRY_COUNT {logic_count}",
        f"#define VG_LOGIC_REAL_SLOTS {logic_count * 5}",
        f"#define VG_LOGIC_INT_SLOTS {logic_count * 3}",
        "",
        "#endif",
        "",
    ]
    return "\n".join(lines)


def render_generated_model_h() -> str:
    return "\n".join(
        [
            "#ifndef GENERATED_MODEL_H",
            "#define GENERATED_MODEL_H",
            "",
            '#include "model_instance.h"',
            "",
            "double vg_heaviside(double x);",
            "double vg_safe_log(double x);",
            "double vg_safe_sqrt(double x);",
            "",
            "void generated_set_start_values(ModelInstance* instance);",
            "void generated_eval_init(ModelInstance* instance);",
            "void generated_eval_discrete_init(ModelInstance* instance);",
            "void generated_eval_residual(ModelInstance* instance, double* out);",
            "void generated_eval_outputs(ModelInstance* instance);",
            "double generated_procedural_next_event(ModelInstance* instance, double t_prev, double t_target);",
            "void generated_procedural_update(ModelInstance* instance, double t);",
            "int generated_get_real(ModelInstance* instance, fmi2ValueReference vr, double* value);",
            "int generated_set_real(ModelInstance* instance, fmi2ValueReference vr, double value);",
            "",
            "#endif",
            "",
        ]
    )


def _render_start_assignments(export_model: ExportModel) -> list[str]:
    lines: list[str] = []
    for variable in export_model.variables:
        if variable.category == VariableCategory.DIFF:
            continue
        if variable.start is None:
            continue
        lines.append(f"    {_storage_expr(variable.storage_segment, variable.storage_index)} = {variable.start:.17g};")
    if not lines:
        lines.append("    (void)instance;")
    return lines


def _render_runtime_init(export_model: ExportModel, visitor: ExprToCVisitor, resolver: CVariableResolver) -> list[str]:
    lines: list[str] = []
    for equation in export_model.equations:
        if equation.group != EquationGroup.RUNTIME_INIT or equation.target_uid is None:
            continue
        lines.append(f"    {resolver.resolve_target(equation.target_uid)} = {visitor.render(equation.expression)};")
    return lines


def _render_init_assignments(export_model: ExportModel, visitor: ExprToCVisitor, resolver: CVariableResolver) -> list[str]:
    lines = _render_runtime_init(export_model, visitor, resolver)
    for equation in export_model.equations:
        if equation.group != EquationGroup.INIT or equation.target_uid is None:
            continue
        lines.append(f"    {resolver.resolve_target(equation.target_uid)} = {visitor.render(equation.expression)};")
    if not lines:
        lines.append("    (void)instance;")
    return lines


def _render_diff_init_assignments(export_model: ExportModel, visitor: ExprToCVisitor) -> list[str]:
    lines: list[str] = []
    for equation in export_model.equations:
        if equation.group != EquationGroup.DIFF_INIT or equation.target_uid is None:
            continue
        diff_variable = export_model.variable_by_uid(equation.target_uid)
        base_uid = diff_variable.diff_base_uid
        if base_uid is None:
            continue
        base_variable = export_model.variable_by_uid(base_uid)
        if base_variable.history_index is None:
            continue
        lines.append(f"    instance->d_history[{base_variable.history_index}] = {visitor.render(equation.expression)};")
    if not lines:
        lines.append("    (void)instance;")
    return lines


def _render_residual_lines(export_model: ExportModel, cfg: ExportConfig, visitor: ExprToCVisitor, resolver: CVariableResolver) -> list[str]:
    lines: list[str] = []
    state_count = export_model.counts.get("states", 0)
    for equation in export_model.equations:
        if equation.group == EquationGroup.STATE and equation.target_uid is not None:
            variable = export_model.variable_by_uid(equation.target_uid)
            if variable.history_index is None:
                raise ValueError(f"State variable {variable.name!r} is missing history index")
            derivative = render_discrete_derivative(
                method=cfg.integration_method,
                state_expr=_storage_expr(StorageSegment.STATES, variable.storage_index),
                history_expr=f"instance->history[{variable.history_index}]",
                d_history_expr=f"instance->d_history[{variable.history_index}]",
                history2_expr=f"instance->history2[{variable.history_index}]",
                step_expr="instance->current_step_size",
            )
            lines.append(f"    out[{equation.index}] = ({derivative}) - ({visitor.render(equation.expression)});")
        elif equation.group == EquationGroup.ALGEBRAIC:
            lines.append(f"    out[{state_count + equation.index}] = {visitor.render(equation.expression)};")
    if not lines:
        lines.append("    (void)out;")
    return lines


def _render_get_real(export_model: ExportModel) -> list[str]:
    lines = ["    switch (vr) {"]
    for variable in sorted(export_model.exposed_variables(), key=lambda item: item.value_reference or -1):
        lines.extend(
            [
                f"        case {variable.value_reference}u:",
                f"            *value = {_storage_expr(variable.storage_segment, variable.storage_index)};",
                "            return 0;",
            ]
        )
    lines.extend(["        default:", "            return 1;", "    }"])
    return lines


def _render_set_real(export_model: ExportModel) -> list[str]:
    lines = ["    switch (vr) {"]
    for variable in sorted(export_model.exposed_variables(), key=lambda item: item.value_reference or -1):
        target = _storage_expr(variable.storage_segment, variable.storage_index)
        if variable.causality == "input" or variable.category == VariableCategory.RUNTIME_PARAM:
            lines.extend(
                [
                    f"        case {variable.value_reference}u:",
                    f"            {target} = value;",
                    "            return 0;",
                ]
            )
        elif variable.category == VariableCategory.CONST_PARAM:
            lines.extend(
                [
                    f"        case {variable.value_reference}u:",
                    "            if (instance->initialized) return 1;",
                    f"            {target} = value;",
                    "            return 0;",
                ]
            )
    lines.extend(["        default:", "            return 1;", "    }"])
    return lines


def render_generated_model_c(export_model: ExportModel, cfg: ExportConfig) -> str:
    resolver = CVariableResolver(export_model, cfg)
    visitor = ExprToCVisitor(resolver)
    residual_count = export_model.counts.get("states", 0) + export_model.counts.get("algebraics", 0)
    lines = [
        '#include "generated_model.h"',
        '#include "generated_metadata.h"',
        '#include "runtime_support.h"',
        "",
        "double vg_heaviside(double x) { return x > 0.0 ? 1.0 : 0.0; }",
        "double vg_safe_log(double x) { return log(x > 1e-300 ? x : 1e-300); }",
        "double vg_safe_sqrt(double x) { return sqrt(x >= 0.0 ? x : 0.0); }",
        "",
        "void generated_set_start_values(ModelInstance* instance) {",
        *_render_start_assignments(export_model),
        "}",
        "",
        "void generated_eval_init(ModelInstance* instance) {",
        *_render_init_assignments(export_model, visitor, resolver),
        "}",
        "",
        "void generated_eval_discrete_init(ModelInstance* instance) {",
        *_render_diff_init_assignments(export_model, visitor),
        "}",
        "",
        "void generated_eval_residual(ModelInstance* instance, double* out) {",
        f"    memset(out, 0, sizeof(double) * {residual_count});",
        *_render_residual_lines(export_model, cfg, visitor, resolver),
        "}",
        "",
        "void generated_eval_outputs(ModelInstance* instance) {",
        "    (void)instance;",
        "}",
        "",
        "int generated_get_real(ModelInstance* instance, fmi2ValueReference vr, double* value) {",
        *_render_get_real(export_model),
        "}",
        "",
        "int generated_set_real(ModelInstance* instance, fmi2ValueReference vr, double value) {",
        *_render_set_real(export_model),
        "}",
        "",
    ]
    return "\n".join(lines)


def emit_c_sources(export_model: ExportModel, cfg: ExportConfig, source_root: Path) -> None:
    _copy_template_tree(source_root)
    resolver = CVariableResolver(export_model, cfg)
    _write_text(source_root / "src" / "generated_metadata.h", render_generated_metadata_h(export_model, cfg))
    _write_text(source_root / "src" / "generated_model.h", render_generated_model_h())
    _write_text(source_root / "src" / "generated_model.c", render_generated_model_c(export_model, cfg))
    _write_text(source_root / "src" / "generated_procedural.c", render_procedural_c(export_model, resolver))


def write_debug_resources(export_model: ExportModel, cfg: ExportConfig, resources_dir: Path) -> None:
    if cfg.include_export_model_resource:
        _write_text(resources_dir / "export_model.json", json.dumps(_json_compatible(export_model.to_dict()), indent=2, sort_keys=True))
    if cfg.include_snapshot_resource:
        _write_text(resources_dir / "snapshot.json", json.dumps(_json_compatible(export_model.source_snapshot), indent=2, sort_keys=True))


def build_shared_library(cfg: ExportConfig, source_dir: Path, build_dir: Path) -> Path:
    build_dir.mkdir(parents=True, exist_ok=True)
    cmake_cmd, env = _toolchain_env()
    configure_cmd = [
        cmake_cmd,
        "-S",
        str(source_dir),
        "-B",
        str(build_dir),
        f"-DVG_MODEL_IDENTIFIER={cfg.model_identifier}",
    ]
    if cfg.target_platform == TargetPlatform.WIN64:
        cmake_generator = os.environ.get("VG_CMAKE_GENERATOR")
        if cmake_generator:
            configure_cmd.extend(["-G", cmake_generator])
        else:
            pass
    try:
        subprocess.run(
            configure_cmd,
            check=True,
            text=True,
            env=env,
        )
        subprocess.run(
            [cmake_cmd, "--build", str(build_dir), "--config", "Release"],
            check=True,
            text=True,
            env=env,
        )
        release_candidate = build_dir / "Release" / cfg.library_name
        if release_candidate.exists():
            return release_candidate
        direct_candidate = build_dir / cfg.library_name
        if direct_candidate.exists():
            return direct_candidate
        matches = list(build_dir.rglob(cfg.library_name))
        if matches:
            return matches[0]
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    return _direct_gcc_build(cfg, source_dir, build_dir)
