# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""Small QWidget chart renderer with explicit Python ownership of chart data."""

from collections.abc import Sequence
from enum import Enum, auto

import numpy as np
from PySide6 import QtCore, QtGui, QtWidgets


class ChartSeriesType(Enum):
    """Rendering primitive stored by :class:`ChartSeries`."""

    LINE = auto()
    SCATTER = auto()
    HORIZONTAL_BAR = auto()
    CUMULATIVE_AREA = auto()
    POLAR = auto()
    POLAR_SCATTER = auto()
    HISTOGRAM = auto()


class ChartContentType(Enum):
    """Coordinate system currently drawn by :class:`GraphsWidget`."""

    XY = auto()
    HORIZONTAL_BAR = auto()
    CUMULATIVE_AREA = auto()
    POLAR = auto()
    HISTOGRAM = auto()


class PolarAngleUnit(Enum):
    """Unit used by the angle buffers of a polar series."""

    RADIANS = auto()
    DEGREES = auto()


class ChartAxis:
    """Value axis state held in Python and consumed by the painter only."""

    __slots__ = ("_title", "_minimum", "_maximum", "_zoom", "_pan")

    def __init__(self) -> None:
        """Create a one-unit visible range without native QObject ownership.

        :return: None.
        """
        self._title: str = ""
        self._minimum: float = 0.0
        self._maximum: float = 1.0
        self._zoom: float = 1.0
        self._pan: float = 0.0

    def set_title(self, title: str) -> None:
        """Set the axis caption rendered around the plot area.

        :param title: Axis caption.
        :return: None.
        """
        self._title = title

    def get_title(self) -> str:
        """Return the current axis caption.

        :return: Axis caption.
        """
        return self._title

    def set_range(self, minimum: float, maximum: float) -> None:
        """Set a finite non-degenerate data range.

        :param minimum: Lowest data value.
        :param maximum: Highest data value.
        :return: None.
        """
        if np.isfinite(minimum) and np.isfinite(maximum) and maximum > minimum:
            self._minimum = minimum
            self._maximum = maximum
        else:
            self._minimum = 0.0
            self._maximum = 1.0

    def get_range(self) -> tuple[float, float]:
        """Return the complete unzoomed data range.

        :return: Minimum and maximum data values.
        """
        return self._minimum, self._maximum

    def set_zoom(self, zoom: float) -> None:
        """Set a bounded viewport magnification.

        :param zoom: Requested viewport magnification.
        :return: None.
        """
        if np.isfinite(zoom):
            self._zoom = min(max(zoom, 1.0), 20.0)
        else:
            self._zoom = 1.0

    def get_zoom(self) -> float:
        """Return the viewport magnification.

        :return: Viewport magnification.
        """
        return self._zoom

    def set_pan(self, pan: float) -> None:
        """Set the data-unit offset from the complete range centre.

        :param pan: Data-unit viewport offset.
        :return: None.
        """
        if np.isfinite(pan):
            self._pan = pan
        else:
            self._pan = 0.0

    def get_pan(self) -> float:
        """Return the data-unit viewport offset.

        :return: Data-unit viewport offset.
        """
        return self._pan

    def reset_viewport(self) -> None:
        """Show the complete range without a pan offset.

        :return: None.
        """
        self._zoom = 1.0
        self._pan = 0.0

    def get_visual_range(self) -> tuple[float, float]:
        """Return the range currently visible after zoom and pan.

        :return: Minimum and maximum displayed values.
        """
        span: float = (self._maximum - self._minimum) / self._zoom
        centre: float = (self._minimum + self._maximum) * 0.5 + self._pan
        return centre - span * 0.5, centre + span * 0.5


class ChartSeries:
    """One Python-owned chart series with private NumPy point buffers."""

    __slots__ = ("_series_type", "_name", "_x_data", "_y_data", "_color", "_point_tooltips")

    def __init__(self,
                 series_type: ChartSeriesType,
                 name: str,
                 x_data: np.ndarray,
                 y_data: np.ndarray,
                 color: QtGui.QColor,
                 point_tooltips: Sequence[str] | None = None) -> None:
        """Create a series whose buffers are owned by this Python object.

        :param series_type: Rendering primitive for the point buffers.
        :param name: Legend label.
        :param x_data: Already validated horizontal point values.
        :param y_data: Already validated vertical point values.
        :param color: Visible series colour.
        :param point_tooltips: Optional text paired with scatter points.
        :return: None.
        """
        self._series_type: ChartSeriesType = series_type
        self._name: str = name
        self._x_data: np.ndarray = np.zeros(0, dtype=float)
        self._y_data: np.ndarray = np.zeros(0, dtype=float)
        self._color: QtGui.QColor = QtGui.QColor(color)
        self._point_tooltips: list[str] = list()
        self.replace_data(x_data=x_data, y_data=y_data, color=color)
        self.set_point_tooltips(point_tooltips=point_tooltips)

    def get_series_type(self) -> ChartSeriesType:
        """Return the primitive used to paint this series.

        :return: Series primitive.
        """
        return self._series_type

    def get_name(self) -> str:
        """Return the legend label.

        :return: Legend label.
        """
        return self._name

    def get_x_data(self) -> np.ndarray:
        """Return the private horizontal buffer for GUI-thread painting.

        :return: Horizontal values owned by this series.
        """
        return self._x_data

    def get_y_data(self) -> np.ndarray:
        """Return the private vertical buffer for GUI-thread painting.

        :return: Vertical values owned by this series.
        """
        return self._y_data

    def get_color(self) -> QtGui.QColor:
        """Return the value-type colour used while painting.

        :return: Series colour.
        """
        return QtGui.QColor(self._color)

    def set_point_tooltips(self, point_tooltips: Sequence[str] | None) -> bool:
        """Set optional text paired with every retained scatter point.

        :param point_tooltips: Text in the same order as the private point buffer.
        :return: Whether the text count matched the point count.
        """
        if point_tooltips is None:
            self._point_tooltips.clear()
            return True
        elif len(point_tooltips) == len(self._x_data):
            tooltip_index: int
            tooltip_values: list[str] = list()
            for tooltip_index in range(len(point_tooltips)):
                tooltip_values.append(str(point_tooltips[tooltip_index]))
            self._point_tooltips = tooltip_values
            return True
        else:
            self._point_tooltips.clear()
            return False

    def get_point_tooltip(self, point_index: int) -> str | None:
        """Return optional text for one point in the private buffer.

        :param point_index: Index in the private point buffer.
        :return: Tooltip text, or ``None`` when this series has no text there.
        """
        if 0 <= point_index < len(self._point_tooltips):
            return self._point_tooltips[point_index]
        else:
            return None

    def has_point_tooltips(self) -> bool:
        """Return whether this series has text for all retained points.

        :return: Whether point tooltip text is available.
        """
        return len(self._point_tooltips) == len(self._x_data) and len(self._point_tooltips) > 0

    def replace_data(self, x_data: np.ndarray, y_data: np.ndarray, color: QtGui.QColor) -> None:
        """Replace both private point buffers after caller-side validation.

        :param x_data: Finite horizontal values.
        :param y_data: Finite vertical values.
        :param color: New visible series colour.
        :return: None.
        """
        # Copy the arrays so producers cannot mutate a buffer while paintEvent reads it.
        self._x_data = np.ascontiguousarray(x_data, dtype=float).copy()
        self._y_data = np.ascontiguousarray(y_data, dtype=float).copy()
        self._color = QtGui.QColor(color)
        if len(self._point_tooltips) != len(self._x_data):
            self._point_tooltips.clear()
        else:
            pass

    def release_data(self) -> None:
        """Drop NumPy references before the owning QWidget is destroyed.

        :return: None.
        """
        self._x_data = np.zeros(0, dtype=float)
        self._y_data = np.zeros(0, dtype=float)
        self._point_tooltips.clear()


def prepare_chart_points(x_values: Sequence[float] | np.ndarray,
                         y_values: Sequence[float] | np.ndarray) -> tuple[np.ndarray, np.ndarray] | None:
    """Validate paired numeric values and return isolated finite buffers.

    :param x_values: Candidate horizontal values.
    :param y_values: Candidate vertical values.
    :return: Finite copied point buffers, or ``None`` for incompatible inputs.
    """
    x_data: np.ndarray = np.asarray(x_values, dtype=float)
    y_data: np.ndarray = np.asarray(y_values, dtype=float)
    if len(x_data) == len(y_data):
        finite_mask: np.ndarray = np.isfinite(x_data) & np.isfinite(y_data)
        return np.ascontiguousarray(x_data[finite_mask], dtype=float), np.ascontiguousarray(y_data[finite_mask], dtype=float)
    else:
        return None


