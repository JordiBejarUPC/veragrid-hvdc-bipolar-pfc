from __future__ import annotations

import importlib
import pkgutil
import re
from functools import lru_cache
from pathlib import Path
from types import ModuleType
from typing import Sequence

from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Const
from VeraGridEngine.Utils.Symbolic.symbolic import Var


class PowerFactoryBasicCatalogTables:
    """
    Immutable semantic tables used to classify and expose the shipped catalog.
    """

    __slots__ = (
        "_pending_template_reason",
        "_category_lookup_arrays_and_matrices",
        "_category_transforms_clarke_park_dq0",
        "_category_transforms_rms_and_sequence",
        "_category_complex_operations",
        "_category_waveforms_signal_generators",
        "_category_waveforms_time_sources",
        "_category_mechanical_drive_train",
        "_category_math_constants_and_scaling",
        "_category_control_measurements_and_units",
        "_category_control_controllers",
        "_category_logic_comparators",
        "_category_logic_gates_and_memory",
        "_category_logic_switching_and_selection",
        "_category_logic_timers_and_enables",
        "_category_limits_limiters",
        "_category_limits_deadbands_and_rate_limiters",
        "_category_continuous_delays_and_memory",
        "_category_continuous_integrators_and_derivatives",
        "_category_continuous_transfer_functions_and_filters",
        "_category_math_scaling_and_products",
        "_category_math_elementary_functions",
        "_category_misc_other",
        "_display_names_rms_and_sequence",
        "_display_names_time_sources",
        "_display_names_constants_and_scaling",
        "_display_names_elementary_functions",
    )

    def __init__(self) -> None:
        """
        Build the immutable semantic tables used by the catalog.

        :returns: None.
        """
        self._pending_template_reason: str = "template_has_no_executable_content"
        self._category_lookup_arrays_and_matrices: tuple[str, str, str] = ("Native", "Lookup and Tables", "Arrays and Matrices")
        self._category_transforms_clarke_park_dq0: tuple[str, str, str] = ("Native", "Transforms", "Clarke, Park and dq0")
        self._category_transforms_rms_and_sequence: tuple[str, str, str] = ("Native", "Transforms", "RMS and Sequence")
        self._category_complex_operations: tuple[str, str, str] = ("Native", "Complex", "Operations")
        self._category_waveforms_signal_generators: tuple[str, str, str] = ("Native", "Waveforms and Time", "Signal Generators")
        self._category_waveforms_time_sources: tuple[str, str, str] = ("Native", "Waveforms and Time", "Time Sources and Timers")
        self._category_mechanical_drive_train: tuple[str, str, str] = ("Native", "Mechanical", "Drive Train")
        self._category_math_constants_and_scaling: tuple[str, str, str] = ("Native", "Math and Functions", "Constants and Scaling")
        self._category_control_measurements_and_units: tuple[str, str, str] = ("Native", "Control and Measurement", "Measurements and Units")
        self._category_control_controllers: tuple[str, str, str] = ("Native", "Control and Measurement", "Controllers")
        self._category_logic_comparators: tuple[str, str, str] = ("Native", "Logic and Events", "Comparators")
        self._category_logic_gates_and_memory: tuple[str, str, str] = ("Native", "Logic and Events", "Gates and Memory")
        self._category_logic_switching_and_selection: tuple[str, str, str] = ("Native", "Logic and Events", "Switching and Selection")
        self._category_logic_timers_and_enables: tuple[str, str, str] = ("Native", "Logic and Events", "Timers and Enables")
        self._category_limits_limiters: tuple[str, str, str] = ("Native", "Limits and Nonlinearities", "Limiters")
        self._category_limits_deadbands_and_rate_limiters: tuple[str, str, str] = ("Native", "Limits and Nonlinearities", "Deadbands and Rate Limiters")
        self._category_continuous_delays_and_memory: tuple[str, str, str] = ("Native", "Continuous", "Delays and Memory")
        self._category_continuous_integrators_and_derivatives: tuple[str, str, str] = ("Native", "Continuous", "Integrators and Derivatives")
        self._category_continuous_transfer_functions_and_filters: tuple[str, str, str] = ("Native", "Continuous", "Transfer Functions and Filters")
        self._category_math_scaling_and_products: tuple[str, str, str] = ("Native", "Math and Functions", "Scaling and Products")
        self._category_math_elementary_functions: tuple[str, str, str] = ("Native", "Math and Functions", "Elementary Functions")
        self._category_misc_other: tuple[str, str, str] = ("Native", "Miscellaneous", "Other")
        self._display_names_rms_and_sequence: tuple[str, ...] = ("rms", "balanced")
        self._display_names_time_sources: tuple[str, ...] = ("time",)
        self._display_names_constants_and_scaling: tuple[str, ...] = (
            "0",
            "1",
            "c",
            "e",
            "-c",
            "pi",
            "pi/2",
            "2pi",
            "1/sqrt2",
            "1/sqrt3",
            "sqrt2",
            "sqrt3",
            "sqrt(2/3)",
            "sqrt(3/2)",
            "sqrt(c1/c2)",
            "c1/c2",
        )
        self._display_names_elementary_functions: tuple[str, ...] = (
            "abs",
            "ceil",
            "equal",
            "exp",
            "floor",
            "frac",
            "ln",
            "log",
            "max2",
            "max3",
            "max4",
            "min2",
            "min3",
            "min4",
            "modulo",
            "reciprocal",
            "reciprocal (feedback)",
            "round",
            "sign",
            "sin",
            "sind",
            "sinh",
            "sinhd",
            "cos",
            "cosd",
            "cosh",
            "coshd",
            "tan",
            "tand",
            "tanh",
            "tanhd",
            "sqrt",
            "x^2",
            "x^p",
            "acos",
            "asin",
            "atan",
            "atan2",
            "atan2d",
            "atand",
        )

    def get_pending_template_reason(self) -> str:
        """
        Return the canonical pending reason for non-executable catalog templates.

        :returns: Pending reason.
        """
        return self._pending_template_reason

    def get_category_lookup_arrays_and_matrices(self) -> tuple[str, str, str]:
        """
        Return the lookup-array category path.

        :returns: Category path.
        """
        return self._category_lookup_arrays_and_matrices

    def get_category_transforms_clarke_park_dq0(self) -> tuple[str, str, str]:
        """
        Return the Clarke/Park category path.

        :returns: Category path.
        """
        return self._category_transforms_clarke_park_dq0

    def get_category_transforms_rms_and_sequence(self) -> tuple[str, str, str]:
        """
        Return the RMS/sequence category path.

        :returns: Category path.
        """
        return self._category_transforms_rms_and_sequence

    def get_category_complex_operations(self) -> tuple[str, str, str]:
        """
        Return the complex-operations category path.

        :returns: Category path.
        """
        return self._category_complex_operations

    def get_category_waveforms_signal_generators(self) -> tuple[str, str, str]:
        """
        Return the signal-generator category path.

        :returns: Category path.
        """
        return self._category_waveforms_signal_generators

    def get_category_waveforms_time_sources(self) -> tuple[str, str, str]:
        """
        Return the time-source category path.

        :returns: Category path.
        """
        return self._category_waveforms_time_sources

    def get_category_mechanical_drive_train(self) -> tuple[str, str, str]:
        """
        Return the drive-train category path.

        :returns: Category path.
        """
        return self._category_mechanical_drive_train

    def get_category_math_constants_and_scaling(self) -> tuple[str, str, str]:
        """
        Return the constants-and-scaling category path.

        :returns: Category path.
        """
        return self._category_math_constants_and_scaling

    def get_category_control_measurements_and_units(self) -> tuple[str, str, str]:
        """
        Return the measurements-and-units category path.

        :returns: Category path.
        """
        return self._category_control_measurements_and_units

    def get_category_control_controllers(self) -> tuple[str, str, str]:
        """
        Return the controllers category path.

        :returns: Category path.
        """
        return self._category_control_controllers

    def get_category_logic_comparators(self) -> tuple[str, str, str]:
        """
        Return the comparators category path.

        :returns: Category path.
        """
        return self._category_logic_comparators

    def get_category_logic_gates_and_memory(self) -> tuple[str, str, str]:
        """
        Return the gates-and-memory category path.

        :returns: Category path.
        """
        return self._category_logic_gates_and_memory

    def get_category_logic_switching_and_selection(self) -> tuple[str, str, str]:
        """
        Return the switching-and-selection category path.

        :returns: Category path.
        """
        return self._category_logic_switching_and_selection

    def get_category_logic_timers_and_enables(self) -> tuple[str, str, str]:
        """
        Return the timers-and-enables category path.

        :returns: Category path.
        """
        return self._category_logic_timers_and_enables

    def get_category_limits_limiters(self) -> tuple[str, str, str]:
        """
        Return the limiters category path.

        :returns: Category path.
        """
        return self._category_limits_limiters

    def get_category_limits_deadbands_and_rate_limiters(self) -> tuple[str, str, str]:
        """
        Return the deadbands-and-rate-limiters category path.

        :returns: Category path.
        """
        return self._category_limits_deadbands_and_rate_limiters

    def get_category_continuous_delays_and_memory(self) -> tuple[str, str, str]:
        """
        Return the delays-and-memory category path.

        :returns: Category path.
        """
        return self._category_continuous_delays_and_memory

    def get_category_continuous_integrators_and_derivatives(self) -> tuple[str, str, str]:
        """
        Return the integrators-and-derivatives category path.

        :returns: Category path.
        """
        return self._category_continuous_integrators_and_derivatives

    def get_category_continuous_transfer_functions_and_filters(self) -> tuple[str, str, str]:
        """
        Return the transfer-functions-and-filters category path.

        :returns: Category path.
        """
        return self._category_continuous_transfer_functions_and_filters

    def get_category_math_scaling_and_products(self) -> tuple[str, str, str]:
        """
        Return the scaling-and-products category path.

        :returns: Category path.
        """
        return self._category_math_scaling_and_products

    def get_category_math_elementary_functions(self) -> tuple[str, str, str]:
        """
        Return the elementary-functions category path.

        :returns: Category path.
        """
        return self._category_math_elementary_functions

    def get_category_misc_other(self) -> tuple[str, str, str]:
        """
        Return the fallback category path.

        :returns: Category path.
        """
        return self._category_misc_other

    def get_display_names_rms_and_sequence(self) -> tuple[str, ...]:
        """
        Return the display names mapped to the RMS/sequence category.

        :returns: Display-name tuple.
        """
        return self._display_names_rms_and_sequence

    def get_display_names_time_sources(self) -> tuple[str, ...]:
        """
        Return the display names mapped to the time-source category.

        :returns: Display-name tuple.
        """
        return self._display_names_time_sources

    def get_display_names_constants_and_scaling(self) -> tuple[str, ...]:
        """
        Return the display names mapped to the constants-and-scaling category.

        :returns: Display-name tuple.
        """
        return self._display_names_constants_and_scaling

    def get_display_names_elementary_functions(self) -> tuple[str, ...]:
        """
        Return the display names mapped to the elementary-functions category.

        :returns: Display-name tuple.
        """
        return self._display_names_elementary_functions


