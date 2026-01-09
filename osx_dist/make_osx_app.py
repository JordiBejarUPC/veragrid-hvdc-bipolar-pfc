#!/usr/bin/env python3
"""
Creates a macOS .app that launches a Terminal window
and runs a configurable system command (e.g. "veragrid"),
with a custom app icon.
"""

from pathlib import Path
import plistlib
import shutil
import stat
import subprocess
import sys
from VeraGrid.__version__ import __VeraGrid_VERSION__
# ============================================================================
# CONFIGURATION
# ============================================================================

APP_NAME = "VeraGrid"
BUNDLE_ID = "com.eroots.veragrid.cli"
VERSION = __VeraGrid_VERSION__
MIN_MACOS = "12.0"

# 🔴 Terminal command to run
TERMINAL_COMMAND = "veragrid"

# 🔴 ICON PATH (PNG or ICNS)
ICON_PATH = Path("../pics/VeraGrid_icon.png")

OUTPUT_DIR = Path("../osx_dist")
OVERWRITE_EXISTING = True
ENABLE_CODESIGN = True

# ============================================================================


def ensure_macos():
    if sys.platform != "darwin":
        raise RuntimeError("This script must be run on macOS")


def make_executable(path: Path):
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def run(cmd):
    subprocess.check_call(cmd)


def write_info_plist(plist_path: Path, icon_name: str | None):
    plist = {
        "CFBundleName": APP_NAME,
        "CFBundleDisplayName": APP_NAME,
        "CFBundleIdentifier": BUNDLE_ID,
        "CFBundleVersion": VERSION,
        "CFBundleShortVersionString": VERSION,
        "CFBundleExecutable": APP_NAME,
        "CFBundlePackageType": "APPL",
        "LSMinimumSystemVersion": MIN_MACOS,
    }

    if icon_name:
        plist["CFBundleIconFile"] = icon_name  # no extension

    with plist_path.open("wb") as f:
        plistlib.dump(plist, f, sort_keys=False)


def create_icns_from_png(png_path: Path, icns_path: Path):
    iconset = icns_path.parent / f"{icns_path.stem}.iconset"
    iconset.mkdir(parents=True, exist_ok=True)

    sizes = [
        (16, "icon_16x16.png"),
        (32, "icon_16x16@2x.png"),
        (32, "icon_32x32.png"),
        (64, "icon_32x32@2x.png"),
        (128, "icon_128x128.png"),
        (256, "icon_128x128@2x.png"),
        (256, "icon_256x256.png"),
        (512, "icon_256x256@2x.png"),
        (512, "icon_512x512.png"),
        (1024, "icon_512x512@2x.png"),
    ]

    for px, name in sizes:
        run([
            "sips", "-z", str(px), str(px),
            str(png_path), "--out", str(iconset / name)
        ])

    run(["iconutil", "-c", "icns", str(iconset), "-o", str(icns_path)])
    shutil.rmtree(iconset, ignore_errors=True)


def create_launcher(launcher_path: Path):
    escaped_cmd = TERMINAL_COMMAND.replace('"', '\\"')

    script = f"""#!/bin/bash

/usr/bin/osascript <<EOF
tell application "Terminal"
    activate
    do script "{escaped_cmd}; exec $SHELL"
end tell
EOF
"""

    launcher_path.write_text(script, encoding="utf-8")
    make_executable(launcher_path)


def ad_hoc_codesign(app_path: Path):
    run(["codesign", "--force", "--deep", "--sign", "-", str(app_path)])
    run(["codesign", "--verify", "--verbose", str(app_path)])


def make_app():
    ensure_macos()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    app_path = OUTPUT_DIR / f"{APP_NAME}.app"

    if app_path.exists():
        if OVERWRITE_EXISTING:
            shutil.rmtree(app_path)
        else:
            raise RuntimeError("App already exists")

    contents = app_path / "Contents"
    macos_dir = contents / "MacOS"
    resources_dir = contents / "Resources"

    macos_dir.mkdir(parents=True)
    resources_dir.mkdir(parents=True)

    # ---- Icon handling ----
    icon_name = None
    if ICON_PATH:
        if not ICON_PATH.exists():
            raise RuntimeError(f"Icon not found: {ICON_PATH}")

        icns_path = resources_dir / f"{APP_NAME}.icns"

        if ICON_PATH.suffix.lower() == ".icns":
            shutil.copy2(ICON_PATH, icns_path)
        else:
            create_icns_from_png(ICON_PATH, icns_path)

        icon_name = APP_NAME

    write_info_plist(contents / "Info.plist", icon_name)
    create_launcher(macos_dir / APP_NAME)

    if ENABLE_CODESIGN:
        ad_hoc_codesign(app_path)

    print("\nDONE")
    print(f"App created at: {app_path}")
    print(f"Terminal command: {TERMINAL_COMMAND}")


if __name__ == "__main__":
    make_app()