def prepare_chart_point_tooltips(x_values: np.ndarray,
                                 y_values: Sequence[float] | np.ndarray,
                                 point_tooltips: Sequence[str] | None) -> list[str] | None:
    """Filter optional point text with the finite values retained for drawing.

    :param x_values: Candidate numeric horizontal values.
    :param y_values: Candidate vertical values.
    :param point_tooltips: Optional text in source-point order.
    :return: Text in retained-point order, or ``None`` without valid metadata.
    """
    if point_tooltips is not None:
        y_data: np.ndarray = np.asarray(y_values, dtype=float)
        if len(point_tooltips) == len(x_values) and len(x_values) == len(y_data):
            finite_mask: np.ndarray = np.isfinite(x_values) & np.isfinite(y_data)
            retained_tooltips: list[str] = list()
            tooltip_index: int
            for tooltip_index in range(len(point_tooltips)):
                if finite_mask[tooltip_index]:
                    retained_tooltips.append(str(point_tooltips[tooltip_index]))
                else:
                    pass
            return retained_tooltips
        else:
            return None
    else:
        return None


def prepare_chart_x_values(x_values: Sequence[float] | np.ndarray) -> tuple[np.ndarray, bool]:
    """Convert numeric or NumPy datetime horizontal coordinates to floats.

    :param x_values: Candidate horizontal values.
    :return: Milliseconds or numeric values, plus whether date labels are needed.
    """
    raw_x_values: np.ndarray = np.asarray(x_values)
    if np.issubdtype(raw_x_values.dtype, np.datetime64):
        x_data: np.ndarray = raw_x_values.astype("datetime64[ms]").astype(np.int64).astype(float)
        x_data[np.isnat(raw_x_values)] = np.nan
        return x_data, True
    else:
        return np.asarray(x_values, dtype=float), False


def format_chart_value(value: float, is_datetime: bool) -> str:
    """Format one axis tick without storing any Qt date-time object.

    :param value: Numeric tick value.
    :param is_datetime: Whether the value represents epoch milliseconds.
    :return: Visible tick text.
    """
    if is_datetime:
        date_value: QtCore.QDateTime = QtCore.QDateTime.fromMSecsSinceEpoch(int(value))
        return date_value.toString("yyyy-MM-dd")
    elif abs(value) >= 10000.0 or (abs(value) > 0.0 and abs(value) < 0.01):
        return f"{value:.2e}"
    else:
        return f"{value:.4g}"


