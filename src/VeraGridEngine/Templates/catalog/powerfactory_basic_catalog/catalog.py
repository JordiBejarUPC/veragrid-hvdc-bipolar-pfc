from __future__ import annotations

import importlib.util
import json
from collections import defaultdict
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import re
from types import ModuleType
from typing import Any

from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory

PENDING_LOOKUP_TYPE_IDS: frozenset[str] = frozenset(
    {
        "5", "6", "7", "8", "9",
        "14", "15", "16", "17", "18", "19", "20",
        "70", "71", "72", "73", "81", "82",
    }
)


@dataclass(frozen=True, slots=True)
class PowerFactoryBasicTemplateDescriptor:
    """
    One editor-facing entry from the imported PowerFactory basic catalog.
    """

    typ_id: str
    blkdef_name: str
    sample_display_name: str
    display_label: str
    category_path: tuple[str, ...]
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    states: tuple[str, ...]
    params: tuple[str, ...]
    unsupported_lines: tuple[str, ...]
    module_filename: str

    @property
    def search_text(self) -> str:
        """
        Build the normalized search text used by the editor filter.
        """

        return " ".join(
            [
                self.display_label,
                self.blkdef_name,
                self.sample_display_name,
                self.typ_id,
                *self.category_path,
            ]
        ).strip()


def get_powerfactory_basic_catalog_root() -> Path:
    """
    Return the directory containing the imported PowerFactory basic catalog.
    """

    return Path(__file__).resolve().parent


def get_powerfactory_basic_catalog_manifest_path() -> Path:
    """
    Return the shipped manifest path.
    """

    return get_powerfactory_basic_catalog_root() / "catalog_manifest.json"


def get_powerfactory_basic_catalog_templates_dir() -> Path:
    """
    Return the directory with the standalone exported modules.
    """

    return get_powerfactory_basic_catalog_root() / "standalone_templates"


@lru_cache(maxsize=1)
def load_powerfactory_basic_catalog_manifest() -> dict[str, Any]:
    """
    Load the shipped PowerFactory basic catalog manifest.
    """

    manifest_path: Path = get_powerfactory_basic_catalog_manifest_path()
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def _display_name_for_entry(entry: dict[str, Any]) -> str:
    """
    Choose the most user-friendly display name available in the manifest row.
    """

    raw_name: Any = entry.get("sample_display_name")
    if isinstance(raw_name, str) and raw_name.strip():
        return raw_name.strip()

    raw_name = entry.get("blkdef_name")
    if isinstance(raw_name, str) and raw_name.strip():
        return raw_name.strip()

    return f"Template {entry.get('typ_id', 'unknown')}"


def _humanize_catalog_label(blkdef_name: str, sample_display_name: str) -> str:
    """
    Build one user-facing label without exposing internal typ_id suffixes.
    """

    label: str = blkdef_name.strip() if blkdef_name.strip() else sample_display_name.strip()

    label = re.sub(r" \(pp(?![A-Za-z])", " (2 parameter inputs)", label)
    label = re.sub(r" \(p\)", " (parameter)", label)
    label = re.sub(r" \(s\)", " (signal)", label)
    label = re.sub(r" \(p(?![A-Za-z])", " (parameter input)", label)
    label = re.sub(r" \(s(?![A-Za-z])", " (signal input)", label)

    shorthand_replacements: tuple[tuple[str, str], ...] = (
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
    )

    qualifier_replacements: tuple[tuple[str, str], ...] = (
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
    )

    old: str
    new: str
    for old, new in shorthand_replacements:
        label = label.replace(old, new)

    for old, new in qualifier_replacements:
        label = label.replace(old, new)

    label = label.replace("_", " ")
    label = re.sub(r"\s+", " ", label).strip()
    label = label.replace(" )", ")")
    label = label.replace("( ", "(")

    exact_overrides: dict[str, str] = {
        "aflipflop": "Analog flip-flop",
        "flipflop": "Flip-flop",
        "EOR": "XOR",
        "2 out of 3": "2-out-of-3",
        "2 out of 3 (pulse)": "2-out-of-3 (pulse)",
        "selfix": "Set if condition",
        "selfix const": "Set if condition (constant)",
        "select": "Selector",
        "select const": "Selector (constant)",
        "lastvalue": "Last value",
        "movingavg": "Moving average",
        "gradlim const": "Gradient limiter (constant)",
        "picdro": "PI droop",
        "picdro const": "PI droop (constant)",
        "RECIPROCAL": "Reciprocal",
        "RECIPROCAL (feedback)": "Reciprocal (feedback)",
        "EDGE DETECT": "Edge detector",
        "Invert Logic": "Invert logic",
        "Equal": "Equal",
    }

    if label in exact_overrides:
        return exact_overrides[label]
    else:
        pass

    gate_match = re.fullmatch(r"(AND|OR|MAX|MIN)(\d)(?: \((.+)\))?", label)
    if gate_match is not None:
        family: str = gate_match.group(1)
        count: str = gate_match.group(2)
        qualifier: str | None = gate_match.group(3)
        if qualifier:
            return f"{family} ({count} inputs, {qualifier})"
        else:
            return f"{family} ({count} inputs)"

    return label