@lru_cache(maxsize=1)
def build_powerfactory_basic_catalog_tables() -> PowerFactoryBasicCatalogTables:
    """
    Build the immutable semantic tables used by the shipped catalog.

    :returns: Cached semantic tables.
    """
    return PowerFactoryBasicCatalogTables()


def get_powerfactory_basic_catalog_pending_template_reason() -> str:
    """
    Return the canonical pending reason for non-executable catalog templates.

    :returns: Pending reason.
    """
    tables: PowerFactoryBasicCatalogTables = build_powerfactory_basic_catalog_tables()
    return tables.get_pending_template_reason()


class PowerFactoryBasicTemplateDescriptor:
    """
    Explicit, typed description of one shipped catalog template.
    """

    __slots__ = (
        "_template_key",
        "_blkdef_name",
        "_sample_display_name",
        "_display_label",
        "_category_path",
        "_inputs",
        "_outputs",
        "_states",
        "_params",
        "_unsupported_lines",
        "_module_name",
        "_module_filename",
    )

    def __init__(
        self,
        template_key: str,
        blkdef_name: str,
        sample_display_name: str,
        display_label: str,
        category_path: Sequence[str],
        inputs: Sequence[str],
        outputs: Sequence[str],
        states: Sequence[str],
        params: Sequence[str],
        unsupported_lines: Sequence[str],
        module_name: str,
        module_filename: str,
    ) -> None:
        """
        Store one immutable catalog descriptor.

        :param template_key: Stable semantic lookup key.
        :param blkdef_name: Raw source block name.
        :param sample_display_name: Clean human-facing source name.
        :param display_label: Unique label exposed in the editor.
        :param category_path: Full editor category path.
        :param inputs: Input names.
        :param outputs: Output names.
        :param states: State names.
        :param params: Runtime parameter names.
        :param unsupported_lines: Pending-reason markers for non editor-ready templates.
        :param module_name: Python module stem inside the standalone package.
        :param module_filename: Python filename inside the standalone package.
        :returns: None.
        """
        self._template_key = template_key
        self._blkdef_name = blkdef_name
        self._sample_display_name = sample_display_name
        self._display_label = display_label
        self._category_path = category_path
        self._inputs = inputs
        self._outputs = outputs
        self._states = states
        self._params = params
        self._unsupported_lines = unsupported_lines
        self._module_name = module_name
        self._module_filename = module_filename

    @property
    def template_key(self) -> str:
        """
        Return the stable semantic lookup key.

        :returns: Template lookup key.
        """
        return self._template_key

    @property
    def blkdef_name(self) -> str:
        """
        Return the raw imported block name.

        :returns: Raw block name.
        """
        return self._blkdef_name

    @property
    def sample_display_name(self) -> str:
        """
        Return the clean display name derived from the shipped module.

        :returns: Clean source name.
        """
        return self._sample_display_name

    @property
    def display_label(self) -> str:
        """
        Return the unique label exposed by the editor.

        :returns: Unique label.
        """
        return self._display_label

    @property
    def category_path(self) -> Sequence[str]:
        """
        Return the full library category path.

        :returns: Category path.
        """
        return self._category_path

    @property
    def inputs(self) -> Sequence[str]:
        """
        Return the input names.

        :returns: Input-name tuple.
        """
        return self._inputs

    @property
    def outputs(self) -> Sequence[str]:
        """
        Return the output names.

        :returns: Output-name tuple.
        """
        return self._outputs

    @property
    def states(self) -> Sequence[str]:
        """
        Return the state names.

        :returns: State-name tuple.
        """
        return self._states

    @property
    def params(self) -> Sequence[str]:
        """
        Return the runtime parameter names.

        :returns: Parameter-name tuple.
        """
        return self._params

    @property
    def unsupported_lines(self) -> Sequence[str]:
        """
        Return the pending markers for non editor-ready templates.

        :returns: Unsupported marker tuple.
        """
        return self._unsupported_lines

    @property
    def module_name(self) -> str:
        """
        Return the standalone Python module stem.

        :returns: Module stem.
        """
        return self._module_name

    @property
    def module_filename(self) -> str:
        """
        Return the standalone Python filename.

        :returns: Module filename.
        """
        return self._module_filename

    @property
    def is_editor_ready(self) -> bool:
        """
        Return whether the template can be exposed in the editor.

        :returns: ``True`` when the template has executable content.
        """
        if len(self._unsupported_lines) == 0:
            return True
        else:
            return False

    @property
    def search_text(self) -> str:
        """
        Build the normalized search text used by the editor filter.

        :returns: Search text.
        """
        tokens: list[str] = list()

        # The search index mixes every stable human-facing field so one filter can
        # match category, source name, semantic key, or the imported provenance id.
        tokens.append(self._display_label)
        tokens.append(self._blkdef_name)
        tokens.append(self._sample_display_name)
        tokens.append(self._template_key)

        category_name: str
        for category_name in self._category_path:
            tokens.append(category_name)

        return " ".join(tokens).strip()


