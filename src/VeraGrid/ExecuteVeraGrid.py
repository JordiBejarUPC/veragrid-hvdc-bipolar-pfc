# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import os
import sys
import ctypes
import platform
import threading

PACKAGE_PARENT = '..'
SCRIPT_DIR = os.path.dirname(os.path.realpath(os.path.join(os.getcwd(), os.path.expanduser(__file__))))
sys.path.append(os.path.normpath(os.path.join(SCRIPT_DIR, PACKAGE_PARENT)))
from VeraGrid.__version__ import about_msg

# NOTE: For some reason I cannot begin to comprehend, the activation fails on windows if called before the GUI...
import VeraGridEngine.Utils.ThirdParty.gslv.gslv_activation

from PySide6.QtCore import QDirIterator, QResource
from PySide6.QtSvg import QSvgRenderer
from VeraGrid.Gui.Main.VeraGridMain import runVeraGrid
from VeraGrid.Gui.update_gui_all import update_all_icons

if platform.system() == 'Windows':
    # this makes the icon display properly under windows
    myappid = 'mycompany.myproduct.subproduct.version'  # arbitrary string
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)


def check_all_svgs() -> bool:
    """
    Iterate through all resources registered by icons_rc and check SVG validity.
    :returns: if any icon has errors
    """
    it = QDirIterator(":/Icons", QDirIterator.IteratorFlag.Subdirectories)
    bad_files = []

    while it.hasNext():
        path = it.next()
        if path.lower().endswith(".svg"):
            res = QResource(path)
            if not res.isValid():
                print(f"[MISSING] {path}")
                bad_files.append((path, "missing"))
                continue

            renderer = QSvgRenderer(path)
            if not renderer.isValid():
                print(f"[INVALID] {path}")
                bad_files.append((path, "invalid"))
            else:
                pass
                # print(f"[OK] {path}")

    print("\nSummary:")
    for path, status in bad_files:
        print(f"  {status.upper():<8} {path}")

    if not bad_files:
        print("✅ All SVG icons are valid!")

    if len(bad_files) > 0:
        update_all_icons()


if __name__ == "__main__":
    print('Loading VeraGrid...')
    print(about_msg)

    # Set the application style to the clear theme
    os.environ["QT_QUICK_CONTROLS_STYLE"] = "Basic"
    # os.environ["QT_QPA_PLATFORMTHEME"] = "qt5ct"  # this forces QT-only menus and look and feel
    threading.stack_size(134217728)
    runVeraGrid()