def _format_count_label(count: int, singular: str, plural: str) -> str:
    """
    Format one count suffix for duplicate label disambiguation.
    """

    if count == 1:
        return f"1 {singular}"
    else:
        return f"{count} {plural}"


def _compact_name_list(names: tuple[str, ...]) -> str:
    """
    Compact one list of manifest names into a short user-facing summary.
    """

    if len(names) == 0:
        return ""
    elif len(names) <= 3:
        return "/".join(names)
    else:
        return f"{'/'.join(names[:3])}+{len(names) - 3}"


def _variant_form_label(index: int) -> str:
    """
    Convert one duplicate index into a short alphabetic form label.
    """

    index += 1
    label: str = ""
    while index > 0:
        index, remainder = divmod(index - 1, 26)
        label = chr(ord('A') + remainder) + label

    return f"form {label}"


def _extract_label_flags(blkdef_name: str) -> tuple[str, ...]:
    """
    Extract visible qualifiers that help distinguish duplicate catalog labels.
    """

    source: str = blkdef_name.lower()
    flags: list[str] = list()

    ordered_flags: tuple[tuple[str, str], ...] = (
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
    )

    token: str
    label: str
    for token, label in ordered_flags:
        if token in source and label not in flags:
            flags.append(label)
        else:
            pass

    return tuple(flags)


def _suffix_from_duplicate_family(entries: list[dict[str, Any]]) -> dict[str, str]:
    """
    Build one user-facing disambiguation suffix for every duplicate family.
    """

    input_signatures: set[tuple[str, ...]] = {entry["inputs"] for entry in entries}
    parameter_signatures: set[tuple[str, ...]] = {entry["params"] for entry in entries}
    state_signatures: set[tuple[str, ...]] = {entry["states"] for entry in entries}
    output_signatures: set[tuple[str, ...]] = {entry["outputs"] for entry in entries}
    any_flags: bool = any(len(entry["flags"]) > 0 for entry in entries)
    raw_candidates: dict[str, str] = dict()

    entry: dict[str, Any]
    for entry in entries:
        parts: list[str] = list()

        if any_flags:
            parts.extend(entry["flags"])
        else:
            pass

        if len(input_signatures) > 1 or (len(entries) > 1 and len(entry["inputs"]) > 1):
            extra_inputs: tuple[str, ...] = tuple(name for name in entry["inputs"] if name != "yi")
            if len(extra_inputs) > 0:
                parts.append(f"signal: {_compact_name_list(extra_inputs)}")
            elif len(entry["inputs"]) > 0:
                parts.append(_format_count_label(len(entry["inputs"]), "input", "inputs"))
            else:
                pass
        else:
            pass

        if len(parameter_signatures) > 1 or (len(entries) > 1 and len(entry["params"]) > 0):
            if len(entry["params"]) > 0:
                parts.append(f"param: {_compact_name_list(entry['params'])}")
            else:
                pass
        else:
            pass

        if len(state_signatures) > 1 or (len(entries) > 1 and len(entry["states"]) > 0):
            parts.append(_format_count_label(len(entry["states"]), "state", "states"))
        else:
            pass

        if len(output_signatures) > 1:
            parts.append(f"out: {_compact_name_list(entry['outputs'])}")
        else:
            pass

        raw_candidates[entry["typ_id"]] = f"{entry['base_label']} [{'; '.join(parts)}]" if len(parts) > 0 else entry["base_label"]

    duplicate_candidates: dict[str, list[str]] = defaultdict(list)
    typ_id: str
    candidate: str
    for typ_id, candidate in raw_candidates.items():
        duplicate_candidates[candidate].append(typ_id)

    final_candidates: dict[str, str] = dict(raw_candidates)
    variant_group: list[str]
    for candidate, variant_group in duplicate_candidates.items():
        if len(variant_group) <= 1:
            continue

        variant_group = sorted(variant_group, key=int)
        index: int
        variant_typ_id: str
        for index, variant_typ_id in enumerate(variant_group):
            if candidate.endswith("]"):
                final_candidates[variant_typ_id] = f"{candidate[:-1]}; {_variant_form_label(index)}]"
            else:
                final_candidates[variant_typ_id] = f"{candidate} [{_variant_form_label(index)}]"

    return final_candidates