class _DescriptorSeed:
    """
    Internal typed seed used before duplicate labels are resolved.
    """

    __slots__ = (
        "template_key",
        "typ_id",
        "blkdef_name",
        "sample_display_name",
        "base_label",
        "inputs",
        "outputs",
        "states",
        "params",
        "flags",
        "unsupported_lines",
        "module_name",
        "module_filename",
    )

    def __init__(
        self,
        template_key: str,
        typ_id: str,
        blkdef_name: str,
        sample_display_name: str,
        base_label: str,
        inputs: Sequence[str],
        outputs: Sequence[str],
        states: Sequence[str],
        params: Sequence[str],
        flags: Sequence[str],
        unsupported_lines: Sequence[str],
        module_name: str,
        module_filename: str,
    ) -> None:
        """
        Store the pre-label-resolution seed for one template.

        :param template_key: Stable semantic lookup key.
        :param typ_id: Imported PowerFactory type identifier.
        :param blkdef_name: Raw imported block name.
        :param sample_display_name: Clean source name.
        :param base_label: Humanized base label before deduplication.
        :param inputs: Input names.
        :param outputs: Output names.
        :param states: State names.
        :param params: Parameter names.
        :param flags: Visible qualifier flags extracted from the source name.
        :param unsupported_lines: Pending markers.
        :param module_name: Standalone module stem.
        :param module_filename: Standalone module filename.
        :returns: None.
        """
        self.template_key = template_key
        self.typ_id = typ_id
        self.blkdef_name = blkdef_name
        self.sample_display_name = sample_display_name
        self.base_label = base_label
        self.inputs = inputs
        self.outputs = outputs
        self.states = states
        self.params = params
        self.flags = flags
        self.unsupported_lines = unsupported_lines
        self.module_name = module_name
        self.module_filename = module_filename


def get_powerfactory_basic_catalog_root() -> Path:
    """
    Return the directory containing the shipped PowerFactory-derived catalog.

    :returns: Catalog root directory.
    """
    return Path(__file__).resolve().parent


def get_powerfactory_basic_catalog_templates_dir() -> Path:
    """
    Return the directory with the shipped standalone template modules.

    :returns: Standalone-template directory.
    """
    return get_powerfactory_basic_catalog_root() / "standalone_templates"


def _get_powerfactory_basic_catalog_templates_package_name() -> str:
    """
    Return the package name that hosts the shipped standalone template modules.

    :returns: Absolute package name.
    """
    return "VeraGridEngine.Templates.catalog.powerfactory_basic_catalog.standalone_templates"


def _module_name_sort_key(module_name: str) -> tuple[int, str]:
    """
    Build the deterministic sort key for one standalone module name.

    :param module_name: Standalone module stem.
    :returns: Sort key ordered by typ_id and module name.
    """
    typ_id_text: str = _extract_typ_id_from_module_name(module_name)
    return int(typ_id_text), module_name


