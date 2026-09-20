# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""Reusable native Qt plot window and its small public plotting API."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import numpy as np
from PySide6 import QtCore, QtGui, QtWidgets

from VeraGrid.Gui.PlotDialogue.plot_dialogue_ui import Ui_PlotDialogue
from VeraGrid.Gui.PlotDialogue.plot_export import save_chart_image
from VeraGrid.Gui.Widgets.qt_chart_widget import GraphsWidget, PolarAngleUnit


class PlotDialogue(QtWidgets.QDialog):
    """Own one or more native QWidget charts in explicitly owned Qt tabs."""

    __slots__ = ('ui', 'chart', '_tab_charts', '_series_selector_override',
                 '_use_rhi_for_many_series')

    def __init__(self,
                 title: str = 'Plot',
                 parent: QtWidgets.QWidget | None = None,
                 use_rhi_for_many_series: bool = False) -> None:
        """Create the retained chart dialog and its Qt-owned child hierarchy.

        :param title: Initial dialog and chart title.
        :param parent: Optional Qt owner for the complete dialog hierarchy.
        :param use_rhi_for_many_series: Whether dense XY line series may use QRhi.
        :return: None.
        """
        QtWidgets.QDialog.__init__(self, parent)
        self.ui: Ui_PlotDialogue = Ui_PlotDialogue()
        self.ui.setupUi(self)
        self.chart: GraphsWidget = self.ui.plotwidget
        self._tab_charts: list[GraphsWidget] = [self.chart]
        self._series_selector_override: bool | None = None
        self._use_rhi_for_many_series: bool = use_rhi_for_many_series
        self.chart.set_rhi_line_rendering(enabled=use_rhi_for_many_series)
        self.ui.plotSplitter.setStretchFactor(0, 1)
        self.ui.plotSplitter.setStretchFactor(1, 0)
        self.setWindowTitle(title)
        self.chart.setTitle(title)

        # All callbacks are delivered in this dialog's GUI thread; no worker
        # or queued ownership crosses the chart lifetime boundary.
        self.ui.actionSaveImage.triggered.connect(self.save_image)
        self.ui.actionResetView.triggered.connect(self.center_data)
        self.ui.actionopencloseTree.triggered.connect(self._toggle_series_selector)
        self.ui.plotTabs.currentChanged.connect(self._refresh_series_selector)
        self.ui.seriesSearchLineEdit.textChanged.connect(self._filter_series_selector)
        self.ui.seriesListWidget.itemChanged.connect(self._set_series_visibility)
        self.ui.selectAllButton.clicked.connect(self.select_all_series)
        self.ui.selectNoneButton.clicked.connect(self.select_no_series)

    def done(self, result: int) -> None:
        """Release every tab buffer before Qt tears down the parent-child widgets.

        :param result: Qt dialog result code.
        :return: None.
        """
        # Stop list callbacks before Qt destroys its child items with this dialog.
        self.ui.seriesListWidget.blockSignals(True)
        self.ui.seriesListWidget.clear()
        self.ui.seriesListWidget.blockSignals(False)
        self.ui.seriesSelectorFrame.setVisible(False)
        chart: GraphsWidget
        for chart in self._tab_charts:
            chart.dispose()
        self._tab_charts.clear()
        QtWidgets.QDialog.done(self, result)

    def showEvent(self, event: QtGui.QShowEvent) -> None:
        """Refresh the optional series selector before Qt makes the dialog visible.

        :param event: Qt visibility event delivered on the dialog owner thread.
        :return: None.
        """
        self._refresh_series_selector()
        QtWidgets.QDialog.showEvent(self, event)

    def get_current_chart(self) -> GraphsWidget:
        """Return the chart owned by the currently selected tab.

        :return: Current tab chart, or the initial chart when no tab is selected.
        """
        current_index: int = self.ui.plotTabs.currentIndex()
        if 0 <= current_index < len(self._tab_charts):
            return self._tab_charts[current_index]
        else:
            return self.chart

    def add_tab(self, title: str) -> GraphsWidget:
        """Create one additional Qt-owned chart tab and make it current.

        :param title: Text displayed in the new tab.
        :return: Newly owned chart widget for the tab.
        """
        tab_page: QtWidgets.QWidget = QtWidgets.QWidget(parent=self.ui.plotTabs)
        tab_layout: QtWidgets.QVBoxLayout = QtWidgets.QVBoxLayout(tab_page)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        tab_chart: GraphsWidget = GraphsWidget(parent=tab_page)
        tab_chart.set_rhi_line_rendering(enabled=self._use_rhi_for_many_series)
        tab_layout.addWidget(tab_chart)
        self._tab_charts.append(tab_chart)
        tab_index: int = self.ui.plotTabs.addTab(tab_page, title)
        self.ui.plotTabs.setCurrentIndex(tab_index)
        self._refresh_series_selector()
        return tab_chart

    def set_current_tab_title(self, title: str) -> None:
        """Set the visible name of the selected plot tab.

        :param title: New text for the selected tab.
        :return: None.
        """
        tab_index: int = self.ui.plotTabs.currentIndex()
        if tab_index >= 0:
            self.ui.plotTabs.setTabText(tab_index, title)
        else:
            pass

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
        chart: GraphsWidget = self.get_current_chart()
        accepted: bool = chart.set_line_series(
            x_values=x_values,
            series_names=series_names,
            series_values=series_values,
            colors=colors,
        )
        if accepted:
            chart.setTitle(title)
            chart.set_axis_titles(x_axis_title, y_axis_title)
            self._refresh_series_selector()
            return True
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
        chart: GraphsWidget = self.get_current_chart()
        accepted: bool = chart.set_cumulative_area_series(
            x_values=x_values,
            series_names=series_names,
            series_values=series_values,
            colors=colors,
        )
        if accepted:
            chart.setTitle(title)
            chart.set_axis_titles(x_axis_title, y_axis_title)
            self._refresh_series_selector()
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
                         angle_unit: PolarAngleUnit = PolarAngleUnit.RADIANS,
                         connect_points: bool = True) -> bool:
        """Replace the chart with native polar lines and circular sample points.

        :param series_names: Visible legend name for each polar line.
        :param angle_values: Angle buffer for each series.
        :param radius_values: Non-negative radial buffer for each series.
        :param colors: Optional Qt colour for each polar line.
        :param title: Visible plot title.
        :param radius_title: Radial axis caption.
        :param angle_unit: Unit used by every angle buffer.
        :param connect_points: Whether consecutive polar samples are joined.
        :return: Whether the native chart accepted every finite buffer.
        """
        chart: GraphsWidget = self.get_current_chart()
        accepted: bool = chart.set_polar_series(
            series_names=series_names,
            angle_values=angle_values,
            radius_values=radius_values,
            colors=colors,
            angle_unit=angle_unit,
            connect_points=connect_points,
        )
        if accepted:
            chart.setTitle(title)
            chart.set_axis_titles('', radius_title)
            self._refresh_series_selector()
        else:
            pass
        return accepted

    def set_histogram(self,
                      values: Sequence[float] | np.ndarray,
                      bin_count: int,
                      title: str = '',
                      x_axis_title: str = '',
                      y_axis_title: str = '') -> bool:
        """Replace the selected tab with one native numeric histogram.

        :param values: Numeric samples from which bin frequencies are calculated.
        :param bin_count: Positive number of equal-width bins.
        :param title: Visible chart title.
        :param x_axis_title: Horizontal numeric axis caption.
        :param y_axis_title: Vertical frequency axis caption.
        :return: Whether the chart accepted the complete finite sample set.
        """
        chart: GraphsWidget = self.get_current_chart()
        accepted: bool = chart.set_histogram(
            values=values,
            bin_count=bin_count,
            name='',
        )
        if accepted:
            chart.setTitle(title)
            chart.set_axis_titles(x_axis_title, y_axis_title)
            self._refresh_series_selector()
        else:
            pass
        return accepted

    def add_histogram_tab(self,
                          tab_title: str,
                          values: Sequence[float] | np.ndarray,
                          bin_count: int,
                          title: str = '',
                          x_axis_title: str = '',
                          y_axis_title: str = '') -> bool:
        """Create a tab that owns one native numeric histogram.

        :param tab_title: Text displayed for the new tab.
        :param values: Numeric samples from which bin frequencies are calculated.
        :param bin_count: Positive number of equal-width bins.
        :param title: Visible chart title.
        :param x_axis_title: Horizontal numeric axis caption.
        :param y_axis_title: Vertical frequency axis caption.
        :return: Whether the new tab chart accepted the complete finite sample set.
        """
        tab_chart: GraphsWidget = self.add_tab(title=tab_title)
        accepted: bool = tab_chart.set_histogram(
            values=values,
            bin_count=bin_count,
            name='',
        )
        if accepted:
            tab_chart.setTitle(title)
            tab_chart.set_axis_titles(x_axis_title, y_axis_title)
            self._refresh_series_selector()
            return True
        else:
            return False

    def _refresh_series_selector(self, current_index: int = -1) -> None:
        """Show a coloured searchable legend only for charts with many named series.

        :param current_index: Tab index provided by Qt and otherwise unused.
        :return: None.
        """
        _ = current_index
        chart: GraphsWidget = self.get_current_chart()
        named_series_count: int = 0
        series_index: int
        for series_index in range(chart.get_series_count()):
            if chart.get_series_name(series_index=series_index) != '':
                named_series_count += 1
            else:
                pass

        automatic_visibility: bool = named_series_count > 20
        selector_visible: bool = automatic_visibility
        if self._series_selector_override is not None:
            selector_visible = self._series_selector_override
        else:
            pass
        chart.set_legend_visible(visible=not selector_visible)
        self.ui.seriesSelectorFrame.setVisible(selector_visible)
        self.ui.actionopencloseTree.setChecked(selector_visible)
        self.ui.seriesListWidget.blockSignals(True)
        self.ui.seriesListWidget.clear()
        for series_index in range(chart.get_series_count()):
            series_name: str = chart.get_series_name(series_index=series_index)
            if series_name != '':
                list_item: QtWidgets.QListWidgetItem = QtWidgets.QListWidgetItem(series_name)
                list_item.setData(QtCore.Qt.ItemDataRole.UserRole, series_index)
                list_item.setFlags(list_item.flags() | QtCore.Qt.ItemFlag.ItemIsUserCheckable)
                list_item.setCheckState(
                    QtCore.Qt.CheckState.Checked if chart.get_series_visible(series_index=series_index)
                    else QtCore.Qt.CheckState.Unchecked,
                )
                list_item.setForeground(QtGui.QBrush(chart.get_series_color(series_index=series_index)))
                self.ui.seriesListWidget.addItem(list_item)
            else:
                pass
        self.ui.seriesListWidget.blockSignals(False)
        self._filter_series_selector(text=self.ui.seriesSearchLineEdit.text())

    def _toggle_series_selector(self, visible: bool) -> None:
        """Apply the toolbar action's requested series-list visibility.

        :param visible: Checked state of the list visibility action.
        :return: None.
        """
        self._series_selector_override = visible
        self.ui.seriesSelectorFrame.setVisible(visible)
        self.get_current_chart().set_legend_visible(visible=not visible)

    def select_all_series(self, checked: bool = False) -> None:
        """Show every series currently listed for the selected chart.

        :param checked: Button state ignored by this momentary action.
        :return: None.
        """
        _ = checked
        self._set_all_series_visibility(visible=True)

    def select_no_series(self, checked: bool = False) -> None:
        """Hide every series currently listed for the selected chart.

        :param checked: Button state ignored by this momentary action.
        :return: None.
        """
        _ = checked
        self._set_all_series_visibility(visible=False)

    def _set_all_series_visibility(self, visible: bool) -> None:
        """Update list check states and chart data without item callbacks per row.

        :param visible: Whether every named series should be rendered.
        :return: None.
        """
        chart: GraphsWidget = self.get_current_chart()
        self.ui.seriesListWidget.blockSignals(True)
        for item_index in range(self.ui.seriesListWidget.count()):
            list_item: QtWidgets.QListWidgetItem = self.ui.seriesListWidget.item(item_index)
            check_state: QtCore.Qt.CheckState = (
                QtCore.Qt.CheckState.Checked if visible else QtCore.Qt.CheckState.Unchecked
            )
            list_item.setCheckState(check_state)
            series_index_value: object = list_item.data(QtCore.Qt.ItemDataRole.UserRole)
            if isinstance(series_index_value, int):
                chart.set_series_visible(series_index=series_index_value, visible=visible)
            else:
                pass
        self.ui.seriesListWidget.blockSignals(False)
        chart.update()
        self._filter_series_selector(text=self.ui.seriesSearchLineEdit.text())

    def _filter_series_selector(self, text: str) -> None:
        """Hide legend rows that do not match the user search text.

        :param text: Case-insensitive text that must occur in a series name.
        :return: None.
        """
        search_text: str = text.casefold()
        item_index: int
        for item_index in range(self.ui.seriesListWidget.count()):
            list_item: QtWidgets.QListWidgetItem = self.ui.seriesListWidget.item(item_index)
            list_item.setHidden(search_text not in list_item.text().casefold())

    def _set_series_visibility(self, list_item: QtWidgets.QListWidgetItem) -> None:
        """Apply one check box change to the currently selected chart series.

        :param list_item: Qt-owned legend row whose check state changed.
        :return: None.
        """
        series_index_value: object = list_item.data(QtCore.Qt.ItemDataRole.UserRole)
        if isinstance(series_index_value, int):
            visible: bool = list_item.checkState() == QtCore.Qt.CheckState.Checked
            self.get_current_chart().set_series_visible(series_index=series_index_value, visible=visible)
        else:
            pass

    def center_data(self, checked: bool = False) -> None:
        """Reset the chart zoom and pan from the toolbar action.

        :param checked: QAction state ignored by the non-checkable action.
        :return: None.
        """
        _ = checked
        self.get_current_chart().reset_viewport()

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
        return save_chart_image(chart=self.get_current_chart(), file_name=file_name)