def _build_display_labels(entries: list[dict[str, Any]]) -> dict[str, str]:
    """
    Build unique user-facing labels for the shipped catalog.
    """

    families: dict[str, list[dict[str, Any]]] = defaultdict(list)
    labels_by_typ_id: dict[str, str] = dict()

    entry: dict[str, Any]
    for entry in entries:
        families[entry["base_label"]].append(entry)

    base_label: str
    family_entries: list[dict[str, Any]]
    for base_label, family_entries in families.items():
        if len(family_entries) == 1:
            labels_by_typ_id[family_entries[0]["typ_id"]] = base_label
        else:
            labels_by_typ_id.update(_suffix_from_duplicate_family(family_entries))

    return labels_by_typ_id


def _iter_str_list(raw_value: Any) -> tuple[str, ...]:
    """
    Normalize one manifest field into a tuple of strings.
    """

    if isinstance(raw_value, list):
        return tuple(str(item) for item in raw_value)
    else:
        return tuple()


def _category_from_name(display_name: str, blkdef_name: str) -> tuple[str, ...]:
    """
    Categorize one imported PowerFactory basic block into the Basic library tree.
    """

    text: str = f"{display_name} {blkdef_name}".lower()
    stripped: str = display_name.strip().lower()

    if "lookup" in text:
        return ("Native", "Lookup and Tables", "Arrays and Matrices")

    if any(token in text for token in ("clarke transform", "park transform", "abc->dq0", "dq0->abc", "inverse park transform", "inverse clarke transform")):
        return ("Native", "Transforms", "Clarke, Park and dq0")

    if stripped in {"rms", "balanced"} or any(token in text for token in ("u seq", "rms value")):
        return ("Native", "Transforms", "RMS and Sequence")

    if any(token in text for token in ("complex", "polar", "rectangular")):
        return ("Native", "Complex", "Operations")

    if any(token in text for token in ("square wave generator", "sawtooth wave generator", "triangle wave generator", "sine wave generator", "pulse")):
        return ("Native", "Waveforms and Time", "Signal Generators")

    if stripped in {"time"} or any(token in text for token in ("clock", "timer")):
        return ("Native", "Waveforms and Time", "Time Sources and Timers")

    if any(token in text for token in ("shaft", "spring", "gear box", "mass_j", "p/omg -> torque", "pt/pturb")):
        return ("Native", "Mechanical", "Drive Train")

    if stripped in {"0", "1", "c", "e", "-c", "pi", "pi/2", "2pi", "1/sqrt2", "1/sqrt3", "sqrt2", "sqrt3", "sqrt(2/3)", "sqrt(3/2)", "sqrt(c1/c2)", "c1/c2"}:
        return ("Native", "Math and Functions", "Constants and Scaling")

    if any(token in text for token in ("pq calculator", "power_base", "el. power", "accelerating power", "hz -> p.u.", "p.u. -> hz", "p.u. -> rpm", "rpm -> p.u.", "rpm -> rad/s", "rad/s -> rpm", "deg -> rad", "rad -> deg", "nm -> p.u.", "abs -> p.u.", "p.u. -> abs")):
        return ("Native", "Control and Measurement", "Measurements and Units")

    if any(token in text for token in ("picdro", "kp", "ki", "kc", "pi", "(1+ks", "k(1+", "k(a1+", "k/(1+", "k/s")):
        return ("Native", "Control and Measurement", "Controllers")

    if any(token in text for token in ("yi greater", "yi less", "yi equals", "yi not equals", "yi1 greater", "yi1 less", "yi1 equals", "yi1 not equals", "abs(in)")):
        return ("Native", "Logic and Events", "Comparators")

    if any(token in text for token in ("and2", "and3", "and4", "or2", "or3", "or4", "nor", "not", "eor", "flipflop", "aflipflop", "bistable", "monostable", "edge detector", "2_out_of_3", "invert logic")):
        return ("Native", "Logic and Events", "Gates and Memory")

    if any(token in text for token in ("switch", "select", "selfix")):
        return ("Native", "Logic and Events", "Switching and Selection")

    if any(token in text for token in ("enable",)):
        return ("Native", "Logic and Events", "Timers and Enables")

    if stripped.startswith("limit") or stripped.startswith("lim") or " limit" in text:
        return ("Native", "Limits and Nonlinearities", "Limiters")

    if any(token in text for token in ("deadband", "backlash", "rate limiter", "gradlim")):
        return ("Native", "Limits and Nonlinearities", "Deadbands and Rate Limiters")

    if any(token in text for token in ("lastvalue", "delay", "e^-s", "incforward", "incbackward", "movingavg")):
        return ("Native", "Continuous", "Delays and Memory")

    if stripped.startswith("1/s") or stripped.startswith("k/s") or stripped.startswith("s/") or stripped.startswith("-st/") or stripped.startswith("st/"):
        return ("Native", "Continuous", "Integrators and Derivatives")

    if any(token in text for token in ("butterworth", "pade approximant", "band pass")):
        return ("Native", "Continuous", "Transfer Functions and Filters")

    if ("/" in stripped or "(" in stripped or ")" in stripped) and "s" in stripped:
        return ("Native", "Continuous", "Transfer Functions and Filters")

    if any(token in text for token in ("multiply", "mx + n", "ax^2 + bx + c", "bias", "a(x-c1)(x-c2)")):
        return ("Native", "Math and Functions", "Scaling and Products")

    if stripped in {"abs", "ceil", "exp", "floor", "frac", "ln", "log", "max2", "max3", "max4", "min2", "min3", "min4", "modulo", "reciprocal", "round", "sign", "sin", "sind", "sinh", "sinhd", "cos", "cosd", "cosh", "coshd", "tan", "tand", "tanh", "tanhd", "sqrt", "x^2", "x^p", "acos", "asin", "atan", "atan2", "atan2d", "atand"} or stripped.startswith("max") or stripped.startswith("min") or stripped.startswith("1/u"):
        return ("Native", "Math and Functions", "Elementary Functions")

    return ("Native", "Miscellaneous", "Other")