def _descriptor_sort_key(descriptor: PowerFactoryBasicTemplateDescriptor) -> tuple[int, str]:
    """
    Build the deterministic sort key for one descriptor.

    :param descriptor: Catalog descriptor.
    :returns: Sort key ordered by module name and template key.
    """
    return _module_name_sort_key(descriptor.module_name)


def _extract_typ_id_from_module_name(module_name: str) -> str:
    """
    Extract the imported type identifier from one module stem.

    :param module_name: Standalone module stem.
    :returns: Imported type identifier.
    :raises ValueError: Raised when the module stem does not follow the shipped naming scheme.
    """
    match_obj: re.Match[str] | None = re.fullmatch(r"typ_(\d+)__.+", module_name)

    if match_obj is None:
        raise ValueError(f"Unexpected standalone template module name '{module_name}'")
    else:
        return match_obj.group(1)


def _extract_slug_from_module_name(module_name: str) -> str:
    """
    Extract the semantic slug from one module stem.

    :param module_name: Standalone module stem.
    :returns: Semantic slug.
    :raises ValueError: Raised when the module stem does not follow the shipped naming scheme.
    """
    match_obj: re.Match[str] | None = re.fullmatch(r"typ_\d+__(.+)", module_name)

    if match_obj is None:
        raise ValueError(f"Unexpected standalone template module name '{module_name}'")
    else:
        return match_obj.group(1)


def _build_slug_counts(module_names: Sequence[str]) -> dict[str, int]:
    """
    Count how many standalone modules share the same semantic slug.

    :param module_names: Standalone module stems.
    :returns: Occurrence count by slug.
    """
    slug_counts: dict[str, int] = dict()
    module_name: str

    # The first pass identifies duplicate semantic slugs so the final public keys
    # can stay readable while still remaining unique.
    for module_name in module_names:
        slug: str = _extract_slug_from_module_name(module_name)
        current_count: int = slug_counts.get(slug, 0)
        slug_counts[slug] = current_count + 1

    return slug_counts


def _build_key_variant_suffix(index: int) -> str:
    """
    Build the semantic suffix used by duplicate template keys.

    :param index: Zero-based duplicate index.
    :returns: Semantic duplicate suffix.
    """
    return _variant_form_label(index).lower().replace(" ", "_")


def _build_template_keys(module_names: Sequence[str]) -> dict[str, str]:
    """
    Build the stable semantic key for every standalone module.

    :param module_names: Standalone module stems.
    :returns: Public key by module name.
    """
    slug_counts: dict[str, int] = _build_slug_counts(module_names)
    grouped_module_names: dict[str, list[str]] = dict()
    module_name_to_key: dict[str, str] = dict()
    module_name: str

    for module_name in module_names:
        slug: str = _extract_slug_from_module_name(module_name)
        grouped_modules: list[str] | None = grouped_module_names.get(slug, None)
        if grouped_modules is None:
            grouped_modules = list()
            grouped_module_names[slug] = grouped_modules
        else:
            pass
        grouped_modules.append(module_name)

    slug: str
    grouped_modules: list[str]
    for slug, grouped_modules in grouped_module_names.items():
        if slug_counts[slug] == 1:
            module_name_to_key[grouped_modules[0]] = slug
        else:
            index: int
            grouped_module_name: str
            for index, grouped_module_name in enumerate(grouped_modules):
                module_name_to_key[grouped_module_name] = f"{slug}_{_build_key_variant_suffix(index)}"

    return module_name_to_key


def _build_import_path_from_module_name(module_name: str) -> str:
    """
    Build the absolute import path for one shipped standalone module.

    :param module_name: Standalone module stem.
    :returns: Absolute import path.
    """
    package_name: str = _get_powerfactory_basic_catalog_templates_package_name()
    return f"{package_name}.{module_name}"


def _sanitize_template_name(raw_name: str) -> str:
    """
    Remove the imported typ_id suffix from one generated template name.

    :param raw_name: Generated template name.
    :returns: Clean source name.
    """
    sanitized_name: str = re.sub(r"__\d+$", "", raw_name).strip()

    if len(sanitized_name) > 0:
        return sanitized_name
    else:
        return raw_name.strip()


def _extract_surface_name(var_obj: Var, template_name: str) -> str:
    """
    Extract the logical surface name from one generated variable name.

    :param var_obj: Generated variable.
    :param template_name: Generated template name.
    :returns: Logical surface name.
    """
    suffix: str = f"_{template_name}"
    var_name: str = var_obj.name

    if var_name.endswith(suffix):
        return var_name[: -len(suffix)]
    else:
        return var_name


def _extract_surface_names(vars_list: list[Var], template_name: str) -> Sequence[str]:
    """
    Extract the logical names from one generated variable list.

    :param vars_list: Generated variable list.
    :param template_name: Generated template name.
    :returns: Logical-name tuple.
    """
    names: list[str] = list()
    var_obj: Var

    # The generated modules suffix every public variable with the template name.
    # Stripping that suffix reconstructs the original logical surface names.
    for var_obj in vars_list:
        names.append(_extract_surface_name(var_obj, template_name))

    return tuple(names)


def _extract_parameter_names(block: Block) -> Sequence[str]:
    """
    Extract the logical parameter names from one materialized block.

    :param block: Materialized symbolic block.
    :returns: Parameter-name tuple.
    """
    names: list[str] = list()
    const_obj: Const

    # The generated templates store user-facing runtime parameter names inside the
    # bound constants of ``event_dict``. The plain ``parameters`` mapping is kept as
    # a fallback so hand-written modules can still participate in the same API.
    for const_obj in block.event_dict.values():
        if isinstance(const_obj, Const):
            if isinstance(const_obj.name, str) and len(const_obj.name) > 0:
                if const_obj.name not in names:
                    names.append(const_obj.name)
                else:
                    pass
            else:
                pass
        else:
            pass

    parameter_var: Var
    for parameter_var in block.parameters.keys():
        parameter_name: str = parameter_var.name
        if parameter_name not in names:
            names.append(parameter_name)
        else:
            pass

    return tuple(names)


