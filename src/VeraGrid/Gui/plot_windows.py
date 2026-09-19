# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from matplotlib.backend_bases import FigureManagerBase
from matplotlib import pyplot as plt
from matplotlib.figure import Figure


def show_matplotlib_window(figure: Figure, title: str) -> None:
    """
    Show one pyplot-managed figure in its standalone Matplotlib window.

    :param figure: Figure created by ``matplotlib.pyplot.figure``.
    :param title: Window title.
    :return: None.
    """
    # Re-register a window if the user closed it and later asks to show it again.
    plt.figure(figure)
    manager: FigureManagerBase | None = figure.canvas.manager
    if manager is not None:
        manager.set_window_title(title)
    else:
        pass
    plt.show(block=False)


def close_matplotlib_windows(figures: list[Figure]) -> None:
    """Close standalone Matplotlib windows owned by one caller.

    :param figures: Caller-owned figure list.
    :return: None.
    """
    figures_to_close: list[Figure] = list(figures)
    figures.clear()
    figure: Figure
    for figure in figures_to_close:
        plt.close(figure)