@lru_cache(maxsize=1)
def _template_filename_by_typ_id() -> dict[str, str]:
    """
    Resolve one exported module filename for each typ_id.
    """

    mapping: dict[str, str] = dict()
    template_path: Path
    prefix: str

    for template_path in get_powerfactory_basic_catalog_templates_dir().glob("typ_*.py"):
        prefix = template_path.stem.split("__", maxsplit=1)[0]
        if prefix.startswith("typ_"):
            mapping[prefix[4:]] = template_path.name
        else:
            pass

    return mapping


@lru_cache(maxsize=1)
def get_powerfactory_basic_catalog_descriptors() -> tuple[PowerFactoryBasicTemplateDescriptor, ...]:
    """
    Return the shipped PowerFactory basic catalog descriptors.
    """

    manifest: dict[str, Any] = load_powerfactory_basic_catalog_manifest()
    raw_entries: Any = manifest.get("entries", list())
    entries: list[dict[str, Any]] = list(raw_entries) if isinstance(raw_entries, list) else list()
    template_filenames: dict[str, str] = _template_filename_by_typ_id()
    descriptor_seed_entries: list[dict[str, Any]] = list()
    descriptors: list[PowerFactoryBasicTemplateDescriptor] = list()

    entry: dict[str, Any]
    for entry in entries:
        typ_id: str = str(entry["typ_id"])
        display_name: str = _display_name_for_entry(entry)
        base_label: str = _humanize_catalog_label(str(entry["blkdef_name"]), display_name)
        module_filename: str | None = template_filenames.get(typ_id, None)

        if module_filename is None:
            raise FileNotFoundError(f"Missing exported template module for typ_id={typ_id}")

        descriptor_seed_entries.append(
            {
                "typ_id": typ_id,
                "base_label": base_label,
                "blkdef_name": str(entry["blkdef_name"]),
                "sample_display_name": display_name,
                "inputs": _iter_str_list(entry.get("inputs", list())),
                "outputs": _iter_str_list(entry.get("outputs", list())),
                "states": _iter_str_list(entry.get("states", list())),
                "params": _iter_str_list(entry.get("params", list())),
                "flags": _extract_label_flags(str(entry["blkdef_name"])),
            }
        )

    display_labels_by_typ_id: dict[str, str] = _build_display_labels(descriptor_seed_entries)

    for entry in entries:
        typ_id = str(entry["typ_id"])
        display_name = _display_name_for_entry(entry)
        module_filename = template_filenames[typ_id]

        descriptors.append(
            PowerFactoryBasicTemplateDescriptor(
                typ_id=typ_id,
                blkdef_name=str(entry["blkdef_name"]),
                sample_display_name=display_name,
                display_label=display_labels_by_typ_id[typ_id],
                category_path=_category_from_name(display_name, str(entry["blkdef_name"])),
                inputs=_iter_str_list(entry.get("inputs", list())),
                outputs=_iter_str_list(entry.get("outputs", list())),
                states=_iter_str_list(entry.get("states", list())),
                params=_iter_str_list(entry.get("params", list())),
                unsupported_lines=_iter_str_list(entry.get("unsupported_lines", list())),
                module_filename=module_filename,
            )
        )

    return tuple(descriptors)