def _has_block_equations(block: Block) -> bool:
    """
    Return whether one block carries direct executable content.

    :param block: Symbolic block.
    :returns: ``True`` when the block owns equations, initialization logic, or procedural logic.
    """
    if len(block.state_eqs) > 0:
        return True
    elif len(block.algebraic_eqs) > 0:
        return True
    elif len(block.init_eqs) > 0:
        return True
    elif len(block.diff_init_eqs) > 0:
        return True
    elif len(block.procedural_logic) > 0:
        return True
    else:
        return False


def _has_executable_content(block: Block) -> bool:
    """
    Return whether one block or any child block carries executable content.

    :param block: Symbolic block.
    :returns: ``True`` when the template is executable in the editor.
    """
    if _has_block_equations(block):
        return True
    else:
        pass

    child_block: Block
    for child_block in block.children:
        if _has_executable_content(child_block):
            return True
        else:
            pass

    return False


def _import_template_module_from_module_name(module_name: str) -> ModuleType:
    """
    Import one shipped standalone module from its stem.

    :param module_name: Standalone module stem.
    :returns: Imported standalone module.
    """
    import_path: str = _build_import_path_from_module_name(module_name)
    imported_module: ModuleType = importlib.import_module(import_path)
    return imported_module


def _build_template_from_imported_module(imported_module: ModuleType,
                                         var_factory: VarFactory,
                                         name: str | None = None) -> EmtModelTemplate:
    """
    Build one EMT template instance from one imported standalone module.

    :param imported_module: Imported standalone module.
    :param var_factory: Variable factory for the new instance.
    :param name: Optional explicit template instance name.
    :returns: Materialized EMT template.
    :raises TypeError: Raised when the imported module does not expose a valid ``get_template`` function.
    """
    template_builder_obj: object | None = imported_module.__dict__.get("get_template", None)

    if callable(template_builder_obj):
        template_obj: object = template_builder_obj(vf=var_factory, name=name)
        if isinstance(template_obj, EmtModelTemplate):
            return template_obj
        else:
            raise TypeError("The imported standalone catalog module returned an invalid template object")
    else:
        raise TypeError("The imported standalone catalog module does not expose get_template()")


def _build_module_names() -> Sequence[str]:
    """
    Discover the shipped standalone module stems.

    :returns: Sorted standalone module stems.
    """
    templates_dir: Path = get_powerfactory_basic_catalog_templates_dir()
    module_info_list: list[pkgutil.ModuleInfo] = list(pkgutil.iter_modules([str(templates_dir)]))
    module_names: list[str] = list()
    module_info: pkgutil.ModuleInfo

    # The catalog is now built directly from the shipped Python modules, so the
    # repository no longer needs a secondary manifest snapshot to describe them.
    for module_info in module_info_list:
        if module_info.ispkg:
            pass
        else:
            if module_info.name.startswith("typ_"):
                module_names.append(module_info.name)
            else:
                pass

    module_names.sort(key=_module_name_sort_key)
    return tuple(module_names)


def _format_count_label(count: int, singular: str, plural: str) -> str:
    """
    Format one count suffix for duplicate label disambiguation.

    :param count: Item count.
    :param singular: Singular label.
    :param plural: Plural label.
    :returns: Humanized count label.
    """
    if count == 1:
        return f"1 {singular}"
    else:
        return f"{count} {plural}"


def _compact_name_list(names: Sequence[str]) -> str:
    """
    Compact one list of names into a short user-facing summary.

    :param names: Name tuple.
    :returns: Short summary label.
    """
    if len(names) == 0:
        return ""
    elif len(names) <= 3:
        return "/".join(names)
    else:
        return f"{'/'.join(names[:3])}+{len(names) - 3}"


def _build_name_signature(names: Sequence[str]) -> str:
    """
    Build one stable hashable signature for a name sequence.

    :param names: Name sequence.
    :returns: Stable signature text.
    """
    return "\x1f".join(names)


def _variant_form_label(index: int) -> str:
    """
    Convert one duplicate index into a short alphabetic form label.

    :param index: Zero-based duplicate index.
    :returns: Alphabetic form label.
    """
    working_index: int = index + 1
    label: str = ""

    while working_index > 0:
        quotient: int
        remainder: int
        quotient, remainder = divmod(working_index - 1, 26)
        label = chr(ord("A") + remainder) + label
        working_index = quotient

    return f"form {label}"


def _extract_label_flags(blkdef_name: str) -> Sequence[str]:
    """
    Extract visible qualifiers that help distinguish duplicate catalog labels.

    :param blkdef_name: Raw imported block name.
    :returns: Qualifier tuple.
    """
    source: str = blkdef_name.lower()
    flags: list[str] = list()
    ordered_flags: list[tuple[str, str]] = list([
        ("_rst_sig_hold", "reset signal hold"),
        ("_rst_hold", "reset hold"),
        ("_rst_sig", "reset signal"),
        ("_reset_sig", "reset signal"),
        ("_reset", "reset"),
        ("_enable", "enable"),
        ("_hold", "hold"),
        ("_bypass", "bypass"),
        ("_fb", "feedback"),
        ("_incfreeze", "freeze"),
        ("_incforward", "forward increment"),
        ("_incbackward", "backward increment"),
        ("_par", "parameter"),
        ("_sig", "signal"),
        ("_ip", "pulse"),
        ("const", "constant"),
        ("fixed", "fixed"),
        ("complex", "complex"),
        ("lower", "lower"),
        ("upper", "upper"),
        ("prio", "priority"),
        ("eps", "epsilon"),
    ])
    token: str
    label: str

    for token, label in ordered_flags:
        if token in source and label not in flags:
            flags.append(label)
        else:
            pass

    return tuple(flags)


