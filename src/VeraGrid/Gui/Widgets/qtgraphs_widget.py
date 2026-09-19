# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from collections.abc import Sequence
from pathlib import Path

import numpy as np
from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtGraphs import (
    QAbstractAxis,
    QAbstractSeries,
    QBarCategoryAxis,
    QBarSeries,
    QBarSet,
    QDateTimeAxis,
    QGraphsTheme,
    QLineSeries,
    QScatterSeries,
    QValueAxis,
    QXYSeries,
)
from PySide6.QtQml import QQmlComponent
from PySide6.QtQuick import QQuickItem
from PySide6.QtQuickWidgets import QQuickWidget


class GraphsWidget(QtWidgets.QWidget):
    """Host a Qt Graphs view in an ordinary Qt Widgets layout."""

    __slots__ = (
        "quick_widget",
        "graph_view",
        "axis_x",
        "axis_y",
        "title_label",
        "legend_layout",
        "legend_container",
        "_legend_items",
        "_circle_marker_delegate",
        "_theme",
        "_series",
        "_has_points",
        "_x_min",
        "_x_max",
        "_y_min",
        "_y_max",
        "_pan_position",
        "_disposed",
    )

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        """Create the QWidget host, then configure axes and theme in Python.

        :param parent: Parent Qt widget.
        :return: None.
        """
        QtWidgets.QWidget.__init__(self, parent)
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Expanding,
        )

        self.title_label: QtWidgets.QLabel = QtWidgets.QLabel(self)
        self.legend_container: QtWidgets.QWidget = QtWidgets.QWidget(self)
        self.legend_layout: QtWidgets.QHBoxLayout = QtWidgets.QHBoxLayout(self.legend_container)
        self.legend_layout.setContentsMargins(4, 0, 4, 0)
        self.legend_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
        self._legend_items: list[QtWidgets.QLabel] = list()
        self._pan_position: QtCore.QPointF | None = None
        self._disposed: bool = False
        self.quick_widget: QQuickWidget = QQuickWidget(self)
        self.quick_widget.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Expanding,
        )
        self.quick_widget.setResizeMode(QQuickWidget.ResizeMode.SizeRootObjectToView)
        self.quick_widget.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        self.quick_widget.setMouseTracking(True)
        self.quick_widget.setToolTip(self.tr("Mouse wheel: zoom\nLeft drag: pan\nDouble-click: reset view"))
        self.quick_widget.installEventFilter(self)

        # Keep Python-created axes and theme alive while the QML view references them.
        self.axis_x: QAbstractAxis = QValueAxis(self)
        self.axis_y: QValueAxis = QValueAxis(self)
        self._theme: QGraphsTheme = QGraphsTheme(self)
        initial_properties: dict[str, object] = dict(
            axisX=self.axis_x,
            axisY=self.axis_y,
            theme=self._theme,
        )
        self.quick_widget.setInitialProperties(initial_properties)

        # Keep only the GraphsView's visual structure in QML; chart data and
        # axes are Python-owned so callers can configure them with Qt APIs.
        qml_path: Path = Path(__file__).with_name("GraphsView.qml")
        self.quick_widget.setSource(QtCore.QUrl.fromLocalFile(str(qml_path)))
        self.graph_view: QQuickItem | None = self.quick_widget.rootObject()
        marker_path: Path = Path(__file__).with_name("CirclePoint.qml")
        marker_delegate: QQmlComponent = QQmlComponent(
            self.quick_widget.engine(),
            QtCore.QUrl.fromLocalFile(str(marker_path)),
            self,
        )
        if marker_delegate.isReady():
            self._circle_marker_delegate: QQmlComponent | None = marker_delegate
        else:
            self._circle_marker_delegate = None

        if self.graph_view is not None:
            self.graph_view.setProperty("marginLeft", 58)
            self.graph_view.setProperty("marginBottom", 46)
            self.graph_view.setProperty("marginRight", 18)
            self.graph_view.setProperty("marginTop", 8)
        else:
            pass
        self.apply_theme(dark=self.palette().color(QtGui.QPalette.ColorRole.Window).lightness() < 128)

        self._series: list[QAbstractSeries] = list()
        self._has_points: bool = False
        self._x_min: float = 0.0
        self._x_max: float = 1.0
        self._y_min: float = 0.0
        self._y_max: float = 1.0

        self.axis_x.setRange(0.0, 1.0)
        self.axis_y.setRange(0.0, 1.0)

        layout: QtWidgets.QVBoxLayout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.title_label, 0)
        layout.addWidget(self.legend_container, 0)
        layout.addWidget(self.quick_widget, 1)
        self.legend_container.hide()

    def apply_theme(self, dark: bool) -> None:
        """Set chart palette colors from Python for the active UI theme.

        :param dark: Whether the surrounding application uses a dark palette.
        :return: None.
        """
        if dark:
            background_color: QtGui.QColor = QtGui.QColor("#171c24")
            plot_color: QtGui.QColor = QtGui.QColor("#171c24")
            label_color: QtGui.QColor = QtGui.QColor("#e7edf5")
            color_scheme: QGraphsTheme.ColorScheme = QGraphsTheme.ColorScheme.Dark
        else:
            background_color = QtGui.QColor("#ffffff")
            plot_color = QtGui.QColor("#f7fbff")
            label_color = QtGui.QColor("#17324a")
            color_scheme = QGraphsTheme.ColorScheme.Light

        self._theme.setColorScheme(color_scheme)
        self._theme.setBackgroundColor(background_color)
        self._theme.setPlotAreaBackgroundColor(plot_color)
        self._theme.setLabelTextColor(label_color)
        self._theme.setGridVisible(True)
        self.axis_x.setTitleColor(label_color)
        self.axis_y.setTitleColor(label_color)

        if self.graph_view is not None:
            self.graph_view.setProperty("theme", self._theme)
        else:
            pass

    def setTitle(self, title: str) -> None:
        """Set the visible plot title.

        :param title: Plot title.
        :return: None.
        """
        self.title_label.setText(title)

    def set_axis_titles(self, x_title: str, y_title: str) -> None:
        """Set the labels shown on both axes.

        :param x_title: Horizontal axis title.
        :param y_title: Vertical axis title.
        :return: None.
        """
        self.axis_x.setTitleText(x_title)
        self.axis_x.setTitleVisible(bool(x_title))
        self.axis_y.setTitleText(y_title)
        self.axis_y.setTitleVisible(bool(y_title))

    def clear(self, force: bool = False) -> None:
        """Remove all series and reset the numeric axes.

        :param force: Accepted for compatibility with the former plot widget.
        :return: None.
        """
        _ = force
        if self.graph_view is not None:
            series: QAbstractSeries
            for series in self._series:
                # Detach first and defer QObject destruction so the Quick renderer can finish removal.
                self.graph_view.removeSeries(series)
                series.deleteLater()
            self._series.clear()
        else:
            pass

        legend_item: QtWidgets.QLabel
        for legend_item in self._legend_items:
            self.legend_layout.removeWidget(legend_item)
            legend_item.deleteLater()
        self._legend_items.clear()
        self.legend_container.hide()

        if not self._disposed:
            self._ensure_numeric_axes()
        else:
            pass
        self._has_points = False
        self._x_min = 0.0
        self._x_max = 1.0
        self._y_min = 0.0
        self._y_max = 1.0
        self._set_axis_ranges()

    def replace_xy_series_data(
            self,
            series_data: Sequence[tuple[np.ndarray, np.ndarray, str | None]]) -> bool:
        """Replace point arrays on existing XY series without destroying them.

        :param series_data: New X values, Y values, and optional colors in series order.
        :return: Whether every existing series was updated.
        """
        if self.graph_view is not None and len(series_data) == len(self._series):
            # Validate and filter the whole replacement before changing any renderer-owned series.
            prepared_data: list[tuple[QXYSeries, np.ndarray, np.ndarray, str | None]] = list()
            series_index: int
            series_values: tuple[np.ndarray, np.ndarray, str | None]
            for series_index, series_values in enumerate(series_data):
                series: QAbstractSeries = self._series[series_index]
                if isinstance(series, QXYSeries):
                    x_data: np.ndarray = np.asarray(series_values[0], dtype=float)
                    y_data: np.ndarray = np.asarray(series_values[1], dtype=float)
                    if len(x_data) == len(y_data):
                        finite_mask: np.ndarray = np.isfinite(x_data) & np.isfinite(y_data)
                        prepared_data.append((series,
                                              x_data[finite_mask],
                                              y_data[finite_mask],
                                              series_values[2]))
                    else:
                        return False
                else:
                    return False

            # Start new ranges from the replacement data so a rerun can zoom in as well as out.
            self._has_points = False
            self._x_min = 0.0
            self._x_max = 1.0
            self._y_min = 0.0
            self._y_max = 1.0
            series_entry: tuple[QXYSeries, np.ndarray, np.ndarray, str | None]
            for series_entry in prepared_data:
                series: QXYSeries = series_entry[0]
                x_data: np.ndarray = series_entry[1]
                y_data: np.ndarray = series_entry[2]
                color: str | None = series_entry[3]
                if len(x_data) > 0:
                    series.replaceNp(x_data, y_data)
                else:
                    series.clear()
                if color is not None:
                    series.setColor(QtGui.QColor(color))
                else:
                    pass
                # Rebuild shared limits from each series after the native data replacement.
                if len(x_data) > 0:
                    self._include_points(x_data=x_data, y_data=y_data)
                else:
                    pass

            if not self._has_points:
                self._set_axis_ranges()
            else:
                pass
            return True
        else:
            return False

    def add_line_series(self,
                        name: str,
                        x_values: Sequence[float] | np.ndarray,
                        y_values: Sequence[float] | np.ndarray,
                        color: str | None = None) -> None:
        """Add one line series from paired finite numeric values.

        :param name: Series name used by the Graphs view.
        :param x_values: Horizontal data values.
        :param y_values: Vertical data values.
        :param color: Optional line color in Qt color syntax.
        :return: None.
        """
        raw_x_values: np.ndarray = np.asarray(x_values)
        if np.issubdtype(raw_x_values.dtype, np.datetime64):
            x_data: np.ndarray = raw_x_values.astype("datetime64[ms]").astype(np.int64).astype(float)
            x_data[np.isnat(raw_x_values)] = np.nan
            self._ensure_datetime_axis()
        else:
            x_data = np.asarray(x_values, dtype=float)

        y_data: np.ndarray = np.asarray(y_values, dtype=float)
        self._add_xy_series(series_type=QLineSeries,
                            name=name,
                            x_data=x_data,
                            y_data=y_data,
                            color=color)

    def add_scatter_series(self,
                           name: str,
                           x_values: Sequence[float] | np.ndarray,
                           y_values: Sequence[float] | np.ndarray,
                           color: str | None = None) -> None:
        """Add one scatter series from paired finite numeric values.

        :param name: Series name used by the Graphs view.
        :param x_values: Horizontal data values.
        :param y_values: Vertical data values.
        :param color: Optional marker color in Qt color syntax.
        :return: None.
        """
        x_data: np.ndarray = np.asarray(x_values, dtype=float)
        y_data: np.ndarray = np.asarray(y_values, dtype=float)
        self._add_xy_series(series_type=QScatterSeries,
                            name=name,
                            x_data=x_data,
                            y_data=y_data,
                            color=color)

    def add_horizontal_bar_series(self,
                                  labels: Sequence[str],
                                  values: Sequence[float] | np.ndarray,
                                  positive_color: str,
                                  negative_color: str) -> None:
        """Add category bars with positive and negative colors.

        :param labels: Category labels in display order.
        :param values: Bar values paired with ``labels``.
        :param positive_color: Bar color for zero and positive values.
        :param negative_color: Bar color for negative values.
        :return: None.
        """
        value_data: np.ndarray = np.asarray(values, dtype=float)

        if self.graph_view is not None and len(labels) == len(value_data) and len(value_data) > 0:
            finite_mask: np.ndarray = np.isfinite(value_data)
            valid_values: np.ndarray = value_data[finite_mask]
            valid_labels: list[str] = [str(labels[index]) for index in range(len(labels)) if finite_mask[index]]

            if len(valid_values) > 0:
                self._ensure_bar_axes(labels=valid_labels)

                # Keep Qt ownership on this GUI widget while the GraphsView uses the series.
                bar_series: QBarSeries = QBarSeries(self)
                positive_set: QBarSet = QBarSet(self.tr("Positive"), bar_series)
                negative_set: QBarSet = QBarSet(self.tr("Negative"), bar_series)
                positive_set.setColor(QtGui.QColor(positive_color))
                negative_set.setColor(QtGui.QColor(negative_color))
                positive_set.append(np.maximum(valid_values, 0.0).tolist())
                negative_set.append(np.minimum(valid_values, 0.0).tolist())
                bar_series.append(positive_set)
                bar_series.append(negative_set)
                bar_series.setBarsType(QBarSeries.BarsType.Stacked)
                self.graph_view.addSeries(bar_series)
                self._series.append(bar_series)
                self._add_legend_entry(name=self.tr("Positive"), color=QtGui.QColor(positive_color))
                self._add_legend_entry(name=self.tr("Negative"), color=QtGui.QColor(negative_color))

                self._x_min = 0.0
                self._x_max = float(len(valid_values) - 1)
                self._y_min = min(0.0, float(np.min(valid_values)))
                self._y_max = max(0.0, float(np.max(valid_values)))
                self._has_points = True
                self._set_axis_ranges()
            else:
                pass
        else:
            pass

    def _ensure_bar_axes(self, labels: Sequence[str]) -> None:
        """Configure category/value axes and horizontal chart orientation.

        :param labels: Category labels for the horizontal axis.
        :return: None.
        """
        if self.graph_view is not None and not isinstance(self.axis_x, QBarCategoryAxis):
            x_title: str = self.axis_x.titleText()
            y_title: str = self.axis_y.titleText()
            self.axis_x.deleteLater()
            self.axis_y.deleteLater()
            self.axis_x = QBarCategoryAxis(self)
            self.axis_y = QValueAxis(self)
            self.axis_x.setTitleText(x_title)
            self.axis_y.setTitleText(y_title)
            self.graph_view.setProperty("axisX", self.axis_x)
            self.graph_view.setProperty("axisY", self.axis_y)
            self.graph_view.setProperty("orientation", QtCore.Qt.Orientation.Horizontal)
        else:
            pass

        if isinstance(self.axis_x, QBarCategoryAxis):
            self.axis_x.clear()
            self.axis_x.append(list(labels))
        else:
            pass

    def _ensure_numeric_axes(self) -> None:
        """Restore numeric axes after a category bar chart.

        :return: None.
        """
        if self.graph_view is not None:
            if not isinstance(self.axis_x, QValueAxis):
                x_title: str = self.axis_x.titleText()
                self.axis_x.deleteLater()
                self.axis_x = QValueAxis(self)
                self.axis_x.setTitleText(x_title)
                self.graph_view.setProperty("axisX", self.axis_x)
            else:
                pass

            self.graph_view.setProperty("orientation", QtCore.Qt.Orientation.Vertical)
        else:
            pass

    def _ensure_datetime_axis(self) -> None:
        """Use calendar labels when the line series uses datetime x values.

        :return: None.
        """
        if self.graph_view is not None and not isinstance(self.axis_x, QDateTimeAxis):
            x_title: str = self.axis_x.titleText()
            self.axis_x.deleteLater()
            self.axis_x = QDateTimeAxis(self)
            self.axis_x.setLabelFormat("yyyy-MM-dd")
            self.axis_x.setTitleText(x_title)
            self.graph_view.setProperty("axisX", self.axis_x)
        else:
            pass

    def _add_xy_series(self,
                       series_type: type[QLineSeries] | type[QScatterSeries],
                       name: str,
                       x_data: np.ndarray,
                       y_data: np.ndarray,
                       color: str | None) -> None:
        """Create one Graphs series after validating its point arrays.

        :param series_type: Qt Graphs line or scatter series class.
        :param name: Visible series name.
        :param x_data: Horizontal values.
        :param y_data: Vertical values.
        :param color: Optional Qt color string.
        :return: None.
        """
        if self.graph_view is not None and len(x_data) == len(y_data):
            finite_mask: np.ndarray = np.isfinite(x_data) & np.isfinite(y_data)
            valid_x: np.ndarray = x_data[finite_mask]
            valid_y: np.ndarray = y_data[finite_mask]

            # Parent Qt ownership here so Python wrapper collection cannot destroy a live renderer object.
            series: QLineSeries | QScatterSeries = series_type(self)
            series.setName(name)

            if isinstance(series, QScatterSeries) and self._circle_marker_delegate is not None:
                series.setPointDelegate(self._circle_marker_delegate)
            else:
                pass

            if color is not None:
                series.setColor(QtGui.QColor(color))
            else:
                pass

            if len(valid_x) > 0:
                series.appendNp(valid_x, valid_y)
            else:
                pass
            self.graph_view.addSeries(series)
            self._series.append(series)
            if name != "":
                self._add_legend_entry(name=name, color=series.color())
            else:
                pass
            if len(valid_x) > 0:
                self._include_points(x_data=valid_x, y_data=valid_y)
            else:
                pass
        else:
            pass

    def _include_points(self, x_data: np.ndarray, y_data: np.ndarray) -> None:
        """Expand the shared axes to include a new data series.

        :param x_data: Finite horizontal values.
        :param y_data: Finite vertical values.
        :return: None.
        """
        if self._has_points:
            self._x_min = min(self._x_min, float(np.min(x_data)))
            self._x_max = max(self._x_max, float(np.max(x_data)))
            self._y_min = min(self._y_min, float(np.min(y_data)))
            self._y_max = max(self._y_max, float(np.max(y_data)))
        else:
            self._x_min = float(np.min(x_data))
            self._x_max = float(np.max(x_data))
            self._y_min = float(np.min(y_data))
            self._y_max = float(np.max(y_data))
            self._has_points = True

        self._set_axis_ranges()

    def _add_legend_entry(self, name: str, color: QtGui.QColor) -> None:
        """Add a Python-configured legend label for one data series.

        :param name: Series label.
        :param color: Series color.
        :return: None.
        """
        legend_label: QtWidgets.QLabel = QtWidgets.QLabel(f"● {name}", self.legend_container)
        legend_label.setStyleSheet(f"color: {color.name()};")
        self.legend_layout.addWidget(legend_label)
        self._legend_items.append(legend_label)
        self.legend_container.show()

    def _set_axis_ranges(self) -> None:
        """Set padded, non-degenerate value ranges for both axes.

        :return: None.
        """
        x_padding: float = max((self._x_max - self._x_min) * 0.05, 0.5)
        y_padding: float = max((self._y_max - self._y_min) * 0.05, 0.5)
        if isinstance(self.axis_x, QValueAxis):
            self.axis_x.setRange(self._x_min - x_padding, self._x_max + x_padding)
        elif isinstance(self.axis_x, QDateTimeAxis):
            date_padding: float = max((self._x_max - self._x_min) * 0.05, 86_400_000.0)
            x_minimum: QtCore.QDateTime = QtCore.QDateTime.fromMSecsSinceEpoch(
                int(self._x_min - date_padding)
            )
            x_maximum: QtCore.QDateTime = QtCore.QDateTime.fromMSecsSinceEpoch(
                int(self._x_max + date_padding)
            )
            self.axis_x.setRange(x_minimum, x_maximum)
        else:
            pass
        self.axis_y.setRange(self._y_min - y_padding, self._y_max + y_padding)

    def redraw(self) -> None:
        """Request a frame from the hosted Qt Graphs view.

        :return: None.
        """
        if not self._disposed:
            self.quick_widget.update()
        else:
            pass

    def eventFilter(self, watched: QtCore.QObject, event: QtCore.QEvent) -> bool:
        """Translate QWidget pointer input into direct Qt Graphs axis navigation.

        :param watched: QObject receiving the original event.
        :param event: Qt input or lifecycle event.
        :return: True when chart navigation consumed the event.
        """
        if watched is self.quick_widget and not self._disposed:
            if event.type() == QtCore.QEvent.Type.Wheel and isinstance(event, QtGui.QWheelEvent):
                self._zoom_from_wheel(delta_y=event.angleDelta().y())
                event.accept()
                return True
            elif event.type() == QtCore.QEvent.Type.MouseButtonPress and isinstance(event, QtGui.QMouseEvent):
                if event.button() == QtCore.Qt.MouseButton.LeftButton:
                    self._pan_position = event.position()
                    event.accept()
                    return True
                else:
                    pass
            elif event.type() == QtCore.QEvent.Type.MouseMove and isinstance(event, QtGui.QMouseEvent):
                if self._pan_position is not None:
                    self._pan_from_drag(current_position=event.position())
                    event.accept()
                    return True
                else:
                    pass
            elif event.type() == QtCore.QEvent.Type.MouseButtonRelease and isinstance(event, QtGui.QMouseEvent):
                if event.button() == QtCore.Qt.MouseButton.LeftButton and self._pan_position is not None:
                    self._pan_position = None
                    event.accept()
                    return True
                else:
                    pass
            elif event.type() == QtCore.QEvent.Type.MouseButtonDblClick and isinstance(event, QtGui.QMouseEvent):
                if event.button() == QtCore.Qt.MouseButton.LeftButton:
                    self._reset_viewport()
                    event.accept()
                    return True
                else:
                    pass
            else:
                pass
        else:
            pass
        return QtWidgets.QWidget.eventFilter(self, watched, event)

    def _zoom_from_wheel(self, delta_y: int) -> None:
        """Scale compatible graph axes from a physical mouse-wheel delta.

        :param delta_y: Vertical wheel delta from the QWidget input event.
        :return: None.
        """
        if delta_y > 0:
            zoom_multiplier: float = 1.25
        elif delta_y < 0:
            zoom_multiplier = 0.8
        else:
            return

        if isinstance(self.axis_x, QValueAxis) or isinstance(self.axis_x, QDateTimeAxis):
            self._zoom_axis(axis=self.axis_x, multiplier=zoom_multiplier)
        else:
            pass
        if isinstance(self.axis_y, QValueAxis) or isinstance(self.axis_y, QDateTimeAxis):
            self._zoom_axis(axis=self.axis_y, multiplier=zoom_multiplier)
        else:
            pass
        self.redraw()

    def _zoom_axis(self, axis: QValueAxis | QDateTimeAxis, multiplier: float) -> None:
        """Apply one bounded zoom multiplier to a navigable Qt Graphs axis.

        :param axis: Value or datetime axis to update.
        :param multiplier: Relative zoom adjustment.
        :return: None.
        """
        zoom_value: float = min(max(axis.zoom() * multiplier, 1.0), 20.0)
        axis.setZoom(zoom_value)

    def _pan_from_drag(self, current_position: QtCore.QPointF) -> None:
        """Move compatible axes by the distance travelled since the last drag event.

        :param current_position: Current pointer position inside the graph widget.
        :return: None.
        """
        if self._pan_position is not None:
            previous_position: QtCore.QPointF = self._pan_position
            delta: QtCore.QPointF = current_position - previous_position
            self._pan_position = current_position
        else:
            return

        if self.quick_widget.width() > 0:
            if isinstance(self.axis_x, QValueAxis) or isinstance(self.axis_x, QDateTimeAxis):
                x_span: float = self._axis_span(axis=self.axis_x)
                self.axis_x.setPan(self.axis_x.pan() - delta.x() * x_span / self.quick_widget.width())
            else:
                pass
        else:
            pass
        if self.quick_widget.height() > 0:
            if isinstance(self.axis_y, QValueAxis) or isinstance(self.axis_y, QDateTimeAxis):
                y_span: float = self._axis_span(axis=self.axis_y)
                self.axis_y.setPan(self.axis_y.pan() + delta.y() * y_span / self.quick_widget.height())
            else:
                pass
        else:
            pass
        self.redraw()

    def _axis_span(self, axis: QValueAxis | QDateTimeAxis) -> float:
        """Return the unzoomed numerical span for a Qt Graphs axis.

        :param axis: Value or datetime axis whose viewport is panned.
        :return: Axis span in its pan coordinate unit.
        """
        if isinstance(axis, QValueAxis):
            return axis.max() - axis.min()
        else:
            return float(axis.max().toMSecsSinceEpoch() - axis.min().toMSecsSinceEpoch())

    def _reset_viewport(self) -> None:
        """Restore unzoomed, unpanned axes after a double-click.

        :return: None.
        """
        if isinstance(self.axis_x, QValueAxis) or isinstance(self.axis_x, QDateTimeAxis):
            self.axis_x.setZoom(1.0)
            self.axis_x.setPan(0.0)
        else:
            pass
        if isinstance(self.axis_y, QValueAxis) or isinstance(self.axis_y, QDateTimeAxis):
            self.axis_y.setZoom(1.0)
            self.axis_y.setPan(0.0)
        else:
            pass
        self.redraw()

    def dispose(self) -> None:
        """Release series before the parent dialog closes.

        :return: None.
        """
        if not self._disposed:
            self._disposed = True
            self.quick_widget.removeEventFilter(self)
            self._pan_position = None
            self.clear()
        else:
            pass

    def event(self, event: QtCore.QEvent) -> bool:
        """Release chart series when Qt schedules this widget for deletion.

        :param event: Qt event.
        :return: True when the event was handled.
        """
        if event.type() == QtCore.QEvent.Type.DeferredDelete:
            self.dispose()
        else:
            pass
        return QtWidgets.QWidget.event(self, event)