@lru_cache(maxsize=1)
def get_editor_ready_powerfactory_basic_catalog_descriptors() -> tuple[PowerFactoryBasicTemplateDescriptor, ...]:
    """
    Return only the PowerFactory basic templates that are ready for editor exposure.
    """

    return tuple(
        descriptor
        for descriptor in get_powerfactory_basic_catalog_descriptors()
        if len(descriptor.unsupported_lines) == 0
    )


@lru_cache(maxsize=1)
def get_pending_powerfactory_basic_catalog_descriptors() -> tuple[PowerFactoryBasicTemplateDescriptor, ...]:
    """
    Return the shipped templates that still depend on unsupported lookup helpers.
    """

    return tuple(
        descriptor
        for descriptor in get_powerfactory_basic_catalog_descriptors()
        if len(descriptor.unsupported_lines) > 0
    )


@lru_cache(maxsize=1)
def get_powerfactory_basic_catalog_descriptor_by_typ_id() -> dict[str, PowerFactoryBasicTemplateDescriptor]:
    """
    Return a typ_id lookup for the shipped catalog descriptors.
    """

    return {descriptor.typ_id: descriptor for descriptor in get_powerfactory_basic_catalog_descriptors()}


def _import_module_from_descriptor(descriptor: PowerFactoryBasicTemplateDescriptor) -> ModuleType:
    """
    Import one shipped standalone template module.
    """

    template_path: Path = get_powerfactory_basic_catalog_templates_dir() / descriptor.module_filename
    module_name: str = f"veragrid_powerfactory_basic_typ_{descriptor.typ_id}"
    spec = importlib.util.spec_from_file_location(module_name, template_path)

    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load PowerFactory basic template module from {template_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if isinstance(module, ModuleType):
        return module
    else:
        raise ImportError(f"Template module at {template_path} did not load as ModuleType")


def import_powerfactory_basic_catalog_module(typ_id: str) -> ModuleType:
    """
    Import one shipped standalone template module by typ_id.
    """

    descriptor: PowerFactoryBasicTemplateDescriptor = get_powerfactory_basic_catalog_descriptor_by_typ_id()[typ_id]
    return _import_module_from_descriptor(descriptor)


def load_powerfactory_basic_catalog_template(
    descriptor: PowerFactoryBasicTemplateDescriptor,
    var_factory: VarFactory,
    name: str | None = None,
) -> EmtModelTemplate:
    """
    Materialize one shipped PowerFactory basic template on demand.
    """

    module: ModuleType = _import_module_from_descriptor(descriptor)
    get_template = getattr(module, "get_template", None)
    if callable(get_template):
        template: EmtModelTemplate = get_template(vf=var_factory, name=name)
        return template
    else:
        raise AttributeError(f"Template module for typ_id={descriptor.typ_id} does not expose get_template()")