def _humanize_catalog_label(blkdef_name: str) -> str:
    """
    Build one user-facing label without exposing internal typ_id suffixes.

    :param blkdef_name: Raw imported block name.
    :returns: Humanized label.
    """
    label: str = blkdef_name.strip()
    shorthand_replacements: list[tuple[str, str]] = list([
        ("[(pp", " (2 parameter inputs)"),
        ("[(p", " (parameter input)"),
        (" [ppp", " (3 parameter inputs)"),
        (" [sp", " (signal + parameter input)"),
        (" [p]", " (parameter)"),
        (" [s]", " (signal)"),
        (" [p", " (parameter)"),
        (" [s", " (signal)"),
        (" {p}", " (parameter)"),
        (" {p", " (parameter)"),
        (" {s}", " (signal)"),
        (" {s", " (signal)"),
    ])
    qualifier_replacements: list[tuple[str, str]] = list([
        (" _rst_sig_hold", " (reset signal hold)"),
        (" _rst_hold", " (reset hold)"),
        (" _rst_sig", " (reset signal)"),
        (" _reset_sig", " (reset signal)"),
        (" _reset", " (reset)"),
        (" _enable", " (enable)"),
        (" _hold", " (hold)"),
        (" _bypass", " (bypass)"),
        (" _fb", " (feedback)"),
        (" _incfreeze", " (freeze)"),
        (" _incforward", " (forward increment)"),
        (" _incbackward", " (backward increment)"),
        (" _par", " (parameter)"),
        (" _sig", " (signal)"),
        (" _ip", " (pulse)"),
    ])
    exact_overrides: dict[str, str] = dict()
    old_text: str
    new_text: str

    # These replacements only apply to the compact input markers, not to normal
    # words such as ``spline``. The regex keeps the shorthand expansion precise.
    label = re.sub(r" \(pp(?![A-Za-z])", " (2 parameter inputs)", label)
    label = re.sub(r" \(p\)", " (parameter)", label)
    label = re.sub(r" \(s\)", " (signal)", label)
    label = re.sub(r" \(p(?![A-Za-z])", " (parameter input)", label)
    label = re.sub(r" \(s(?![A-Za-z])", " (signal input)", label)

    exact_overrides["aflipflop"] = "Analog flip-flop"
    exact_overrides["flipflop"] = "Flip-flop"
    exact_overrides["EOR"] = "XOR"
    exact_overrides["2 out of 3"] = "2-out-of-3"
    exact_overrides["2 out of 3 (pulse)"] = "2-out-of-3 (pulse)"
    exact_overrides["selfix"] = "Set if condition"
    exact_overrides["selfix const"] = "Set if condition (constant)"
    exact_overrides["select"] = "Selector"
    exact_overrides["select const"] = "Selector (constant)"
    exact_overrides["lastvalue"] = "Last value"
    exact_overrides["movingavg"] = "Moving average"
    exact_overrides["gradlim const"] = "Gradient limiter (constant)"
    exact_overrides["picdro"] = "PI droop"
    exact_overrides["picdro const"] = "PI droop (constant)"
    exact_overrides["RECIPROCAL"] = "Reciprocal"
    exact_overrides["RECIPROCAL (feedback)"] = "Reciprocal (feedback)"
    exact_overrides["EDGE DETECT"] = "Edge detector"
    exact_overrides["Invert Logic"] = "Invert logic"
    exact_overrides["Equal"] = "Equal"

    for old_text, new_text in shorthand_replacements:
        label = label.replace(old_text, new_text)

    for old_text, new_text in qualifier_replacements:
        label = label.replace(old_text, new_text)

    label = label.replace("_", " ")
    label = re.sub(r"\s+", " ", label).strip()
    label = label.replace(" )", ")")
    label = label.replace("( ", "(")

    if label in exact_overrides:
        return exact_overrides[label]
    else:
        pass

    gate_match: re.Match[str] | None = re.fullmatch(r"(AND|OR|MAX|MIN)(\d)(?: \((.+)\))?", label)
    if gate_match is not None:
        family: str = gate_match.group(1)
        count: str = gate_match.group(2)
        qualifier: str | None = gate_match.group(3)
        if qualifier is None:
            return f"{family} ({count} inputs)"
        else:
            return f"{family} ({count} inputs, {qualifier})"
    else:
        return label


def _suffix_from_duplicate_family(entries: list[_DescriptorSeed]) -> dict[str, str]:
    """
    Build one user-facing disambiguation suffix for every duplicate label family.

    :param entries: Duplicate label family.
    :returns: Final label by template key.
    """
    input_signatures: set[str] = set()
    parameter_signatures: set[str] = set()
    state_signatures: set[str] = set()
    output_signatures: set[str] = set()
    raw_candidates: dict[str, str] = dict()
    duplicate_candidates: dict[str, list[str]] = dict()
    final_candidates: dict[str, str] = dict()
    entry: _DescriptorSeed

    for entry in entries:
        input_signatures.add(_build_name_signature(entry.inputs))
        parameter_signatures.add(_build_name_signature(entry.params))
        state_signatures.add(_build_name_signature(entry.states))
        output_signatures.add(_build_name_signature(entry.outputs))

    any_flags: bool = any(len(entry.flags) > 0 for entry in entries)

    for entry in entries:
        parts: list[str] = list()

        if any_flags:
            flag_name: str
            for flag_name in entry.flags:
                parts.append(flag_name)
        else:
            pass

        if len(input_signatures) > 1 or (len(entries) > 1 and len(entry.inputs) > 1):
            extra_inputs: Sequence[str] = tuple(name for name in entry.inputs if name != "yi")
            if len(extra_inputs) > 0:
                parts.append(f"signal: {_compact_name_list(extra_inputs)}")
            elif len(entry.inputs) > 0:
                parts.append(_format_count_label(len(entry.inputs), "input", "inputs"))
            else:
                pass
        else:
            pass

        if len(parameter_signatures) > 1 or (len(entries) > 1 and len(entry.params) > 0):
            if len(entry.params) > 0:
                parts.append(f"param: {_compact_name_list(entry.params)}")
            else:
                pass
        else:
            pass

        if len(state_signatures) > 1 or (len(entries) > 1 and len(entry.states) > 0):
            parts.append(_format_count_label(len(entry.states), "state", "states"))
        else:
            pass

        if len(output_signatures) > 1:
            parts.append(f"out: {_compact_name_list(entry.outputs)}")
        else:
            pass

        if len(parts) > 0:
            raw_candidates[entry.template_key] = f"{entry.base_label} [{'; '.join(parts)}]"
        else:
            raw_candidates[entry.template_key] = entry.base_label

    template_key: str
    candidate_label: str
    for template_key, candidate_label in raw_candidates.items():
        variant_group: list[str] | None = duplicate_candidates.get(candidate_label, None)
        if variant_group is None:
            variant_group = list()
            duplicate_candidates[candidate_label] = variant_group
        else:
            pass
        variant_group.append(template_key)

    final_candidates.update(raw_candidates)

    for candidate_label, variant_group in duplicate_candidates.items():
        if len(variant_group) <= 1:
            pass
        else:
            index: int
            variant_template_key: str
            for index, variant_template_key in enumerate(variant_group):
                if candidate_label.endswith("]"):
                    final_candidates[variant_template_key] = f"{candidate_label[:-1]}; {_variant_form_label(index)}]"
                else:
                    final_candidates[variant_template_key] = f"{candidate_label} [{_variant_form_label(index)}]"

    return final_candidates


