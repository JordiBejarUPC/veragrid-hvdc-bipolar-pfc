from __future__ import annotations

import json
from pathlib import Path

from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.international_standards.templates import InternationalStandardModel
from VeraGridEngine.Templates.international_standards.templates import build_international_standard_template
from VeraGridEngine.Templates.international_standards.templates import parse_international_standard_model
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Var


class InternationalStandardTemplateDescriptor:
    """Store the immutable catalog description of one dynamic template."""

    __slots__ = (
        "template_key",
        "display_name",
        "source_xml_name",
        "module_name",
        "module_filename",
        "payload_filename",
        "state_var_count",
        "diff_var_count",
        "algebraic_var_count",
        "state_eq_count",
        "algebraic_eq_count",
        "warning_messages",
    )

    def __init__(
            self: InternationalStandardTemplateDescriptor,
            template_key: str,
            display_name: str,
            source_xml_name: str,
            module_name: str,
            module_filename: str,
            payload_filename: str,
            state_var_count: int,
            diff_var_count: int,
            algebraic_var_count: int,
            state_eq_count: int,
            algebraic_eq_count: int,
            warning_messages: tuple[str, ...],
    ) -> None:
        """
        Initialize one catalog descriptor from validated manifest fields.

        :param template_key: Stable public catalog key.
        :type template_key: str
        :param display_name: User-facing model name.
        :type display_name: str
        :param source_xml_name: Source-document provenance name.
        :type source_xml_name: str
        :param module_name: Python module name used by the runtime registry.
        :type module_name: str
        :param module_filename: Python module filename.
        :type module_filename: str
        :param payload_filename: Validation payload filename, when available.
        :type payload_filename: str
        :param state_var_count: Expected continuous-state variable count.
        :type state_var_count: int
        :param diff_var_count: Expected derivative variable count.
        :type diff_var_count: int
        :param algebraic_var_count: Expected algebraic variable count.
        :type algebraic_var_count: int
        :param state_eq_count: Expected continuous-state equation count.
        :type state_eq_count: int
        :param algebraic_eq_count: Expected algebraic equation count.
        :type algebraic_eq_count: int
        :param warning_messages: Provenance and reconstruction warnings.
        :type warning_messages: tuple[str, ...]
        :return: None.
        :rtype: None
        """
        # Keep the descriptor fixed-size and type-explicit for predictable catalog access.
        self.template_key: str = template_key
        self.display_name: str = display_name
        self.source_xml_name: str = source_xml_name
        self.module_name: str = module_name
        self.module_filename: str = module_filename
        self.payload_filename: str = payload_filename
        self.state_var_count: int = state_var_count
        self.diff_var_count: int = diff_var_count
        self.algebraic_var_count: int = algebraic_var_count
        self.state_eq_count: int = state_eq_count
        self.algebraic_eq_count: int = algebraic_eq_count
        self.warning_messages: tuple[str, ...] = warning_messages


class InternationalStandardGenerationFailure:
    """Store one failed source-model conversion reported by the manifest."""

    __slots__ = ("template_key", "source_xml_name", "error_messages", "warning_messages")

    def __init__(
            self: InternationalStandardGenerationFailure,
            template_key: str,
            source_xml_name: str,
            error_messages: tuple[str, ...],
            warning_messages: tuple[str, ...],
    ) -> None:
        """
        Initialize one failed-generation record.

        :param template_key: Stable catalog key assigned to the source model.
        :type template_key: str
        :param source_xml_name: Source-document provenance name.
        :type source_xml_name: str
        :param error_messages: Conversion errors reported by the generator.
        :type error_messages: tuple[str, ...]
        :param warning_messages: Non-fatal conversion warnings.
        :type warning_messages: tuple[str, ...]
        :return: None.
        :rtype: None
        """
        # A fixed-size light class makes failed records inspectable without dataclass magic.
        self.template_key: str = template_key
        self.source_xml_name: str = source_xml_name
        self.error_messages: tuple[str, ...] = error_messages
        self.warning_messages: tuple[str, ...] = warning_messages


def get_international_standard_root() -> Path:
    """
    Resolve the maintainable production catalog directory.

    :return: Absolute package directory containing the runtime catalog.
    :rtype: Path
    """
    # Resolve from this module so the catalog never depends on PATH or environment variables.
    catalog_root: Path = Path(__file__).resolve().parent
    return catalog_root


def get_international_standard_manifest_path() -> Path:
    """
    Resolve the production manifest path.

    :return: Absolute path of ``manifest.json``.
    :rtype: Path
    """
    # Keep manifest discovery relative to the installed package for reproducible deployments.
    manifest_path: Path = get_international_standard_root() / "manifest.json"
    return manifest_path


def get_international_standard_templates_dir() -> Path:
    """
    Resolve the maintainable template-module directory.

    :return: Absolute directory containing runtime template modules.
    :rtype: Path
    """
    # Expose the resolved path for catalog validation without relying on process state.
    templates_dir: Path = get_international_standard_root() / "templates"
    return templates_dir