class GraphsWidget(QtWidgets.QWidget):
    """Paint native line, scatter, area, bar, polar, and histogram charts."""

    __slots__ = (
        "axis_x",
        "axis_y",
        "_series",
        "_content_type",
        "_bar_labels",
        "_title",
        "_has_points",
        "_x_min",
        "_x_max",
        "_y_min",
        "_y_max",
        "_x_is_datetime",
        "_pan_position",
        "_disposed",
        "_background_color",
        "_plot_color",
        "_label_color",
        "_grid_color",
    )

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        """Create a single QWidget chart with Python-owned state only.

        :param parent: Parent Qt widget that owns this chart widget.
        :return: None.
        """
        QtWidgets.QWidget.__init__(self, parent)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding)
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)
        self.setToolTip(self.tr("Mouse wheel: zoom\nLeft drag: pan\nDouble-click: reset view"))

        # The axes and series are plain Python values, so QWidget owns every native object involved.
        self.axis_x: ChartAxis = ChartAxis()
        self.axis_y: ChartAxis = ChartAxis()
        self._series: list[ChartSeries] = list()
        self._content_type: ChartContentType = ChartContentType.XY
        self._bar_labels: list[str] = list()
        self._title: str = ""
        self._has_points: bool = False
        self._x_min: float = 0.0
        self._x_max: float = 1.0
        self._y_min: float = 0.0
        self._y_max: float = 1.0
        self._x_is_datetime: bool = False
        self._pan_position: QtCore.QPointF | None = None
        self._disposed: bool = False
        self._background_color: QtGui.QColor = QtGui.QColor("#ffffff")
        self._plot_color: QtGui.QColor = QtGui.QColor("#f7fbff")
        self._label_color: QtGui.QColor = QtGui.QColor("#17324a")
        self._grid_color: QtGui.QColor = QtGui.QColor("#cbd5e1")
        self.apply_theme(dark=self.palette().color(QtGui.QPalette.ColorRole.Window).lightness() < 128)
        self._set_axis_ranges()

    def sizeHint(self) -> QtCore.QSize:
        """Return a useful initial size while allowing layout expansion.

        :return: Preferred chart size.
        """
        return QtCore.QSize(560, 360)

    def minimumSizeHint(self) -> QtCore.QSize:
        """Return a small usable chart size for narrow editor panels.

        :return: Minimum preferred chart size.
        """
        return QtCore.QSize(240, 180)

    def apply_theme(self, dark: bool) -> None:
        """Set paint colours from the surrounding Qt Widgets palette choice.

        :param dark: Whether the surrounding application uses a dark palette.
        :return: None.
        """
        if dark:
            self._background_color = QtGui.QColor("#171c24")
            self._plot_color = QtGui.QColor("#202834")
            self._label_color = QtGui.QColor("#e7edf5")
            self._grid_color = QtGui.QColor("#445164")
        else:
            self._background_color = QtGui.QColor("#ffffff")
            self._plot_color = QtGui.QColor("#f7fbff")
            self._label_color = QtGui.QColor("#17324a")
            self._grid_color = QtGui.QColor("#cbd5e1")
        if self._can_mutate():
            self.update()
        else:
            pass

    def setTitle(self, title: str) -> None:
        """Set the visible plot title.

        :param title: Plot title.
        :return: None.
        """
        if self._can_mutate():
            self._title = title
            self.update()
        else:
            pass

    def set_axis_titles(self, x_title: str, y_title: str) -> None:
        """Set the labels shown on both axes.

        :param x_title: Horizontal axis title.
        :param y_title: Vertical axis title.
        :return: None.
        """
        if self._can_mutate():
            self.axis_x.set_title(x_title)
            self.axis_y.set_title(y_title)
            self.update()
        else:
            pass

    def reset_viewport(self) -> None:
        """Show every stored data point and clear the current pan offset.

        :return: None.
        """
        if self._can_mutate():
            self.axis_x.reset_viewport()
            self.axis_y.reset_viewport()
            self.update()
        else:
            pass

    def set_cumulative_area_series(
            self,
            x_values: Sequence[float] | np.ndarray,
            series_names: Sequence[str],
            series_values: Sequence[Sequence[float] | np.ndarray],
            colors: Sequence[str | None] | None = None) -> bool:
        """Replace the chart with stacked cumulative areas sharing one X axis.

        :param x_values: Numeric or NumPy datetime coordinates shared by every area.
        :param series_names: Visible name for each cumulative band.
        :param series_values: One value buffer for each name in display order.
        :param colors: Optional Qt colour for each band.
        :return: Whether every input buffer had a compatible finite shape.
        """
        if self._can_mutate() and len(series_names) == len(series_values) and len(series_names) > 0:
            x_data: np.ndarray
            is_datetime: bool
            x_data, is_datetime = prepare_chart_x_values(x_values=x_values)
            valid_mask: np.ndarray = np.isfinite(x_data)
            values_data: list[np.ndarray] = list()
            series_index: int
            for series_index in range(len(series_values)):
                value_data: np.ndarray = np.asarray(series_values[series_index], dtype=float)
                if len(value_data) == len(x_data):
                    values_data.append(value_data)
                    valid_mask &= np.isfinite(value_data)
                else:
                    return False

            if colors is None:
                color_values: list[str | None] = list()
                for series_index in range(len(series_names)):
                    color_values.append(None)
            elif len(colors) == len(series_names):
                color_values = list(colors)
            else:
                return False

            if np.any(valid_mask):
                retained_x_data: np.ndarray = np.ascontiguousarray(x_data[valid_mask], dtype=float)
                new_series: list[ChartSeries] = list()
                cumulative_values: np.ndarray = np.zeros(len(retained_x_data), dtype=float)
                minimum_value: float = 0.0
                maximum_value: float = 0.0
                for series_index in range(len(values_data)):
                    retained_data: np.ndarray = np.ascontiguousarray(
                        values_data[series_index][valid_mask],
                        dtype=float,
                    )
                    cumulative_values += retained_data
                    minimum_value = min(minimum_value, float(np.min(cumulative_values)))
                    maximum_value = max(maximum_value, float(np.max(cumulative_values)))
                    new_series.append(
                        ChartSeries(
                            series_type=ChartSeriesType.CUMULATIVE_AREA,
                            name=str(series_names[series_index]),
                            x_data=retained_x_data,
                            y_data=retained_data,
                            color=self._make_series_color(
                                color_name=color_values[series_index],
                                series_index=series_index,
                            ),
                        )
                    )

                # Release the old Python buffers before swapping the chart mode.
                self.clear()
                self._content_type = ChartContentType.CUMULATIVE_AREA
                self._series = new_series
                self._has_points = True
                self._x_min = float(np.min(retained_x_data))
                self._x_max = float(np.max(retained_x_data))
                self._y_min = minimum_value
                self._y_max = maximum_value
                self._x_is_datetime = is_datetime
                self._set_axis_ranges()
                self.update()
                return True
            else:
                return False
        else:
            return False

    def set_polar_series(
            self,
            series_names: Sequence[str],
            angle_values: Sequence[Sequence[float] | np.ndarray],
            radius_values: Sequence[Sequence[float] | np.ndarray],
            colors: Sequence[str | None] | None = None,
            angle_unit: PolarAngleUnit = PolarAngleUnit.RADIANS,
            connect_points: bool = True) -> bool:
        """Replace the chart with line series in polar coordinates.

        :param series_names: Visible name for each polar line.
        :param angle_values: Angle buffer for each series.
        :param radius_values: Non-negative radial buffer for each series.
        :param colors: Optional Qt colour for each polar line.
        :param angle_unit: Unit used by every angle buffer.
        :param connect_points: Whether consecutive samples are joined by line segments.
        :return: Whether every input series had compatible finite coordinates.
        """
        series_count: int = len(series_names)
        if (self._can_mutate() and series_count > 0 and len(angle_values) == series_count
                and len(radius_values) == series_count):
            if colors is None:
                color_values: list[str | None] = list()
                series_index: int
                for series_index in range(series_count):
                    color_values.append(None)
            elif len(colors) == series_count:
                color_values = list(colors)
            else:
                return False

            new_series: list[ChartSeries] = list()
            maximum_radius: float = 0.0
            series_index: int
            for series_index in range(series_count):
                angles: np.ndarray = np.asarray(angle_values[series_index], dtype=float)
                radii: np.ndarray = np.asarray(radius_values[series_index], dtype=float)
                if len(angles) == len(radii):
                    finite_mask: np.ndarray = np.isfinite(angles) & np.isfinite(radii) & (radii >= 0.0)
                    if np.any(finite_mask):
                        retained_angles: np.ndarray = np.ascontiguousarray(angles[finite_mask], dtype=float)
                        retained_radii: np.ndarray = np.ascontiguousarray(radii[finite_mask], dtype=float)
                        if angle_unit == PolarAngleUnit.DEGREES:
                            retained_angles = np.deg2rad(retained_angles)
                        elif angle_unit == PolarAngleUnit.RADIANS:
                            pass
                        else:
                            return False
                        maximum_radius = max(maximum_radius, float(np.max(retained_radii)))
                        if connect_points:
                            series_type: ChartSeriesType = ChartSeriesType.POLAR
                        else:
                            series_type = ChartSeriesType.POLAR_SCATTER
                        new_series.append(
                            ChartSeries(
                                series_type=series_type,
                                name=str(series_names[series_index]),
                                x_data=retained_angles,
                                y_data=retained_radii,
                                color=self._make_series_color(
                                    color_name=color_values[series_index],
                                    series_index=series_index,
                                ),
                            )
                        )
                    else:
                        return False
                else:
                    return False

            self.clear()
            self._content_type = ChartContentType.POLAR
            self._series = new_series
            self._has_points = True
            self._x_min = 0.0
            self._x_max = 2.0 * np.pi
            self._y_min = 0.0
            self._y_max = max(maximum_radius, 1.0)
            self._x_is_datetime = False
            self.axis_x.set_range(self._x_min, self._x_max)
            self.axis_y.set_range(0.0, self._y_max * 1.05)
            self.axis_x.reset_viewport()
            self.axis_y.reset_viewport()
            self.update()
            return True
        else:
            return False

    def clear(self, force: bool = False) -> None:
        """Release all chart data and restore a neutral numeric viewport.

        :param force: Accepted for compatibility with former chart callers.
        :return: None.
        """
        _ = force
        if self._is_owner_thread():
            series: ChartSeries
            for series in self._series:
                series.release_data()
            self._series.clear()
            self._content_type = ChartContentType.XY
            self._bar_labels.clear()
            self._has_points = False
            self._x_min = 0.0
            self._x_max = 1.0
            self._y_min = 0.0
            self._y_max = 1.0
            self._x_is_datetime = False
            self.axis_x.reset_viewport()
            self.axis_y.reset_viewport()
            self._set_axis_ranges()
            if not self._disposed:
                self.update()
            else:
                pass
        else:
            pass

    def replace_xy_series_data(
            self,
            series_data: Sequence[tuple[np.ndarray, np.ndarray, str | None]]) -> bool:
        """Replace stable line or scatter buffers without recreating series objects.

        :param series_data: New X values, Y values, and optional colours in series order.
        :return: Whether every existing XY series was updated.
        """
        if self._can_mutate() and self._content_type == ChartContentType.XY and len(series_data) == len(self._series):
            prepared_data: list[tuple[np.ndarray, np.ndarray, QtGui.QColor]] = list()
            series_index: int
            series_values: tuple[np.ndarray, np.ndarray, str | None]
            for series_index, series_values in enumerate(series_data):
                series: ChartSeries = self._series[series_index]
                points: tuple[np.ndarray, np.ndarray] | None = prepare_chart_points(
                    x_values=series_values[0],
                    y_values=series_values[1],
                )
                if points is not None and series.get_series_type() in (ChartSeriesType.LINE, ChartSeriesType.SCATTER):
                    color: QtGui.QColor = self._make_series_color(
                        color_name=series_values[2],
                        series_index=series_index,
                    )
                    prepared_data.append((points[0], points[1], color))
                else:
                    return False

            # Validate every replacement first, then make the state change as one GUI-thread operation.
            self._reset_data_bounds()
            for series_index, series_entry in enumerate(prepared_data):
                target_series: ChartSeries = self._series[series_index]
                x_data: np.ndarray = series_entry[0]
                y_data: np.ndarray = series_entry[1]
                target_series.replace_data(x_data=x_data, y_data=y_data, color=series_entry[2])
                if len(x_data) > 0:
                    self._include_points(x_data=x_data, y_data=y_data)
                else:
                    pass
            self._set_axis_ranges()
            self.update()
            return True
        else:
            return False

    def add_line_series(self,
                        name: str,
                        x_values: Sequence[float] | np.ndarray,
                        y_values: Sequence[float] | np.ndarray,
                        color: str | None = None) -> None:
        """Add one line series from paired finite numeric values.

        :param name: Series name used by the legend.
        :param x_values: Horizontal data values.
        :param y_values: Vertical data values.
        :param color: Optional line colour in Qt colour syntax.
        :return: None.
        """
        x_data: np.ndarray
        is_datetime: bool
        x_data, is_datetime = prepare_chart_x_values(x_values=x_values)
        self._add_xy_series(
            series_type=ChartSeriesType.LINE,
            name=name,
            x_data=x_data,
            y_values=y_values,
            color=color,
            is_datetime=is_datetime,
            point_tooltips=None,
        )

    def add_scatter_series(self,
                           name: str,
                           x_values: Sequence[float] | np.ndarray,
                           y_values: Sequence[float] | np.ndarray,
                           color: str | None = None,
                           point_tooltips: Sequence[str] | None = None) -> None:
        """Add one circle-scatter series from paired finite numeric values.

        :param name: Series name used by the legend.
        :param x_values: Horizontal data values.
        :param y_values: Vertical data values.
        :param color: Optional circle colour in Qt colour syntax.
        :param point_tooltips: Optional text displayed while hovering each circle.
        :return: None.
        """
        x_data: np.ndarray = np.asarray(x_values, dtype=float)
        self._add_xy_series(
            series_type=ChartSeriesType.SCATTER,
            name=name,
            x_data=x_data,
            y_values=y_values,
            color=color,
            is_datetime=False,
            point_tooltips=point_tooltips,
        )

    def set_series_point_tooltips(self, series_index: int, point_tooltips: Sequence[str] | None) -> bool:
        """Set optional tooltip text for an existing scatter series.

        :param series_index: Position of the scatter series in chart display order.
        :param point_tooltips: Text in retained-point order, or ``None`` to clear it.
        :return: Whether the series and text count were valid.
        """
        if self._can_mutate() and 0 <= series_index < len(self._series):
            series: ChartSeries = self._series[series_index]
            if series.get_series_type() == ChartSeriesType.SCATTER:
                updated: bool = series.set_point_tooltips(point_tooltips=point_tooltips)
                self.update()
                return updated
            else:
                return False
        else:
            return False

    def get_point_tooltip_at(self, position: QtCore.QPointF) -> str | None:
        """Return tooltip text for the circular point below a widget position.

        :param position: Pointer position in this widget's coordinates.
        :return: Tooltip text, or ``None`` when no labelled point is nearby.
        """
        if self._content_type == ChartContentType.XY:
            plot_rect: QtCore.QRectF = self._get_plot_rect()
            if plot_rect.contains(position):
                nearest_tooltip: str | None = None
                nearest_distance_squared: float = 49.0
                series: ChartSeries
                for series in self._series:
                    if series.get_series_type() == ChartSeriesType.SCATTER and series.has_point_tooltips():
                        x_data: np.ndarray = series.get_x_data()
                        y_data: np.ndarray = series.get_y_data()
                        point_index: int
                        for point_index in range(len(x_data)):
                            mapped_point: QtCore.QPointF = self._map_xy_point(
                                x_value=float(x_data[point_index]),
                                y_value=float(y_data[point_index]),
                                plot_rect=plot_rect,
                            )
                            delta_x: float = mapped_point.x() - position.x()
                            delta_y: float = mapped_point.y() - position.y()
                            distance_squared: float = delta_x * delta_x + delta_y * delta_y
                            if distance_squared <= nearest_distance_squared:
                                nearest_tooltip = series.get_point_tooltip(point_index=point_index)
                                nearest_distance_squared = distance_squared
                            else:
                                pass
                    else:
                        pass
                return nearest_tooltip
            else:
                return None
        else:
            return None

    def add_horizontal_bar_series(self,
                                  labels: Sequence[str],
                                  values: Sequence[float] | np.ndarray,
                                  positive_color: str,
                                  negative_color: str) -> None:
        """Add horizontal positive and negative bars for named categories.

        :param labels: Category labels in display order.
        :param values: Values paired with ``labels``.
        :param positive_color: Bar colour for zero and positive values.
        :param negative_color: Bar colour for negative values.
        :return: None.
        """
        value_data: np.ndarray = np.asarray(values, dtype=float)
        if self._can_mutate() and len(labels) == len(value_data) and len(value_data) > 0:
            finite_mask: np.ndarray = np.isfinite(value_data)
            valid_values: np.ndarray = np.ascontiguousarray(value_data[finite_mask], dtype=float)
            valid_labels: list[str] = list()
            label_index: int
            for label_index in range(len(labels)):
                if finite_mask[label_index]:
                    valid_labels.append(str(labels[label_index]))
                else:
                    pass
            if len(valid_values) > 0:
                self.clear()
                category_positions: np.ndarray = np.arange(len(valid_values), dtype=float)
                positive_values: np.ndarray = np.maximum(valid_values, 0.0)
                negative_values: np.ndarray = np.minimum(valid_values, 0.0)
                self._content_type = ChartContentType.HORIZONTAL_BAR
                self._bar_labels = valid_labels
                positive_series: ChartSeries = ChartSeries(
                    series_type=ChartSeriesType.HORIZONTAL_BAR,
                    name=self.tr("Positive"),
                    x_data=category_positions,
                    y_data=positive_values,
                    color=self._make_series_color(color_name=positive_color, series_index=0),
                )
                negative_series: ChartSeries = ChartSeries(
                    series_type=ChartSeriesType.HORIZONTAL_BAR,
                    name=self.tr("Negative"),
                    x_data=category_positions,
                    y_data=negative_values,
                    color=self._make_series_color(color_name=negative_color, series_index=1),
                )
                self._series.append(positive_series)
                self._series.append(negative_series)
                self._x_min = min(0.0, float(np.min(valid_values)))
                self._x_max = max(0.0, float(np.max(valid_values)))
                self._y_min = -0.5
                self._y_max = float(len(valid_values)) - 0.5
                self._has_points = True
                self.axis_x.reset_viewport()
                self.axis_y.reset_viewport()
                self._set_axis_ranges()
                self.update()
            else:
                pass
        else:
            pass

    def set_histogram(self,
                      values: Sequence[float] | np.ndarray,
                      bin_count: int,
                      name: str = '',
                      color: str | None = None) -> bool:
        """Replace the chart with a finite numeric histogram.

        :param values: Sample values used to calculate bin frequencies.
        :param bin_count: Positive number of equal-width bins.
        :param name: Optional legend label for the histogram bars.
        :param color: Optional Qt colour for the histogram bars.
        :return: Whether the complete histogram was created.
        """
        value_data: np.ndarray = np.asarray(values, dtype=float)
        if self._can_mutate() and bin_count > 0:
            finite_values: np.ndarray = np.ascontiguousarray(value_data[np.isfinite(value_data)], dtype=float)
            if len(finite_values) > 0:
                counts: np.ndarray
                edges: np.ndarray
                counts, edges = np.histogram(finite_values, bins=bin_count)
                self.clear()
                self._content_type = ChartContentType.HISTOGRAM
                self._series.append(
                    ChartSeries(
                        series_type=ChartSeriesType.HISTOGRAM,
                        name=name,
                        x_data=edges,
                        y_data=counts.astype(float),
                        color=self._make_series_color(color_name=color, series_index=0),
                    )
                )
                self._has_points = True
                self._x_min = float(edges[0])
                self._x_max = float(edges[-1])
                self._y_min = 0.0
                self._y_max = max(float(np.max(counts)), 1.0)
                self._x_is_datetime = False
                self.axis_x.reset_viewport()
                self.axis_y.reset_viewport()
                self._set_axis_ranges()
                self.update()
                return True
            else:
                return False
        else:
            return False

    def redraw(self) -> None:
        """Request a QWidget paint pass when this chart is still active.

        :return: None.
        """
        if self._can_mutate():
            self.update()
        else:
            pass

    def dispose(self) -> None:
        """Drop every Python chart buffer before parent QWidget destruction.

        :return: None.
        """
        if not self._disposed and self._is_owner_thread():
            self._disposed = True
            self._pan_position = None
            self.unsetCursor()
            QtWidgets.QToolTip.hideText()
            self.clear()
        else:
            pass

    def wheelEvent(self, event: QtGui.QWheelEvent) -> None:
        """Zoom value axes by a visible step from the mouse wheel.

        :param event: Mouse wheel event delivered by Qt Widgets.
        :return: None.
        """
        if self._can_mutate():
            delta_y: int = event.angleDelta().y()
            if delta_y > 0:
                multiplier: float = 1.25
                if self._content_type in (ChartContentType.XY, ChartContentType.CUMULATIVE_AREA,
                                          ChartContentType.HISTOGRAM):
                    self.axis_x.set_zoom(self.axis_x.get_zoom() * multiplier)
                    self.axis_y.set_zoom(self.axis_y.get_zoom() * multiplier)
                elif self._content_type == ChartContentType.POLAR:
                    self.axis_y.set_zoom(self.axis_y.get_zoom() * multiplier)
                else:
                    self.axis_x.set_zoom(self.axis_x.get_zoom() * multiplier)
                self.update()
                event.accept()
            elif delta_y < 0:
                multiplier = 0.8
                if self._content_type in (ChartContentType.XY, ChartContentType.CUMULATIVE_AREA,
                                          ChartContentType.HISTOGRAM):
                    self.axis_x.set_zoom(self.axis_x.get_zoom() * multiplier)
                    self.axis_y.set_zoom(self.axis_y.get_zoom() * multiplier)
                elif self._content_type == ChartContentType.POLAR:
                    self.axis_y.set_zoom(self.axis_y.get_zoom() * multiplier)
                else:
                    self.axis_x.set_zoom(self.axis_x.get_zoom() * multiplier)
                self.update()
                event.accept()
            else:
                event.ignore()
        else:
            event.ignore()

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        """Start a value-axis pan from a left-button press.

        :param event: Mouse button press delivered by Qt Widgets.
        :return: None.
        """
        if self._can_mutate() and event.button() == QtCore.Qt.MouseButton.LeftButton:
            QtWidgets.QToolTip.hideText()
            self._pan_position = event.position()
            self.setCursor(QtCore.Qt.CursorShape.ClosedHandCursor)
            event.accept()
        else:
            event.ignore()

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:
        """Pan the visible value range while the left-button drag is active.

        :param event: Pointer motion delivered by Qt Widgets.
        :return: None.
        """
        if self._can_mutate() and self._pan_position is not None:
            previous_position: QtCore.QPointF = self._pan_position
            current_position: QtCore.QPointF = event.position()
            delta: QtCore.QPointF = current_position - previous_position
            plot_rect: QtCore.QRectF = self._get_plot_rect()
            if plot_rect.width() > 0.0 and self._content_type != ChartContentType.POLAR:
                x_minimum: float
                x_maximum: float
                # Use the visible span so one drag covers the same screen distance at every zoom.
                x_minimum, x_maximum = self.axis_x.get_visual_range()
                self.axis_x.set_pan(
                    self.axis_x.get_pan() - delta.x() * (x_maximum - x_minimum) / plot_rect.width()
                )
            else:
                pass
            if self._content_type in (ChartContentType.XY, ChartContentType.CUMULATIVE_AREA,
                                      ChartContentType.HISTOGRAM) and plot_rect.height() > 0.0:
                y_minimum: float
                y_maximum: float
                # The visible span gives vertical panning the same zoom-consistent behaviour.
                y_minimum, y_maximum = self.axis_y.get_visual_range()
                self.axis_y.set_pan(
                    self.axis_y.get_pan() + delta.y() * (y_maximum - y_minimum) / plot_rect.height()
                )
            else:
                pass
            self._pan_position = current_position
            self.update()
            event.accept()
        elif self._can_mutate():
            point_tooltip: str | None = self.get_point_tooltip_at(position=event.position())
            if point_tooltip is not None:
                QtWidgets.QToolTip.showText(event.globalPosition().toPoint(), point_tooltip, self)
            else:
                QtWidgets.QToolTip.hideText()
            event.accept()
        else:
            event.ignore()

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:
        """Finish a left-button pan and release its cursor state.

        :param event: Mouse release event delivered by Qt Widgets.
        :return: None.
        """
        if event.button() == QtCore.Qt.MouseButton.LeftButton and self._pan_position is not None:
            self._pan_position = None
            self.unsetCursor()
            event.accept()
        else:
            event.ignore()

    def leaveEvent(self, event: QtCore.QEvent) -> None:
        """Hide a point tooltip after the pointer leaves this chart widget.

        :param event: Qt leave event delivered by Qt Widgets.
        :return: None.
        """
        _ = event
        QtWidgets.QToolTip.hideText()
        QtWidgets.QWidget.leaveEvent(self, event)

    def mouseDoubleClickEvent(self, event: QtGui.QMouseEvent) -> None:
        """Reset zoom and pan from a left-button double-click.

        :param event: Mouse double-click event delivered by Qt Widgets.
        :return: None.
        """
        if self._can_mutate() and event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.reset_viewport()
            event.accept()
        else:
            event.ignore()

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        """Paint the entire chart synchronously from Python-owned buffers.

        :param event: Paint request delivered only on this QWidget's GUI thread.
        :return: None.
        """
        _ = event
        painter: QtGui.QPainter = QtGui.QPainter(self)
        self.paint_to_painter(painter=painter)
        painter.end()

    def paint_to_painter(self, painter: QtGui.QPainter) -> None:
        """Paint the current chart into an already-active Qt paint device.

        :param painter: Active painter targeting this widget's native size.
        :return: None.
        """
        painter.save()
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(self.rect(), self._background_color)
        plot_rect: QtCore.QRectF = self._get_plot_rect()
        self._paint_title_and_legend(painter=painter, plot_rect=plot_rect)
        if plot_rect.width() > 2.0 and plot_rect.height() > 2.0:
            painter.fillRect(plot_rect, self._plot_color)
            if self._content_type == ChartContentType.HORIZONTAL_BAR:
                self._paint_bar_axes(painter=painter, plot_rect=plot_rect)
                painter.save()
                painter.setClipRect(plot_rect)
                self._paint_horizontal_bars(painter=painter, plot_rect=plot_rect)
                painter.restore()
            elif self._content_type == ChartContentType.CUMULATIVE_AREA:
                self._paint_xy_axes(painter=painter, plot_rect=plot_rect)
                painter.save()
                painter.setClipRect(plot_rect)
                self._paint_cumulative_areas(painter=painter, plot_rect=plot_rect)
                painter.restore()
            elif self._content_type == ChartContentType.POLAR:
                self._paint_polar_axes(painter=painter, plot_rect=plot_rect)
                painter.save()
                painter.setClipRect(plot_rect)
                self._paint_polar_series(painter=painter, plot_rect=plot_rect)
                painter.restore()
            elif self._content_type == ChartContentType.HISTOGRAM:
                self._paint_xy_axes(painter=painter, plot_rect=plot_rect)
                painter.save()
                painter.setClipRect(plot_rect)
                self._paint_histogram(painter=painter, plot_rect=plot_rect)
                painter.restore()
            else:
                self._paint_xy_axes(painter=painter, plot_rect=plot_rect)
                painter.save()
                painter.setClipRect(plot_rect)
                self._paint_xy_series(painter=painter, plot_rect=plot_rect)
                painter.restore()
            painter.setPen(QtGui.QPen(self._label_color, 1.0))
            # Restoring the clipped painter also restores the last series brush.
            painter.setBrush(QtGui.QBrush(QtCore.Qt.BrushStyle.NoBrush))
            painter.drawRect(plot_rect)
        else:
            pass
        painter.restore()

    def event(self, event: QtCore.QEvent) -> bool:
        """Release Python buffers before a deferred QWidget deletion completes.

        :param event: Qt lifecycle event.
        :return: Whether Qt handled the event.
        """
        if event.type() == QtCore.QEvent.Type.DeferredDelete:
            self.dispose()
        else:
            pass
        return QtWidgets.QWidget.event(self, event)

    def _can_mutate(self) -> bool:
        """Return whether GUI-thread code may change chart state safely.

        :return: Whether the chart is active on its Qt owner thread.
        """
        return not self._disposed and self._is_owner_thread()

    def _is_owner_thread(self) -> bool:
        """Return whether the caller is running on this QWidget's Qt thread.

        :return: Whether the caller owns this QWidget's thread affinity.
        """
        return QtCore.QThread.currentThread() == self.thread()

    def _reset_data_bounds(self) -> None:
        """Reset accumulated XY limits before replacing every series buffer.

        :return: None.
        """
        self._has_points = False
        self._x_min = 0.0
        self._x_max = 1.0
        self._y_min = 0.0
        self._y_max = 1.0

    def _add_xy_series(self,
                       series_type: ChartSeriesType,
                       name: str,
                       x_data: np.ndarray,
                       y_values: Sequence[float] | np.ndarray,
                       color: str | None,
                       is_datetime: bool,
                       point_tooltips: Sequence[str] | None) -> None:
        """Append one validated XY series and expand the shared data range.

        :param series_type: Line or scatter primitive.
        :param name: Legend label.
        :param x_data: Numeric or converted date horizontal values.
        :param y_values: Candidate vertical values.
        :param color: Optional Qt colour name.
        :param is_datetime: Whether horizontal values represent milliseconds.
        :param point_tooltips: Optional text in source-point order.
        :return: None.
        """
        points: tuple[np.ndarray, np.ndarray] | None = prepare_chart_points(x_values=x_data, y_values=y_values)
        if self._can_mutate() and points is not None and self._content_type == ChartContentType.XY:
            series_index: int = len(self._series)
            series_color: QtGui.QColor = self._make_series_color(color_name=color, series_index=series_index)
            retained_tooltips: list[str] | None = prepare_chart_point_tooltips(
                x_values=x_data,
                y_values=y_values,
                point_tooltips=point_tooltips,
            )
            series: ChartSeries = ChartSeries(
                series_type=series_type,
                name=name,
                x_data=points[0],
                y_data=points[1],
                color=series_color,
                point_tooltips=retained_tooltips,
            )
            self._series.append(series)
            if len(points[0]) > 0:
                self._include_points(x_data=points[0], y_data=points[1])
            else:
                pass
            if is_datetime:
                self._x_is_datetime = True
            else:
                pass
            self._set_axis_ranges()
            self.update()
        else:
            pass

    def _include_points(self, x_data: np.ndarray, y_data: np.ndarray) -> None:
        """Expand shared XY data bounds to include a finite point buffer.

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

    def _set_axis_ranges(self) -> None:
        """Set padded, non-degenerate axis ranges from current chart content.

        :return: None.
        """
        x_padding: float = max((self._x_max - self._x_min) * 0.05, 0.5)
        y_padding: float = max((self._y_max - self._y_min) * 0.05, 0.5)
        if self._content_type == ChartContentType.HORIZONTAL_BAR:
            self.axis_x.set_range(self._x_min - x_padding, self._x_max + x_padding)
            self.axis_y.set_range(self._y_min, self._y_max)
        else:
            self.axis_x.set_range(self._x_min - x_padding, self._x_max + x_padding)
            self.axis_y.set_range(self._y_min - y_padding, self._y_max + y_padding)

    def _make_series_color(self, color_name: str | None, series_index: int) -> QtGui.QColor:
        """Return a valid explicit or deterministic fallback series colour.

        :param color_name: Optional caller-provided Qt colour name.
        :param series_index: Position used to select a fallback colour.
        :return: Valid QColor value.
        """
        if color_name is not None:
            requested_color: QtGui.QColor = QtGui.QColor(color_name)
            if requested_color.isValid():
                return requested_color
            else:
                pass
        else:
            pass
        palette_colors: tuple[str, ...] = (
            "#2563eb",
            "#f97316",
            "#0f766e",
            "#dc2626",
            "#7c3aed",
            "#0891b2",
        )
        return QtGui.QColor(palette_colors[series_index % len(palette_colors)])

    def _get_plot_rect(self) -> QtCore.QRectF:
        """Return the data rectangle after title, legend, and axis margins.

        :return: Rectangle available to the data renderer.
        """
        title_space: float = 24.0 if self._title != "" else 4.0
        legend_space: float = 20.0 if len(self._visible_legend_series()) > 0 else 0.0
        return QtCore.QRectF(self.rect()).adjusted(74.0, title_space + legend_space + 4.0, -20.0, -58.0)

    def _visible_legend_series(self) -> list[ChartSeries]:
        """Return named series to be painted in the legend.

        :return: Named series in display order.
        """
        visible_series: list[ChartSeries] = list()
        series: ChartSeries
        for series in self._series:
            if series.get_name() != "":
                visible_series.append(series)
            else:
                pass
        return visible_series

    def _paint_title_and_legend(self, painter: QtGui.QPainter, plot_rect: QtCore.QRectF) -> None:
        """Paint title and legend above the available plot area.

        :param painter: Active painter for this paint event.
        :param plot_rect: Final data drawing rectangle.
        :return: None.
        """
        painter.setPen(QtGui.QPen(self._label_color))
        if self._title != "":
            title_font: QtGui.QFont = QtGui.QFont(painter.font())
            title_font.setBold(True)
            painter.setFont(title_font)
            painter.drawText(QtCore.QRectF(8.0, 2.0, float(self.width() - 16), 22.0),
                             QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter,
                             self._title)
        else:
            pass

        legend_series: list[ChartSeries] = self._visible_legend_series()
        if len(legend_series) > 0:
            legend_y: float = plot_rect.top() - 20.0
            legend_x: float = plot_rect.left()
            normal_font: QtGui.QFont = QtGui.QFont(painter.font())
            normal_font.setBold(False)
            painter.setFont(normal_font)
            series: ChartSeries
            for series in legend_series:
                marker_color: QtGui.QColor = series.get_color()
                painter.setBrush(QtGui.QBrush(marker_color))
                painter.setPen(QtGui.QPen(marker_color))
                painter.drawEllipse(QtCore.QPointF(legend_x + 5.0, legend_y + 9.0), 4.0, 4.0)
                painter.setPen(QtGui.QPen(self._label_color))
                legend_text: str = series.get_name()
                painter.drawText(QtCore.QPointF(legend_x + 13.0, legend_y + 14.0), legend_text)
                text_width: int = painter.fontMetrics().horizontalAdvance(legend_text)
                legend_x += float(text_width + 34)
                if legend_x > float(self.width() - 120):
                    break
                else:
                    pass
        else:
            pass

    def _paint_xy_axes(self, painter: QtGui.QPainter, plot_rect: QtCore.QRectF) -> None:
        """Paint numeric grids, ticks, and captions for an XY chart.

        :param painter: Active painter for this paint event.
        :param plot_rect: Data drawing rectangle.
        :return: None.
        """
        x_minimum: float
        x_maximum: float
        y_minimum: float
        y_maximum: float
        x_minimum, x_maximum = self.axis_x.get_visual_range()
        y_minimum, y_maximum = self.axis_y.get_visual_range()
        grid_pen: QtGui.QPen = QtGui.QPen(self._grid_color, 1.0)
        painter.setPen(grid_pen)
        tick_index: int
        for tick_index in range(6):
            fraction: float = float(tick_index) / 5.0
            x_position: float = plot_rect.left() + plot_rect.width() * fraction
            y_position: float = plot_rect.bottom() - plot_rect.height() * fraction
            painter.drawLine(QtCore.QPointF(x_position, plot_rect.top()), QtCore.QPointF(x_position, plot_rect.bottom()))
            painter.drawLine(QtCore.QPointF(plot_rect.left(), y_position), QtCore.QPointF(plot_rect.right(), y_position))

            painter.setPen(QtGui.QPen(self._label_color))
            x_value: float = x_minimum + (x_maximum - x_minimum) * fraction
            y_value: float = y_minimum + (y_maximum - y_minimum) * fraction
            painter.drawText(QtCore.QRectF(x_position - 42.0, plot_rect.bottom() + 5.0, 84.0, 18.0),
                             QtCore.Qt.AlignmentFlag.AlignHCenter | QtCore.Qt.AlignmentFlag.AlignTop,
                             format_chart_value(value=x_value, is_datetime=self._x_is_datetime))
            painter.drawText(QtCore.QRectF(2.0, y_position - 9.0, plot_rect.left() - 9.0, 18.0),
                             QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter,
                             format_chart_value(value=y_value, is_datetime=False))
            painter.setPen(grid_pen)

        painter.setPen(QtGui.QPen(self._label_color))
        painter.drawText(QtCore.QRectF(plot_rect.left(), plot_rect.bottom() + 28.0, plot_rect.width(), 20.0),
                         QtCore.Qt.AlignmentFlag.AlignHCenter | QtCore.Qt.AlignmentFlag.AlignTop,
                         self.axis_x.get_title())
        painter.save()
        painter.translate(15.0, plot_rect.center().y())
        painter.rotate(-90.0)
        painter.drawText(QtCore.QRectF(-plot_rect.height() * 0.5, -10.0, plot_rect.height(), 20.0),
                         QtCore.Qt.AlignmentFlag.AlignHCenter | QtCore.Qt.AlignmentFlag.AlignVCenter,
                         self.axis_y.get_title())
        painter.restore()

    def _paint_xy_series(self, painter: QtGui.QPainter, plot_rect: QtCore.QRectF) -> None:
        """Paint line paths and circular scatter markers inside the XY axes.

        :param painter: Active painter for this paint event.
        :param plot_rect: Data drawing rectangle.
        :return: None.
        """
        series: ChartSeries
        for series in self._series:
            if series.get_series_type() == ChartSeriesType.LINE:
                self._paint_line_series(painter=painter, plot_rect=plot_rect, series=series)
            elif series.get_series_type() == ChartSeriesType.SCATTER:
                self._paint_scatter_series(painter=painter, plot_rect=plot_rect, series=series)
            else:
                pass

    def _paint_line_series(self,
                           painter: QtGui.QPainter,
                           plot_rect: QtCore.QRectF,
                           series: ChartSeries) -> None:
        """Paint one sampled line path from an owned NumPy buffer.

        :param painter: Active painter for this paint event.
        :param plot_rect: Data drawing rectangle.
        :param series: Owned line series to draw.
        :return: None.
        """
        x_data: np.ndarray = series.get_x_data()
        y_data: np.ndarray = series.get_y_data()
        if len(x_data) > 0:
            indices: np.ndarray = self._sample_indices(point_count=len(x_data), plot_rect=plot_rect)
            path: QtGui.QPainterPath = QtGui.QPainterPath()
            point_index: int
            for point_index in range(len(indices)):
                data_index: int = int(indices[point_index])
                point: QtCore.QPointF = self._map_xy_point(
                    x_value=float(x_data[data_index]),
                    y_value=float(y_data[data_index]),
                    plot_rect=plot_rect,
                )
                if point_index == 0:
                    path.moveTo(point)
                else:
                    path.lineTo(point)
            painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
            painter.setPen(QtGui.QPen(series.get_color(), 1.8))
            painter.drawPath(path)
        else:
            pass

    def _paint_scatter_series(self,
                              painter: QtGui.QPainter,
                              plot_rect: QtCore.QRectF,
                              series: ChartSeries) -> None:
        """Paint circular markers from an owned NumPy buffer.

        :param painter: Active painter for this paint event.
        :param plot_rect: Data drawing rectangle.
        :param series: Owned scatter series to draw.
        :return: None.
        """
        x_data: np.ndarray = series.get_x_data()
        y_data: np.ndarray = series.get_y_data()
        if len(x_data) > 0:
            indices: np.ndarray = self._sample_indices(point_count=len(x_data), plot_rect=plot_rect)
            color: QtGui.QColor = series.get_color()
            painter.setPen(QtGui.QPen(color.darker(125), 1.0))
            painter.setBrush(QtGui.QBrush(color))
            point_index: int
            for point_index in range(len(indices)):
                data_index: int = int(indices[point_index])
                point: QtCore.QPointF = self._map_xy_point(
                    x_value=float(x_data[data_index]),
                    y_value=float(y_data[data_index]),
                    plot_rect=plot_rect,
                )
                # QRectF selects the bounded ellipse overload across PySide versions.
                marker_rect: QtCore.QRectF = QtCore.QRectF(
                    point.x() - 4.5,
                    point.y() - 4.5,
                    9.0,
                    9.0,
                )
                painter.drawEllipse(marker_rect)
        else:
            pass

    def _paint_histogram(self, painter: QtGui.QPainter, plot_rect: QtCore.QRectF) -> None:
        """Paint the equal-width bin rectangles held by one histogram series.

        :param painter: Active painter clipped to the numeric plot rectangle.
        :param plot_rect: Rectangle used to map bin edges and frequencies.
        :return: None.
        """
        if len(self._series) == 1 and self._series[0].get_series_type() == ChartSeriesType.HISTOGRAM:
            series: ChartSeries = self._series[0]
            edges: np.ndarray = series.get_x_data()
            counts: np.ndarray = series.get_y_data()
            if len(edges) == len(counts) + 1:
                color: QtGui.QColor = series.get_color()
                fill_color: QtGui.QColor = QtGui.QColor(color)
                fill_color.setAlpha(165)
                painter.setPen(QtGui.QPen(color.darker(120), 1.0))
                painter.setBrush(QtGui.QBrush(fill_color))
                baseline: QtCore.QPointF = self._map_xy_point(
                    x_value=float(edges[0]),
                    y_value=0.0,
                    plot_rect=plot_rect,
                )
                bin_index: int
                for bin_index in range(len(counts)):
                    left_point: QtCore.QPointF = self._map_xy_point(
                        x_value=float(edges[bin_index]),
                        y_value=0.0,
                        plot_rect=plot_rect,
                    )
                    right_point: QtCore.QPointF = self._map_xy_point(
                        x_value=float(edges[bin_index + 1]),
                        y_value=float(counts[bin_index]),
                        plot_rect=plot_rect,
                    )
                    # The baseline follows pan and zoom, preserving natural rectangle geometry.
                    rectangle: QtCore.QRectF = QtCore.QRectF(left_point, right_point).normalized()
                    rectangle.setBottom(baseline.y())
                    painter.drawRect(rectangle.normalized())
            else:
                pass
        else:
            pass

    def _paint_cumulative_areas(self, painter: QtGui.QPainter, plot_rect: QtCore.QRectF) -> None:
        """Paint each stacked area between its prior and cumulative values.

        :param painter: Active painter clipped to the numeric plot rectangle.
        :param plot_rect: Rectangle used to map the shared X and Y coordinates.
        :return: None.
        """
        if len(self._series) > 0:
            point_count: int = len(self._series[0].get_x_data())
            indices: np.ndarray = self._sample_indices(point_count=point_count, plot_rect=plot_rect)
            cumulative_values: np.ndarray = np.zeros(point_count, dtype=float)
            series: ChartSeries
            for series in self._series:
                if series.get_series_type() == ChartSeriesType.CUMULATIVE_AREA:
                    x_data: np.ndarray = series.get_x_data()
                    y_data: np.ndarray = series.get_y_data()
                    upper_values: np.ndarray = cumulative_values + y_data
                    if len(indices) > 0:
                        first_index: int = int(indices[0])
                        path: QtGui.QPainterPath = QtGui.QPainterPath()
                        lower_first: QtCore.QPointF = self._map_xy_point(
                            x_value=float(x_data[first_index]),
                            y_value=float(cumulative_values[first_index]),
                            plot_rect=plot_rect,
                        )
                        path.moveTo(lower_first)
                        point_index: int
                        for point_index in range(len(indices)):
                            data_index: int = int(indices[point_index])
                            upper_point: QtCore.QPointF = self._map_xy_point(
                                x_value=float(x_data[data_index]),
                                y_value=float(upper_values[data_index]),
                                plot_rect=plot_rect,
                            )
                            path.lineTo(upper_point)
                        reverse_index: int
                        for reverse_index in range(len(indices) - 1, -1, -1):
                            data_index = int(indices[reverse_index])
                            lower_point: QtCore.QPointF = self._map_xy_point(
                                x_value=float(x_data[data_index]),
                                y_value=float(cumulative_values[data_index]),
                                plot_rect=plot_rect,
                            )
                            path.lineTo(lower_point)
                        path.closeSubpath()
                        area_color: QtGui.QColor = series.get_color()
                        fill_color: QtGui.QColor = QtGui.QColor(area_color)
                        fill_color.setAlpha(145)
                        painter.setPen(QtGui.QPen(area_color.darker(120), 1.25))
                        painter.setBrush(QtGui.QBrush(fill_color))
                        painter.drawPath(path)
                    else:
                        pass
                    cumulative_values = upper_values
                else:
                    pass
        else:
            pass

    def _get_polar_rect(self, plot_rect: QtCore.QRectF) -> QtCore.QRectF:
        """Return a centred square inside the available plot rectangle.

        :param plot_rect: Rectangle reserved for the plotted content.
        :return: Square used for radial grid geometry.
        """
        diameter: float = min(plot_rect.width(), plot_rect.height()) - 20.0
        if diameter > 2.0:
            return QtCore.QRectF(
                plot_rect.center().x() - diameter * 0.5,
                plot_rect.center().y() - diameter * 0.5,
                diameter,
                diameter,
            )
        else:
            return QtCore.QRectF()

    def _paint_polar_axes(self, painter: QtGui.QPainter, plot_rect: QtCore.QRectF) -> None:
        """Paint the radial grid, angular guides, and radial labels.

        :param painter: Active painter used for the polar grid.
        :param plot_rect: Rectangle available to the polar content.
        :return: None.
        """
        polar_rect: QtCore.QRectF = self._get_polar_rect(plot_rect=plot_rect)
        if polar_rect.width() > 2.0:
            centre: QtCore.QPointF = polar_rect.center()
            outer_radius: float = polar_rect.width() * 0.5
            radial_minimum: float
            radial_maximum: float
            radial_minimum, radial_maximum = self.axis_y.get_visual_range()
            grid_pen: QtGui.QPen = QtGui.QPen(self._grid_color, 1.0)
            painter.setPen(grid_pen)
            painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
            circle_index: int
            for circle_index in range(1, 5):
                fraction: float = float(circle_index) / 4.0
                radius: float = outer_radius * fraction
                painter.drawEllipse(QtCore.QRectF(
                    centre.x() - radius,
                    centre.y() - radius,
                    radius * 2.0,
                    radius * 2.0,
                ))
                radial_value: float = radial_minimum + (radial_maximum - radial_minimum) * fraction
                painter.setPen(QtGui.QPen(self._label_color))
                painter.drawText(
                    QtCore.QPointF(centre.x() + 4.0, centre.y() - radius + 13.0),
                    format_chart_value(value=radial_value, is_datetime=False),
                )
                painter.setPen(grid_pen)

            ray_index: int
            for ray_index in range(12):
                angle: float = float(ray_index) * np.pi / 6.0
                end_point: QtCore.QPointF = QtCore.QPointF(
                    centre.x() + outer_radius * np.cos(angle),
                    centre.y() - outer_radius * np.sin(angle),
                )
                painter.drawLine(centre, end_point)
                if ray_index % 3 == 0:
                    painter.setPen(QtGui.QPen(self._label_color))
                    label_point: QtCore.QPointF = QtCore.QPointF(
                        centre.x() + (outer_radius + 14.0) * np.cos(angle),
                        centre.y() - (outer_radius + 14.0) * np.sin(angle),
                    )
                    painter.drawText(
                        QtCore.QRectF(label_point.x() - 18.0, label_point.y() - 9.0, 36.0, 18.0),
                        QtCore.Qt.AlignmentFlag.AlignCenter,
                        f'{ray_index * 30}°',
                    )
                    painter.setPen(grid_pen)

            painter.setPen(QtGui.QPen(self._label_color))
            painter.drawText(
                QtCore.QRectF(plot_rect.left(), plot_rect.bottom() + 28.0, plot_rect.width(), 20.0),
                QtCore.Qt.AlignmentFlag.AlignHCenter | QtCore.Qt.AlignmentFlag.AlignTop,
                self.axis_y.get_title(),
            )
        else:
            pass

    def _paint_polar_series(self, painter: QtGui.QPainter, plot_rect: QtCore.QRectF) -> None:
        """Paint every native polar line and its circular sample points.

        :param painter: Active painter clipped to the numeric plot rectangle.
        :param plot_rect: Rectangle used for the radial mapping.
        :return: None.
        """
        polar_rect: QtCore.QRectF = self._get_polar_rect(plot_rect=plot_rect)
        series: ChartSeries
        for series in self._series:
            if (series.get_series_type() in (ChartSeriesType.POLAR, ChartSeriesType.POLAR_SCATTER)
                    and polar_rect.width() > 2.0):
                angles: np.ndarray = series.get_x_data()
                radii: np.ndarray = series.get_y_data()
                indices: np.ndarray = self._sample_indices(point_count=len(angles), plot_rect=polar_rect)
                if len(indices) > 0:
                    if series.get_series_type() == ChartSeriesType.POLAR:
                        path: QtGui.QPainterPath = QtGui.QPainterPath()
                        point_index: int
                        for point_index in range(len(indices)):
                            data_index: int = int(indices[point_index])
                            point: QtCore.QPointF = self._map_polar_point(
                                angle=float(angles[data_index]),
                                radius=float(radii[data_index]),
                                polar_rect=polar_rect,
                            )
                            if point_index == 0:
                                path.moveTo(point)
                            else:
                                path.lineTo(point)
                    else:
                        path = QtGui.QPainterPath()
                    color: QtGui.QColor = series.get_color()
                    if series.get_series_type() == ChartSeriesType.POLAR:
                        painter.setPen(QtGui.QPen(color, 1.8))
                        painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
                        painter.drawPath(path)
                    else:
                        pass
                    painter.setPen(QtGui.QPen(color.darker(125), 1.0))
                    painter.setBrush(QtGui.QBrush(color))
                    for point_index in range(len(indices)):
                        data_index = int(indices[point_index])
                        point = self._map_polar_point(
                            angle=float(angles[data_index]),
                            radius=float(radii[data_index]),
                            polar_rect=polar_rect,
                        )
                        painter.drawEllipse(QtCore.QRectF(point.x() - 3.0, point.y() - 3.0, 6.0, 6.0))
                else:
                    pass
            else:
                pass

    def _paint_bar_axes(self, painter: QtGui.QPainter, plot_rect: QtCore.QRectF) -> None:
        """Paint numeric horizontal ticks and category labels for bar charts.

        :param painter: Active painter for this paint event.
        :param plot_rect: Data drawing rectangle.
        :return: None.
        """
        x_minimum: float
        x_maximum: float
        x_minimum, x_maximum = self.axis_x.get_visual_range()
        grid_pen: QtGui.QPen = QtGui.QPen(self._grid_color, 1.0)
        painter.setPen(grid_pen)
        tick_index: int
        for tick_index in range(6):
            fraction: float = float(tick_index) / 5.0
            x_position: float = plot_rect.left() + plot_rect.width() * fraction
            painter.drawLine(QtCore.QPointF(x_position, plot_rect.top()), QtCore.QPointF(x_position, plot_rect.bottom()))
            painter.setPen(QtGui.QPen(self._label_color))
            x_value: float = x_minimum + (x_maximum - x_minimum) * fraction
            painter.drawText(QtCore.QRectF(x_position - 42.0, plot_rect.bottom() + 5.0, 84.0, 18.0),
                             QtCore.Qt.AlignmentFlag.AlignHCenter | QtCore.Qt.AlignmentFlag.AlignTop,
                             format_chart_value(value=x_value, is_datetime=False))
            painter.setPen(grid_pen)

        label_index: int
        for label_index in range(len(self._bar_labels)):
            y_position: float = self._map_bar_category(index=label_index, plot_rect=plot_rect)
            painter.setPen(QtGui.QPen(self._label_color))
            painter.drawText(QtCore.QRectF(2.0, y_position - 9.0, plot_rect.left() - 8.0, 18.0),
                             QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter,
                             self._bar_labels[label_index])
        painter.setPen(QtGui.QPen(self._label_color))
        painter.drawText(QtCore.QRectF(plot_rect.left(), plot_rect.bottom() + 28.0, plot_rect.width(), 20.0),
                         QtCore.Qt.AlignmentFlag.AlignHCenter | QtCore.Qt.AlignmentFlag.AlignTop,
                         self.axis_x.get_title())

    def _paint_horizontal_bars(self, painter: QtGui.QPainter, plot_rect: QtCore.QRectF) -> None:
        """Paint horizontal bars from the two owned positive and negative buffers.

        :param painter: Active painter for this paint event.
        :param plot_rect: Data drawing rectangle.
        :return: None.
        """
        zero_x: float = self._map_x_value(value=0.0, plot_rect=plot_rect)
        bar_height: float = max(plot_rect.height() / max(len(self._bar_labels), 1) * 0.62, 2.0)
        series: ChartSeries
        for series in self._series:
            if series.get_series_type() == ChartSeriesType.HORIZONTAL_BAR:
                x_data: np.ndarray = series.get_x_data()
                y_data: np.ndarray = series.get_y_data()
                painter.setPen(QtCore.Qt.PenStyle.NoPen)
                painter.setBrush(QtGui.QBrush(series.get_color()))
                point_index: int
                for point_index in range(len(x_data)):
                    end_x: float = self._map_x_value(value=float(y_data[point_index]), plot_rect=plot_rect)
                    centre_y: float = self._map_bar_category(index=int(x_data[point_index]), plot_rect=plot_rect)
                    rectangle: QtCore.QRectF = QtCore.QRectF(
                        min(zero_x, end_x),
                        centre_y - bar_height * 0.5,
                        abs(end_x - zero_x),
                        bar_height,
                    )
                    painter.drawRect(rectangle)
            else:
                pass

    def _map_xy_point(self, x_value: float, y_value: float, plot_rect: QtCore.QRectF) -> QtCore.QPointF:
        """Map one XY data point into the current painter rectangle.

        :param x_value: Horizontal data coordinate.
        :param y_value: Vertical data coordinate.
        :param plot_rect: Data drawing rectangle.
        :return: Pixel coordinate for the painter.
        """
        x_position: float = self._map_x_value(value=x_value, plot_rect=plot_rect)
        y_minimum: float
        y_maximum: float
        y_minimum, y_maximum = self.axis_y.get_visual_range()
        y_fraction: float = (y_value - y_minimum) / (y_maximum - y_minimum)
        y_position: float = plot_rect.bottom() - y_fraction * plot_rect.height()
        return QtCore.QPointF(x_position, y_position)

    def _map_polar_point(self, angle: float, radius: float, polar_rect: QtCore.QRectF) -> QtCore.QPointF:
        """Map one polar coordinate into the radial drawing square.

        :param angle: Angle in radians.
        :param radius: Non-negative radial coordinate.
        :param polar_rect: Square used for the polar grid.
        :return: Point in widget coordinates.
        """
        radial_minimum: float
        radial_maximum: float
        radial_minimum, radial_maximum = self.axis_y.get_visual_range()
        radial_fraction: float = (radius - radial_minimum) / (radial_maximum - radial_minimum)
        bounded_fraction: float = min(max(radial_fraction, 0.0), 1.0)
        outer_radius: float = polar_rect.width() * 0.5
        centre: QtCore.QPointF = polar_rect.center()
        return QtCore.QPointF(
            centre.x() + outer_radius * bounded_fraction * np.cos(angle),
            centre.y() - outer_radius * bounded_fraction * np.sin(angle),
        )

    def _map_x_value(self, value: float, plot_rect: QtCore.QRectF) -> float:
        """Map one horizontal data value into the current painter rectangle.

        :param value: Horizontal data coordinate.
        :param plot_rect: Data drawing rectangle.
        :return: Pixel horizontal coordinate.
        """
        x_minimum: float
        x_maximum: float
        x_minimum, x_maximum = self.axis_x.get_visual_range()
        x_fraction: float = (value - x_minimum) / (x_maximum - x_minimum)
        return plot_rect.left() + x_fraction * plot_rect.width()

    def _map_bar_category(self, index: int, plot_rect: QtCore.QRectF) -> float:
        """Map one category index to its vertical bar-chart centre.

        :param index: Category index.
        :param plot_rect: Data drawing rectangle.
        :return: Pixel vertical coordinate.
        """
        y_minimum: float
        y_maximum: float
        y_minimum, y_maximum = self.axis_y.get_visual_range()
        fraction: float = (float(index) - y_minimum) / (y_maximum - y_minimum)
        return plot_rect.bottom() - fraction * plot_rect.height()

    def _sample_indices(self, point_count: int, plot_rect: QtCore.QRectF) -> np.ndarray:
        """Bound painter work to useful screen resolution for large buffers.

        :param point_count: Number of available data points.
        :param plot_rect: Data drawing rectangle.
        :return: Ordered indices that retain both series endpoints.
        """
        maximum_points: int = max(int(plot_rect.width()) * 2, 2)
        if point_count > maximum_points:
            return np.linspace(0, point_count - 1, maximum_points, dtype=int)
        else:
            return np.arange(point_count, dtype=int)