def _build_display_labels(entries: list[_DescriptorSeed]) -> dict[str, str]:
    """
    Build unique user-facing labels for the shipped catalog.

    :param entries: Descriptor seeds.
    :returns: Final label by template key.
    """
    families: dict[str, list[_DescriptorSeed]] = dict()
    labels_by_template_key: dict[str, str] = dict()
    entry: _DescriptorSeed

    # The first grouping keeps the nicest short label for the common case while the
    # second step adds only the minimum suffixes needed for duplicate families.
    for entry in entries:
        family_entries: list[_DescriptorSeed] | None = families.get(entry.base_label, None)
        if family_entries is None:
            family_entries = list()
            families[entry.base_label] = family_entries
        else:
            pass
        family_entries.append(entry)

    base_label: str
    family_entries: list[_DescriptorSeed]
    for base_label, family_entries in families.items():
        if len(family_entries) == 1:
            labels_by_template_key[family_entries[0].template_key] = base_label
        else:
            labels_by_template_key.update(_suffix_from_duplicate_family(family_entries))

    return labels_by_template_key


def _category_from_name(display_name: str, blkdef_name: str) -> Sequence[str]:
    """
    Categorize one imported block into the Basic library tree.

    :param display_name: Clean display name.
    :param blkdef_name: Raw source block name.
    :returns: Full category path.
    """
    tables: PowerFactoryBasicCatalogTables = build_powerfactory_basic_catalog_tables()
    normalized_display_name: str = re.sub(r" \[[^]]+\]$", "", display_name).strip()
    text: str = f"{normalized_display_name} {blkdef_name}".lower()
    stripped: str = normalized_display_name.lower()

    if "lookup" in text or any(token in text for token in ("lapprox", "sapprox", "invlapprox")):
        return tables.get_category_lookup_arrays_and_matrices()
    elif any(token in text for token in ("clarke transform", "park transform", "abc->dq0", "dq0->abc", "inverse park transform", "inverse clarke transform")):
        return tables.get_category_transforms_clarke_park_dq0()
    elif stripped in tables.get_display_names_rms_and_sequence() or any(token in text for token in ("u seq", "rms value")):
        return tables.get_category_transforms_rms_and_sequence()
    elif any(token in text for token in ("complex", "polar", "rectangular")):
        return tables.get_category_complex_operations()
    elif any(token in text for token in ("square wave generator", "sawtooth wave generator", "triangle wave generator", "sine wave generator", "pulse")):
        return tables.get_category_waveforms_signal_generators()
    elif stripped in tables.get_display_names_time_sources() or any(token in text for token in ("clock", "timer")):
        return tables.get_category_waveforms_time_sources()
    elif any(token in text for token in ("shaft", "spring", "gear box", "mass_j", "p/omg -> torque", "pt/pturb")):
        return tables.get_category_mechanical_drive_train()
    elif stripped in tables.get_display_names_constants_and_scaling():
        return tables.get_category_math_constants_and_scaling()
    elif any(token in text for token in ("pq calculator", "power_base", "el. power", "accelerating power", "hz -> p.u.", "p.u. -> hz", "p.u. -> rpm", "rpm -> p.u.", "rpm -> rad/s", "rad/s -> rpm", "deg -> rad", "rad -> deg", "nm -> p.u.", "abs -> p.u.", "p.u. -> abs")):
        return tables.get_category_control_measurements_and_units()
    elif any(token in text for token in ("picdro", "kp", "ki", "kc", "pi", "(1+ks", "k(1+", "k(a1+", "k/(1+", "k/s")):
        return tables.get_category_control_controllers()
    elif any(token in text for token in ("yi greater", "yi less", "yi equals", "yi not equals", "yi1 greater", "yi1 less", "yi1 equals", "yi1 not equals", "abs(in)")):
        return tables.get_category_logic_comparators()
    elif any(token in text for token in ("and2", "and3", "and4", "or2", "or3", "or4", "nor", "not", "eor", "flipflop", "aflipflop", "bistable", "monostable", "edge detector", "2_out_of_3", "invert logic")):
        return tables.get_category_logic_gates_and_memory()
    elif any(token in text for token in ("switch", "select", "selfix")):
        return tables.get_category_logic_switching_and_selection()
    elif any(token in text for token in ("enable",)):
        return tables.get_category_logic_timers_and_enables()
    elif stripped.startswith("limit") or stripped.startswith("lim") or " limit" in text:
        return tables.get_category_limits_limiters()
    elif any(token in text for token in ("deadband", "backlash", "rate limiter", "gradlim")):
        return tables.get_category_limits_deadbands_and_rate_limiters()
    elif any(token in text for token in ("lastvalue", "delay", "e^-s", "incforward", "incbackward", "movingavg")):
        return tables.get_category_continuous_delays_and_memory()
    elif stripped.startswith("1/s") or stripped.startswith("k/s") or stripped.startswith("s/") or stripped.startswith("-st/") or stripped.startswith("st/"):
        return tables.get_category_continuous_integrators_and_derivatives()
    elif any(token in text for token in ("butterworth", "pade approximant", "band pass")):
        return tables.get_category_continuous_transfer_functions_and_filters()
    elif "s" in stripped and ("/" in stripped or "(" in stripped or ")" in stripped):
        return tables.get_category_continuous_transfer_functions_and_filters()
    elif any(token in text for token in ("multiply", "mx + n", "ax^2 + bx + c", "bias", "a(x-c1)(x-c2)")):
        return tables.get_category_math_scaling_and_products()
    elif stripped in tables.get_display_names_elementary_functions() or stripped.startswith("max") or stripped.startswith("min") or stripped.startswith("1/u"):
        return tables.get_category_math_elementary_functions()
    else:
        return tables.get_category_misc_other()