def _empty_manifest() -> dict[str, object]:
    """
    Build an explicit empty manifest for handled read or format failures.

    :return: Manifest with empty success and failure collections.
    :rtype: dict[str, object]
    """
    empty_success: list[object] = list()
    empty_failed: list[object] = list()
    manifest: dict[str, object] = dict()
    manifest["success"] = empty_success
    manifest["failed"] = empty_failed
    return manifest


def _load_manifest() -> dict[str, object]:
    """
    Read the standards manifest while handling unavailable or malformed files.

    :return: Parsed manifest dictionary or an explicit empty manifest.
    :rtype: dict[str, object]
    """
    manifest_path: Path = get_international_standard_manifest_path()
    raw_manifest: object | None = None

    # A missing or malformed optional catalog is a handled empty state, not a process failure.
    if manifest_path.is_file():
        try:
            manifest_text: str = manifest_path.read_text(encoding="utf-8")
            raw_manifest = json.loads(manifest_text)
        except (OSError, json.JSONDecodeError):
            raw_manifest = None
    else:
        raw_manifest = None

    if isinstance(raw_manifest, dict):
        manifest: dict[str, object] = raw_manifest
    else:
        manifest = _empty_manifest()

    return manifest


def _read_manifest_text(raw_entry: dict[object, object], key: str) -> str:
    """
    Read one optional manifest field as text.

    :param raw_entry: Parsed JSON object for one model.
    :type raw_entry: dict[object, object]
    :param key: Field name to read.
    :type key: str
    :return: Text value, or an empty string when the field is absent.
    :rtype: str
    """
    raw_value: object | None = raw_entry.get(key, None)
    if raw_value is None:
        value: str = ""
    else:
        value = str(raw_value)
    return value


def _read_manifest_int(raw_entry: dict[object, object], key: str) -> int:
    """
    Read one optional manifest field as an integer count.

    :param raw_entry: Parsed JSON object for one model.
    :type raw_entry: dict[object, object]
    :param key: Field name to read.
    :type key: str
    :return: Non-negative parsed count, or zero for an invalid field.
    :rtype: int
    """
    raw_value: object | None = raw_entry.get(key, None)
    value: int

    # JSON counts are normally integers; guarded string parsing keeps corrupt entries handled.
    if isinstance(raw_value, bool):
        value = 0
    elif isinstance(raw_value, int):
        value = raw_value
    elif isinstance(raw_value, float):
        value = int(raw_value)
    elif isinstance(raw_value, str):
        try:
            value = int(raw_value)
        except ValueError:
            value = 0
    else:
        value = 0

    if value >= 0:
        normalized_value: int = value
    else:
        normalized_value = 0
    return normalized_value


def _read_manifest_messages(raw_entry: dict[object, object], key: str) -> tuple[str, ...]:
    """
    Read one optional manifest message collection.

    :param raw_entry: Parsed JSON object for one model.
    :type raw_entry: dict[object, object]
    :param key: Message-list field name.
    :type key: str
    :return: Immutable ordered message tuple.
    :rtype: tuple[str, ...]
    """
    raw_messages: object | None = raw_entry.get(key, None)
    messages: list[str] = list()

    if isinstance(raw_messages, list):
        raw_message: object
        for raw_message in raw_messages:
            messages.append(str(raw_message))
    else:
        pass

    return tuple(messages)


def get_international_standard_descriptors() -> tuple[InternationalStandardTemplateDescriptor, ...]:
    """
    Materialize every successful dynamic-model descriptor in manifest order.

    :return: Immutable ordered descriptor collection.
    :rtype: tuple[InternationalStandardTemplateDescriptor, ...]
    """
    manifest: dict[str, object] = _load_manifest()
    raw_entries: object | None = manifest.get("success", None)
    descriptors: list[InternationalStandardTemplateDescriptor] = list()

    # Preserve manifest order because it is already deterministic and avoids callback-based sorting.
    if isinstance(raw_entries, list):
        raw_entry: object
        for raw_entry in raw_entries:
            if isinstance(raw_entry, dict):
                descriptor: InternationalStandardTemplateDescriptor = InternationalStandardTemplateDescriptor(
                    template_key=_read_manifest_text(raw_entry=raw_entry, key="template_key"),
                    display_name=_read_manifest_text(raw_entry=raw_entry, key="display_name"),
                    source_xml_name=_read_manifest_text(raw_entry=raw_entry, key="source_xml_name"),
                    module_name=_read_manifest_text(raw_entry=raw_entry, key="module_name"),
                    module_filename=_read_manifest_text(raw_entry=raw_entry, key="module_filename"),
                    payload_filename=_read_manifest_text(raw_entry=raw_entry, key="payload_filename"),
                    state_var_count=_read_manifest_int(raw_entry=raw_entry, key="state_var_count"),
                    diff_var_count=_read_manifest_int(raw_entry=raw_entry, key="diff_var_count"),
                    algebraic_var_count=_read_manifest_int(raw_entry=raw_entry, key="algebraic_var_count"),
                    state_eq_count=_read_manifest_int(raw_entry=raw_entry, key="state_eq_count"),
                    algebraic_eq_count=_read_manifest_int(raw_entry=raw_entry, key="algebraic_eq_count"),
                    warning_messages=_read_manifest_messages(raw_entry=raw_entry, key="warning_messages"),
                )
                descriptors.append(descriptor)
            else:
                pass
    else:
        pass

    return tuple(descriptors)


