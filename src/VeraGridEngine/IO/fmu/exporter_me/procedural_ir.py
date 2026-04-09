from __future__ import annotations

from typing import Any

from .compat import Block, procedural_logic_to_dict
from .export_ir import ExportLogicEntry


SUPPORTED_LOGIC_TYPES = {
    "fixed_sample",
    "sampled_value",
    "flipflop",
}


def build_logic_entries(block: Block) -> tuple[ExportLogicEntry, ...]:
    serialized = procedural_logic_to_dict(block.procedural_logic)
    entries: list[ExportLogicEntry] = []
    for index, item in enumerate(serialized):
        logic_type = str(item.get("logic_type", ""))
        if logic_type not in SUPPORTED_LOGIC_TYPES:
            raise ValueError(f"Unsupported procedural logic type for Model Exchange export: {logic_type!r}")
        entries.append(
            ExportLogicEntry(
                index=index,
                logic_type=logic_type,
                name=str(item.get("name", "")),
                data=dict(item),
            )
        )
    return tuple(entries)


def export_logic_manifest(entries: tuple[ExportLogicEntry, ...]) -> list[dict[str, Any]]:
    return [dict(entry.data) for entry in entries]