def _build_descriptor_seed(module_name: str, template_key: str) -> _DescriptorSeed:
    """
    Materialize one standalone module into a typed descriptor seed.

    :param module_name: Standalone module stem.
    :param template_key: Stable semantic lookup key.
    :returns: Descriptor seed.
    """
    tables: PowerFactoryBasicCatalogTables = build_powerfactory_basic_catalog_tables()
    imported_module: ModuleType = _import_template_module_from_module_name(module_name)
    template: EmtModelTemplate = _build_template_from_imported_module(imported_module, VarFactory())
    block: Block = template.block
    generated_name: str = block.name
    clean_name: str = _sanitize_template_name(generated_name)
    typ_id_text: str = _extract_typ_id_from_module_name(module_name)
    inputs: Sequence[str] = _extract_surface_names(list(block.in_vars), generated_name)
    outputs: Sequence[str] = _extract_surface_names(list(block.out_vars), generated_name)
    states: Sequence[str] = _extract_surface_names(list(block.state_vars), generated_name)
    params: Sequence[str] = _extract_parameter_names(block)
    base_label: str = _humanize_catalog_label(clean_name)
    flags: Sequence[str] = _extract_label_flags(clean_name)
    unsupported_lines: Sequence[str]

    # Editor readiness is derived from the shipped module behavior itself.
    # Lookup placeholders remain discoverable, but they are kept out of the menu.
    if _has_executable_content(block):
        unsupported_lines = tuple()
    else:
        unsupported_lines = (tables.get_pending_template_reason(),)

    return _DescriptorSeed(
        template_key=template_key,
        typ_id=typ_id_text,
        blkdef_name=clean_name,
        sample_display_name=clean_name,
        base_label=base_label,
        inputs=inputs,
        outputs=outputs,
        states=states,
        params=params,
        flags=flags,
        unsupported_lines=unsupported_lines,
        module_name=module_name,
        module_filename=f"{module_name}.py",
    )


@lru_cache(maxsize=1)
def get_powerfactory_basic_catalog_descriptors() -> Sequence[PowerFactoryBasicTemplateDescriptor]:
    """
    Return the shipped PowerFactory-derived catalog descriptors.

    :returns: Full descriptor tuple.
    """
    module_names: Sequence[str] = _build_module_names()
    template_keys_by_module_name: dict[str, str] = _build_template_keys(module_names)
    seeds: list[_DescriptorSeed] = list()
    descriptors: list[PowerFactoryBasicTemplateDescriptor] = list()
    module_name: str

    # The descriptor list is built in two passes: first collect the real module
    # surfaces, then resolve the final human-facing labels once duplicates are known.
    for module_name in module_names:
        seeds.append(_build_descriptor_seed(module_name, template_keys_by_module_name[module_name]))

    display_labels_by_template_key: dict[str, str] = _build_display_labels(seeds)
    seed: _DescriptorSeed
    for seed in seeds:
        display_label: str = display_labels_by_template_key[seed.template_key]
        descriptors.append(
            PowerFactoryBasicTemplateDescriptor(
                template_key=seed.template_key,
                blkdef_name=seed.blkdef_name,
                sample_display_name=seed.sample_display_name,
                display_label=display_label,
                category_path=_category_from_name(display_label, seed.blkdef_name),
                inputs=seed.inputs,
                outputs=seed.outputs,
                states=seed.states,
                params=seed.params,
                unsupported_lines=seed.unsupported_lines,
                module_name=seed.module_name,
                module_filename=seed.module_filename,
            )
        )

    descriptors.sort(key=_descriptor_sort_key)
    return tuple(descriptors)


@lru_cache(maxsize=1)
def get_editor_ready_powerfactory_basic_catalog_descriptors() -> Sequence[PowerFactoryBasicTemplateDescriptor]:
    """
    Return only the shipped templates that are ready for editor exposure.

    :returns: Editor-ready descriptor tuple.
    """
    ready_descriptors: list[PowerFactoryBasicTemplateDescriptor] = list()
    descriptor: PowerFactoryBasicTemplateDescriptor

    for descriptor in get_powerfactory_basic_catalog_descriptors():
        if descriptor.is_editor_ready:
            ready_descriptors.append(descriptor)
        else:
            pass

    return tuple(ready_descriptors)


@lru_cache(maxsize=1)
def get_pending_powerfactory_basic_catalog_descriptors() -> Sequence[PowerFactoryBasicTemplateDescriptor]:
    """
    Return only the shipped templates that are not ready for editor exposure.

    :returns: Pending descriptor tuple.
    """
    pending_descriptors: list[PowerFactoryBasicTemplateDescriptor] = list()
    descriptor: PowerFactoryBasicTemplateDescriptor

    for descriptor in get_powerfactory_basic_catalog_descriptors():
        if descriptor.is_editor_ready:
            pass
        else:
            pending_descriptors.append(descriptor)

    return tuple(pending_descriptors)


@lru_cache(maxsize=1)
def get_powerfactory_basic_catalog_descriptor_by_key() -> dict[str, PowerFactoryBasicTemplateDescriptor]:
    """
    Return the descriptor lookup indexed by semantic key.

    :returns: Descriptor lookup by semantic key.
    """
    descriptor_lookup: dict[str, PowerFactoryBasicTemplateDescriptor] = dict()
    descriptor: PowerFactoryBasicTemplateDescriptor

    for descriptor in get_powerfactory_basic_catalog_descriptors():
        descriptor_lookup[descriptor.template_key] = descriptor

    return descriptor_lookup


def import_powerfactory_basic_catalog_module_by_key(template_key: str) -> ModuleType:
    """
    Import one shipped standalone template module by semantic key.

    :param template_key: Stable semantic lookup key.
    :returns: Imported standalone module.
    """
    descriptor: PowerFactoryBasicTemplateDescriptor = get_powerfactory_basic_catalog_descriptor_by_key()[template_key]
    return _import_template_module_from_module_name(descriptor.module_name)


def load_powerfactory_basic_catalog_template(
    descriptor: PowerFactoryBasicTemplateDescriptor,
    var_factory: VarFactory,
    name: str | None = None,
) -> EmtModelTemplate:
    """
    Materialize one shipped PowerFactory-derived template on demand.

    :param descriptor: Template descriptor.
    :param var_factory: Variable factory for the new instance.
    :param name: Optional explicit instance name.
    :returns: Materialized EMT template.
    """
    imported_module: ModuleType = _import_template_module_from_module_name(descriptor.module_name)
    template: EmtModelTemplate = _build_template_from_imported_module(imported_module, var_factory, name=name)
    return template
