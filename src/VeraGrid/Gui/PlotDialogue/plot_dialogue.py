# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""Reusable native Qt plot window and its small public plotting API."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import numpy as np
from PySide6 import QtWidgets

from VeraGrid.Gui.PlotDialogue.plot_dialogue_ui import Ui_PlotDialogue
from VeraGrid.Gui.PlotDialogue.plot_export import save_chart_image
from VeraGrid.Gui.Widgets.qt_chart_widget import GraphsWidget, PolarAngleUnit


class PlotDialogue(QtWidgets.QDialog):
    """Own one QWidget chart and expose line, area, and polar plot modes."""

    __slots__ = ('ui', 'chart')

    def __init__(self, title: str = 'Plot', parent: QtWidgets.QWidget | None = None) -> None:
        """Create the retained chart dialog and its Qt-owned child hierarchy.

        :param title: Initial dialog and chart title.
        :param parent: Optional Qt owner for the complete dialog hierarchy.
        :return: None.
        """
        QtWidgets.QDialog.__init__(self, parent)
        self.ui: Ui_PlotDialogue = Ui_PlotDialogue()
        self.ui.setupUi(self)
        self.chart: GraphsWidget = self.ui.plotwidget
        self.setWindowTitle(title)
        self.chart.setTitle(title)

        # All callbacks are delivered in this dialog's GUI thread; no worker
        # or queued ownership crosses the chart lifetime boundary.
        self.ui.actionSaveImage.triggered.connect(self.save_image)
        self.ui.actionResetView.triggered.connect(self.center_data)
        self.ui.buttonBox.rejected.connect(self.reject)

    def done(self, result: int) -> None:
        """Release chart buffers before Qt tears down its parent-child widgets.

        :param result: Qt dialog result code.
        :return: None.
        """
        self.chart.dispose()
        QtWidgets.QDialog.done(self, result)

    def set_line_series(self,
                        x_values: Sequence[float] | np.ndarray,
                        series_names: Sequence[str],
                        series_values: Sequence[Sequence[float] | np.ndarray],
                        colors: Sequence[str | None] | None = None,
                        title: str = '',
                        x_axis_title: str = '',
                        y_axis_title: str = '') -> bool:
        """Replace the chart with one or more line series sharing an X axis.

        :param x_values: Numeric or NumPy datetime coordinates.
        :param series_names: Visible legend name for each line.
        :param series_values: Y value buffer for each line.
        :param colors: Optional Qt colour for each line.
        :param title: Visible plot title.
        :param x_axis_title: Horizontal axis caption.
        :param y_axis_title: Vertical axis caption.
        :return: Whether every buffer was shape-compatible.
        """
        series_count: int = len(series_names)
        if series_count > 0 and len(series_values) == series_count:
            if colors is None:
                color_values: list[str | None] = list()
                series_index: int
                for series_index in range(series_count):
                    color_values.append(None)
            elif len(colors) == series_count:
                color_values = list(colors)
            else:
                return False

            valid: bool = True
            series_index: int
            for series_index in range(series_count):
                if len(series_values[series_index]) == len(x_values):
                    pass
                else:
                    valid = False

            if valid:
                self.chart.clear()
                for series_index in range(series_count):
                    self.chart.add_line_series(
                        name=str(series_names[series_index]),
                        x_values=x_values,
                        y_values=series_values[series_index],
                        color=color_values[series_index],
                    )
                self.chart.setTitle(title)
                self.chart.set_axis_titles(x_axis_title, y_axis_title)
                return True
            else:
                return False
        else:
            return False

    def set_time_series(self,
                        time_values: Sequence[float] | np.ndarray,
                        series_names: Sequence[str],
                        series_values: Sequence[Sequence[float] | np.ndarray],
                        colors: Sequence[str | None] | None = None,
                        title: str = '',
                        y_axis_title: str = '') -> bool:
        """Replace the chart with lines using a NumPy datetime X axis.

        :param time_values: NumPy datetime coordinates or numeric timestamps.
        :param series_names: Visible legend name for each line.
        :param series_values: Y value buffer for each line.
        :param colors: Optional Qt colour for each line.
        :param title: Visible plot title.
        :param y_axis_title: Vertical axis caption.
        :return: Whether every buffer was shape-compatible.
        """
        return self.set_line_series(
            x_values=time_values,
            series_names=series_names,
            series_values=series_values,
            colors=colors,
            title=title,
            x_axis_title=self.tr('Time'),
            y_axis_title=y_axis_title,
        )

    def set_cumulative_area_series(self,
                                   x_values: Sequence[float] | np.ndarray,
                                   series_names: Sequence[str],
                                   series_values: Sequence[Sequence[float] | np.ndarray],
                                   colors: Sequence[str | None] | None = None,
                                   title: str = '',
                                   x_axis_title: str = '',
                                   y_axis_title: str = '') -> bool:
        """Replace the chart with stacked cumulative areas sharing one X axis.

        :param x_values: Numeric or NumPy datetime coordinates.
        :param series_names: Visible legend name for each cumulative band.
        :param series_values: Y value buffer for each cumulative band.
        :param colors: Optional Qt colour for each band.
        :param title: Visible plot title.
        :param x_axis_title: Horizontal axis caption.
        :param y_axis_title: Vertical axis caption.
        :return: Whether the native chart accepted every finite buffer.
        """
        accepted: bool = self.chart.set_cumulative_area_series(
            x_values=x_values,
            series_names=series_names,
            series_values=series_values,
            colors=colors,
        )
        if accepted:
            self.chart.setTitle(title)
            self.chart.set_axis_titles(x_axis_title, y_axis_title)
        else:
            pass
        return accepted

    def set_polar_series(self,
                         series_names: Sequence[str],
                         angle_values: Sequence[Sequence[float] | np.ndarray],
                         radius_values: Sequence[Sequence[float] | np.ndarray],
                         colors: Sequence[str | None] | None = None,
                         title: str = '',
                         radius_title: str = '',
                         angle_unit: PolarAngleUnit = PolarAngleUnit.RADIANS) -> bool:
        """Replace the chart with native polar lines and circular sample points.

        :param series_names: Visible legend name for each polar line.
        :param angle_values: Angle buffer for each series.
        :param radius_values: Non-negative radial buffer for each series.
        :param colors: Optional Qt colour for each polar line.
        :param title: Visible plot title.
        :param radius_title: Radial axis caption.
        :param angle_unit: Unit used by every angle buffer.
        :return: Whether the native chart accepted every finite buffer.
        """
        accepted: bool = self.chart.set_polar_series(
            series_names=series_names,
            angle_values=angle_values,
            radius_values=radius_values,
            colors=colors,
            angle_unit=angle_unit,
        )
        if accepted:
            self.chart.setTitle(title)
            self.chart.set_axis_titles('', radius_title)
        else:
            pass
        return accepted

    def center_data(self, checked: bool = False) -> None:
        """Reset the chart zoom and pan from the toolbar action.

        :param checked: QAction state ignored by the non-checkable action.
        :return: None.
        """
        _ = checked
        self.chart.reset_viewport()

    def save_image(self, checked: bool = False) -> None:
        """Ask for a PNG or SVG path and export the current native chart.

        :param checked: QAction state ignored by the non-checkable action.
        :return: None.
        """
        _ = checked
        file_name: str
        selected_filter: str
        file_name, selected_filter = QtWidgets.QFileDialog.getSaveFileName(
            self,
            self.tr('Save plot image'),
            '',
            self.tr('SVG image (*.svg);;PNG image (*.png)'),
        )
        if file_name != '':
            output_path: Path = Path(file_name)
            if output_path.suffix == '':
                if selected_filter.startswith('SVG'):
                    output_path = output_path.with_suffix('.svg')
                else:
                    output_path = output_path.with_suffix('.png')
            else:
                pass
            self.save_image_to_file(file_name=str(output_path))
        else:
            pass

    def save_image_to_file(self, file_name: str) -> bool:
        """Export the current chart without opening a file dialog.

        :param file_name: Target PNG or SVG filename.
        :return: Whether a non-empty image file was created.
        """
        return save_chart_image(chart=self.chart, file_name=file_name)
