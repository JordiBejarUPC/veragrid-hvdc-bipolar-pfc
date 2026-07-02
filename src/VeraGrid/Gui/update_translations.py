from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


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


def update_translations() -> None:
    """
    Refresh the application ``.ts`` file and compile ``.qm`` outputs.

    :returns: Nothing.
    """
    gui_root: Path = Path(__file__).resolve().parent
    translations_dir: Path = gui_root / "translations"
    ts_file: Path = translations_dir / "veragrid_es.ts"

    translations_dir.mkdir(parents=True, exist_ok=True)

    _run_command(
        [
            _find_tool("pyside6-lupdate"),
            str(gui_root),
            "-ts",
            str(ts_file),
        ]
    )
    _run_command(
        [
            _find_tool("pyside6-lrelease"),
            str(ts_file),
            "-qm",
            str(translations_dir / "veragrid_es.qm"),
        ]
    )


if __name__ == "__main__":
    update_translations()
