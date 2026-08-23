from __future__ import annotations

import re
import shutil
import subprocess
from enum import Enum
from html import escape, unescape
from pathlib import Path

from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.enumerations import DeviceType, ResultTypes, SimulationTypes, StudyResultsType


def _find_tool(tool_name: str) -> str:
    """
    Resolve one Qt translation tool from PATH.

    :param tool_name: Executable name.
    :returns: Executable path or the original name.
    """
    resolved_path: str | None = shutil.which(tool_name)
    if resolved_path is None:
        return tool_name
    else:
        return resolved_path


def _run_command(arguments: list[str]) -> None:
    """
    Run one subprocess and fail fast on errors.

    :param arguments: Command arguments.
    :returns: Nothing.
    """
    subprocess.run(arguments, check=True)


def _get_translation_source_files(translations_dir: Path) -> list[Path]:
    """
    Return every translation source file stored in the translations directory.

    :param translations_dir: Directory containing ``.ts`` files.
    :returns: Sorted translation source files.
    """
    ts_files: list[Path] = sorted(translations_dir.glob("*.ts"))
    return ts_files


def _escape_ts_text(text: str) -> str:
    """
    Escape one source text for XML ``.ts`` storage.

    :param text: Source text.
    :returns: XML escaped source text.
    """
    return escape(text, quote=False)


def _get_runtime_tree_label_sources() -> list[str]:
    """
    Return every source label used by runtime-built database and results trees.

    :returns: Sorted source labels.
    """
    source_texts: set[str] = set()
    circuit: MultiCircuit = MultiCircuit()
    group_name: str
    enum_classes: list[type[Enum]] = [
        DeviceType,
        ResultTypes,
        SimulationTypes,
        StudyResultsType,
    ]
    enum_class: type[Enum]
    enum_entry: Enum

    source_texts.add("Objects")
    source_texts.add("Results")

    # Database tree group labels come from the circuit template grouping, not from enums.
    for group_name in circuit.get_template_objects_type_dict().keys():
        source_texts.add(str(group_name))

    # Database leaves, result-study rows and result leaves use enum values only for display.
    for enum_class in enum_classes:
        for enum_entry in enum_class:
            source_texts.add(str(enum_entry.value))

    return sorted(source_texts)


def _build_unfinished_ts_message(source_text: str) -> str:
    """
    Build one untranslated Qt Linguist message block.

    :param source_text: Source text.
    :returns: Message XML block.
    """
    escaped_source_text: str = _escape_ts_text(text=source_text)
    return (
        "    <message>\n"
        f"        <source>{escaped_source_text}</source>\n"
        '        <translation type="unfinished"></translation>\n'
        "    </message>\n"
    )


def _collect_context_source_texts(context_block: str) -> set[str]:
    """
    Collect source texts already present in one Qt Linguist context block.

    :param context_block: Full context XML block.
    :returns: Source texts found in the block.
    """
    source_texts: set[str] = set()
    match: re.Match[str]

    for match in re.finditer(r"<source>(.*?)</source>", context_block, flags=re.DOTALL):
        source_texts.add(unescape(match.group(1)))

    return source_texts


def _sync_tree_label_context(ts_file: Path, source_texts: list[str]) -> None:
    """
    Ensure the manual runtime tree-label context contains every enum label.

    :param ts_file: Translation source file to patch.
    :param source_texts: Required tree-label source texts.
    :returns: Nothing.
    """
    context_name: str = "VeraGridTreeLabels"
    contents: str = ts_file.read_text(encoding="utf-8")
    context_pattern: str = rf"(<context>\s*<name>{context_name}</name>)(.*?)(</context>)"
    context_match: re.Match[str] | None = re.search(context_pattern, contents, flags=re.DOTALL)
    missing_messages: list[str] = list()
    source_text: str

    if context_match is None:
        for source_text in source_texts:
            missing_messages.append(_build_unfinished_ts_message(source_text=source_text))

        context_block: str = (
            "<context>\n"
            f"    <name>{context_name}</name>\n"
            + "".join(missing_messages)
            + "</context>\n"
        )
        contents = contents.replace("</TS>\n", context_block + "</TS>\n")
    else:
        existing_source_texts: set[str] = _collect_context_source_texts(context_block=context_match.group(0))
        for source_text in source_texts:
            if source_text in existing_source_texts:
                pass
            else:
                missing_messages.append(_build_unfinished_ts_message(source_text=source_text))

        if len(missing_messages) > 0:
            contents = (
                contents[:context_match.start(3)]
                + "".join(missing_messages)
                + contents[context_match.start(3):]
            )
        else:
            pass

    ts_file.write_text(contents, encoding="utf-8")


def _reactivate_manual_context_translations(ts_file: Path) -> None:
    """
    Restore manual translation contexts after ``lupdate`` marks them vanished.

    :param ts_file: Translation source file to patch.
    :returns: Nothing.
    """
    contents: str = ts_file.read_text(encoding="utf-8")
    updated_contents: str = contents

    for context_name in ["ContextMenu", "ConfigurationMain", "messages", "SimulationsMain", "VeraGridTreeLabels"]:
        context_pattern: str = rf"(<context>\s*<name>{context_name}</name>.*?</context>)"

        def reactivate_context_block(context_match: re.Match[str]) -> str:
            """
            Remove ``vanished`` and selected ``unfinished`` markers from one runtime context block.

            :param context_match: Regex match containing one whole TS context block.
            :returns: Patched TS context block.
            """
            context_block: str = context_match.group(1)
            reactivated_block: str = context_block.replace(
                '<translation type="vanished">',
                "<translation>",
            )
            reactivated_block = re.sub(
                r'<translation type="unfinished">([^<]+)</translation>',
                r"<translation>\1</translation>",
                reactivated_block,
            )
            return reactivated_block

        updated_contents = re.sub(
            context_pattern,
            reactivate_context_block,
            updated_contents,
            flags=re.DOTALL,
        )

    if updated_contents == contents:
        return
    else:
        pass

    # Only the manual runtime contexts are rewritten so translator-managed
    # formatting outside those catalogs remains untouched.
    ts_file.write_text(updated_contents, encoding="utf-8")


def update_translations() -> None:
    """
    Refresh every application ``.ts`` file and compile matching ``.qm`` outputs.

    :returns: Nothing.
    """
    gui_root: Path = Path(__file__).resolve().parent
    translations_dir: Path = gui_root / "translations"
    ts_files: list[Path]
    tree_label_sources: list[str] = _get_runtime_tree_label_sources()

    translations_dir.mkdir(parents=True, exist_ok=True)
    ts_files = _get_translation_source_files(translations_dir=translations_dir)

    if len(ts_files) == 0:
        return
    else:
        pass

    # Update all catalogs in one lupdate pass so every translation file sees the same source tree.
    _run_command(
        list(
            [
            _find_tool("pyside6-lupdate"),
            str(gui_root),
            "-ts",
            ]
        ) + [str(ts_file) for ts_file in ts_files]
    )

    ts_file: Path
    for ts_file in ts_files:
        _reactivate_manual_context_translations(ts_file=ts_file)
        _sync_tree_label_context(ts_file=ts_file, source_texts=tree_label_sources)

    # Compile each catalog to the qm file with the same stem in the same folder.
    for ts_file in ts_files:
        qm_file: Path = ts_file.with_suffix(".qm")
        _run_command(
            [
                _find_tool("pyside6-lrelease"),
                str(ts_file),
                "-qm",
                str(qm_file),
            ]
        )


if __name__ == "__main__":
    update_translations()