def get_international_standard_failures() -> tuple[InternationalStandardGenerationFailure, ...]:
    """
    Materialize every failed source-model conversion in manifest order.

    :return: Immutable ordered failure collection.
    :rtype: tuple[InternationalStandardGenerationFailure, ...]
    """
    manifest: dict[str, object] = _load_manifest()
    raw_entries: object | None = manifest.get("failed", None)
    failures: list[InternationalStandardGenerationFailure] = list()

    if isinstance(raw_entries, list):
        raw_entry: object
        for raw_entry in raw_entries:
            if isinstance(raw_entry, dict):
                failure: InternationalStandardGenerationFailure = InternationalStandardGenerationFailure(
                    template_key=_read_manifest_text(raw_entry=raw_entry, key="template_key"),
                    source_xml_name=_read_manifest_text(raw_entry=raw_entry, key="source_xml_name"),
                    error_messages=_read_manifest_messages(raw_entry=raw_entry, key="error_messages"),
                    warning_messages=_read_manifest_messages(raw_entry=raw_entry, key="warning_messages"),
                )
                failures.append(failure)
            else:
                pass
    else:
        pass

    return tuple(failures)


def get_international_standard_descriptor_by_key() -> dict[str, InternationalStandardTemplateDescriptor]:
    """
    Index the model descriptors by their stable public key.

    :return: Lookup dictionary used at catalog boundaries.
    :rtype: dict[str, InternationalStandardTemplateDescriptor]
    """
    descriptor_lookup: dict[str, InternationalStandardTemplateDescriptor] = dict()
    descriptor: InternationalStandardTemplateDescriptor

    # A dictionary is appropriate here because this function is explicitly a key lookup boundary.
    for descriptor in get_international_standard_descriptors():
        descriptor_lookup[descriptor.template_key] = descriptor

    return descriptor_lookup


def _normalize_var_group(var_group: list[Var]) -> None:
    """
    Normalize generated time-variable names in one concrete variable group.

    :param var_group: Mutable symbolic-variable collection owned by a block.
    :type var_group: list[Var]
    :return: None.
    :rtype: None
    """
    var_obj: Var
    for var_obj in var_group:
        if var_obj.name.startswith("time_"):
            var_obj.name = "time"
        else:
            pass


def _normalize_block_time_vars(block: Block) -> None:
    """
    Normalize time variables throughout one block hierarchy.

    :param block: Root symbolic block to normalize recursively.
    :type block: Block
    :return: None.
    :rtype: None
    """
    # Visit each storage group explicitly so every source of symbolic variables is inspectable.
    _normalize_var_group(var_group=block.state_vars)
    _normalize_var_group(var_group=block.algebraic_vars)
    _normalize_var_group(var_group=block.diff_vars)
    _normalize_var_group(var_group=block.in_vars)
    _normalize_var_group(var_group=block.out_vars)
    _normalize_var_group(var_group=list(block.event_dict.keys()))
    _normalize_var_group(var_group=list(block.mode_dict.keys()))
    _normalize_var_group(var_group=list(block.parameters.keys()))
    _normalize_var_group(var_group=list(block.init_eqs.keys()))
    _normalize_var_group(var_group=list(block.diff_init_eqs.keys()))

    # Rebuild the name index after normalization so downstream equation lookup stays coherent.
    var_mapping: dict[str, Var] = dict()
    var_obj: Var
    for var_obj in block.algebraic_vars:
        var_mapping[var_obj.name] = var_obj
    block.var_mapping = var_mapping

    # Recurse at module scope; nested functions are deliberately avoided for auditability.
    child_block: Block
    for child_block in block.children:
        _normalize_block_time_vars(block=child_block)


def load_international_standard_template(
        descriptor: InternationalStandardTemplateDescriptor,
        vf: VarFactory,
        name: str | None = None,
) -> EmtModelTemplate:
    """
    Build and normalize one manifest-selected international-standard model.

    :param descriptor: Validated catalog descriptor to materialize.
    :type descriptor: InternationalStandardTemplateDescriptor
    :param vf: Variable factory that owns the symbolic variables.
    :type vf: VarFactory
    :param name: Optional runtime instance name.
    :type name: str | None
    :return: Materialized and normalized dynamic template.
    :rtype: EmtModelTemplate
    """
    model: InternationalStandardModel | None = parse_international_standard_model(
        module_name=descriptor.module_name,
    )

    # An unknown manifest entry cannot be represented safely, so reject it at this typed boundary.
    if model is None:
        raise ValueError(f"Unknown international-standard module: {descriptor.module_name}")
    else:
        template: EmtModelTemplate = build_international_standard_template(model=model, vf=vf, name=name)

    _normalize_block_time_vars(block=template.block)
    return template
