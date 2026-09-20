# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""Deterministic lifecycle stress coverage for the native QWidget renderer."""

from __future__ import annotations

import numpy as np
from PySide6 import QtCore, QtGui, QtWidgets

from VeraGrid.Gui.Widgets.qt_chart_widget import ChartContentType, ChartSeriesType, GraphsWidget, PolarAngleUnit


class ObjectDestructionProbe:
    """Record the deferred native destruction of one Qt-owned chart widget."""

    __slots__ = ("destroyed_count",)

    def __init__(self) -> None:
        """Create an empty destruction counter.

        :return: None.
        """
        self.destroyed_count: int = 0

    def mark_destroyed(self, destroyed_object: QtCore.QObject | None = None) -> None:
        """Record Qt's native destruction signal.

        :param destroyed_object: QObject instance being destroyed by Qt.
        :return: None.
        """
        _ = destroyed_object
        self.destroyed_count += 1


def make_wheel_event(widget: GraphsWidget, delta_y: int) -> QtGui.QWheelEvent:
    """Build one wheel event centered in the visible chart widget.

    :param widget: Target chart receiving the zoom operation.
    :param delta_y: Vertical wheel delta in Qt angle units.
    :return: Native wheel event for the widget.
    """
    local_position: QtCore.QPointF = QtCore.QPointF(widget.width() * 0.5, widget.height() * 0.5)
    global_position: QtCore.QPointF = QtCore.QPointF(widget.mapToGlobal(local_position.toPoint()))
    return QtGui.QWheelEvent(
        local_position,
        global_position,
        QtCore.QPoint(0, 0),
        QtCore.QPoint(0, delta_y),
        QtCore.Qt.MouseButton.NoButton,
        QtCore.Qt.KeyboardModifier.NoModifier,
        QtCore.Qt.ScrollPhase.ScrollUpdate,
        False,
    )


def make_mouse_event(event_type: QtCore.QEvent.Type,
                     widget: GraphsWidget,
                     local_position: QtCore.QPointF,
                     button: QtCore.Qt.MouseButton,
                     buttons: QtCore.Qt.MouseButton,
                     modifiers: QtCore.Qt.KeyboardModifier = QtCore.Qt.KeyboardModifier.NoModifier
                     ) -> QtGui.QMouseEvent:
    """Build one mouse event in the chart coordinate system.

    :param event_type: Qt mouse event type.
    :param widget: Target chart receiving the input operation.
    :param local_position: Pointer position in chart pixels.
    :param button: Button that caused the event.
    :param buttons: Buttons held while the event is delivered.
    :param modifiers: Keyboard modifiers held during the gesture.
    :return: Native mouse event for the widget.
    """
    global_position: QtCore.QPointF = QtCore.QPointF(widget.mapToGlobal(local_position.toPoint()))
    return QtGui.QMouseEvent(
        event_type,
        local_position,
        global_position,
        button,
        buttons,
        modifiers,
    )


def paint_chart_to_image(widget: GraphsWidget) -> QtGui.QImage:
    """Render the current chart to an owned raster paint device.

    :param widget: Chart whose full paint path is exercised.
    :return: Non-null image containing the chart rendering.
    """
    image: QtGui.QImage = QtGui.QImage(
        widget.size(),
        QtGui.QImage.Format.Format_ARGB32_Premultiplied,
    )
    image.fill(QtGui.QColor("#ffffff"))
    painter: QtGui.QPainter = QtGui.QPainter(image)
    widget.render(painter, QtCore.QPoint(0, 0))
    painter.end()
    return image


def delete_chart_owner(owner: QtWidgets.QDialog,
                       chart: GraphsWidget,
                       probe: ObjectDestructionProbe,
                       app: QtWidgets.QApplication) -> None:
    """Dispose and destroy one QWidget chart through its parent-child owner tree.

    :param owner: Dialog owning the chart through a Qt layout.
    :param chart: Chart whose Python buffers must be released.
    :param probe: Recorder attached to the chart destruction signal.
    :param app: Shared Qt application that receives deferred deletions.
    :return: None.
    """
    owner.reject()
    chart.deleteLater()
    owner.deleteLater()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)
    app.processEvents()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)
    app.processEvents()
    assert probe.destroyed_count == 1


def drag_select_zoom(chart: GraphsWidget) -> None:
    """Deliver one left-button selection across the current chart data area.

    :param chart: Visible native chart receiving the zoom gesture.
    :return: None.
    """
    plot_rect: QtCore.QRectF = chart._get_plot_rect()
    start_position: QtCore.QPointF = QtCore.QPointF(
        plot_rect.left() + plot_rect.width() * 0.25,
        plot_rect.top() + plot_rect.height() * 0.25,
    )
    end_position: QtCore.QPointF = QtCore.QPointF(
        plot_rect.left() + plot_rect.width() * 0.75,
        plot_rect.top() + plot_rect.height() * 0.75,
    )
    chart.mousePressEvent(make_mouse_event(
        event_type=QtCore.QEvent.Type.MouseButtonPress,
        widget=chart,
        local_position=start_position,
        button=QtCore.Qt.MouseButton.LeftButton,
        buttons=QtCore.Qt.MouseButton.LeftButton,
    ))
    chart.mouseMoveEvent(make_mouse_event(
        event_type=QtCore.QEvent.Type.MouseMove,
        widget=chart,
        local_position=end_position,
        button=QtCore.Qt.MouseButton.NoButton,
        buttons=QtCore.Qt.MouseButton.LeftButton,
    ))
    chart.mouseReleaseEvent(make_mouse_event(
        event_type=QtCore.QEvent.Type.MouseButtonRelease,
        widget=chart,
        local_position=end_position,
        button=QtCore.Qt.MouseButton.LeftButton,
        buttons=QtCore.Qt.MouseButton.NoButton,
    ))


def test_chart_widget_rectangle_zoom_covers_every_native_renderer(
        qt_app: QtWidgets.QApplication) -> None:
    """Verify every chart mode accepts a left-drag zoom without retained Qt items.

    :param qt_app: Shared Qt application fixture.
    :return: None.
    """
    owner: QtWidgets.QDialog = QtWidgets.QDialog()
    layout: QtWidgets.QVBoxLayout = QtWidgets.QVBoxLayout(owner)
    chart: GraphsWidget = GraphsWidget(parent=owner)
    layout.addWidget(chart)
    owner.resize(720, 520)
    owner.show()
    qt_app.processEvents()

    chart.add_line_series(
        name="XY",
        x_values=np.array((0.0, 1.0, 2.0, 3.0), dtype=float),
        y_values=np.array((1.0, 3.0, 2.0, 4.0), dtype=float),
    )
    drag_select_zoom(chart=chart)
    assert chart.axis_x.get_zoom() > 1.0
    assert chart.axis_y.get_zoom() > 1.0

    assert chart.set_cumulative_area_series(
        x_values=np.array((0.0, 1.0, 2.0, 3.0), dtype=float),
        series_names=("A", "B"),
        series_values=(
            np.array((1.0, 2.0, 1.0, 2.0), dtype=float),
            np.array((2.0, 1.0, 2.0, 1.0), dtype=float),
        ),
    )
    drag_select_zoom(chart=chart)
    assert chart.axis_x.get_zoom() > 1.0
    assert chart.axis_y.get_zoom() > 1.0

    chart.add_horizontal_bar_series(
        labels=("A", "B", "C"),
        values=np.array((1.0, -2.0, 3.0), dtype=float),
        positive_color="#0f766e",
        negative_color="#dc2626",
    )
    drag_select_zoom(chart=chart)
    assert chart.axis_x.get_zoom() > 1.0

    assert chart.set_histogram(
        values=np.array((-2.0, -1.0, 0.0, 1.0, 2.0), dtype=float),
        bin_count=3,
    )
    drag_select_zoom(chart=chart)
    assert chart.axis_x.get_zoom() > 1.0
    assert chart.axis_y.get_zoom() > 1.0

    assert chart.set_polar_series(
        series_names=("Polar",),
        angle_values=(np.array((0.0, 90.0, 180.0, 270.0), dtype=float),),
        radius_values=(np.array((1.0, 0.5, 0.8, 1.2), dtype=float),),
        angle_unit=PolarAngleUnit.DEGREES,
    )
    drag_select_zoom(chart=chart)
    assert chart.axis_y.get_zoom() > 1.0

    chart.dispose()
    owner.deleteLater()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)
    qt_app.processEvents()


def test_line_decimation_preserves_spikes_for_dense_series(
        qt_app: QtWidgets.QApplication) -> None:
    """Retain local peaks and dips when a long line is reduced to screen pixels.

    :param qt_app: Shared Qt application fixture.
    :return: None.
    """
    chart: GraphsWidget = GraphsWidget()
    chart.resize(400, 260)
    source_x: np.ndarray = np.linspace(0.0, 1.0, 10000, dtype=float)
    source_y: np.ndarray = np.zeros(len(source_x), dtype=float)
    source_y[4321] = 20.0
    source_y[7654] = -10.0
    chart.add_line_series(name='Spikes', x_values=source_x, y_values=source_y)
    plot_rect: QtCore.QRectF = chart._get_plot_rect()
    retained_indices: np.ndarray = chart._sample_xy_indices(
        x_data=chart._series[0].get_x_data(),
        y_data=chart._series[0].get_y_data(),
        x_is_monotonic=chart._series[0].get_x_is_monotonic(),
        plot_rect=plot_rect,
        visible_line_count=2224,
    )
    assert len(retained_indices) <= 500000 // 2224
    assert 4321 in retained_indices
    assert 7654 in retained_indices
    chart.dispose()
    chart.deleteLater()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)
    qt_app.processEvents()


def test_chart_widget_stress_replaces_data_paints_and_destroys_cleanly(
        qt_app: QtWidgets.QApplication) -> None:
    """Stress XY updates, input, paint, mode changes, and deferred destruction.

    :param qt_app: Shared Qt application fixture.
    :return: None.
    """
    app: QtWidgets.QApplication = qt_app
    random_generator: np.random.Generator = np.random.default_rng(91627)
    cycle_index: int

    for cycle_index in range(48):
        owner: QtWidgets.QDialog = QtWidgets.QDialog()
        layout: QtWidgets.QVBoxLayout = QtWidgets.QVBoxLayout(owner)
        chart: GraphsWidget = GraphsWidget(parent=owner)
        probe: ObjectDestructionProbe = ObjectDestructionProbe()
        chart.destroyed.connect(probe.mark_destroyed)
        layout.addWidget(chart)
        owner.resize(640 + cycle_index * 4, 460 + cycle_index * 3)
        owner.show()
        app.processEvents()

        source_x: np.ndarray = np.linspace(-8.0, 8.0, 2048, dtype=float)
        source_y: np.ndarray = np.sin(source_x) + random_generator.normal(0.0, 0.01, len(source_x))
        source_y[17] = np.nan
        source_y[31] = np.inf
        chart.setTitle(f"Stress cycle {cycle_index}")
        chart.set_axis_titles("X", "Y")
        chart.add_line_series(name="Line", x_values=source_x, y_values=source_y, color="#2563eb")
        chart.add_scatter_series(
            name="Points",
            x_values=source_x[::256],
            y_values=source_y[::256],
            color="#f97316",
            point_tooltips=tuple(f"Point {point_index}" for point_index in range(8)),
        )
        assert len(chart._series) == 2
        assert chart._series[0].get_series_type() == ChartSeriesType.LINE
        assert chart._series[1].get_series_type() == ChartSeriesType.SCATTER
        scatter_point: QtCore.QPointF = chart._map_xy_point(
            x_value=float(chart._series[1].get_x_data()[0]),
            y_value=float(chart._series[1].get_y_data()[0]),
            plot_rect=chart._get_plot_rect(),
        )
        assert chart.get_point_tooltip_at(position=scatter_point) == "Point 0"

        # ChartSeries copies inputs, so a producer changing its own buffer cannot
        # race the QWidget paint path through shared NumPy memory.
        first_chart_value: float = float(chart._series[0].get_y_data()[1])
        source_y[1] = 999999.0
        assert float(chart._series[0].get_y_data()[1]) == first_chart_value

        update_index: int
        stable_series: tuple[object, ...] = tuple(chart._series)
        for update_index in range(16):
            update_x: np.ndarray = np.linspace(-8.0, 8.0, 1024 + update_index, dtype=float)
            update_line_y: np.ndarray = np.cos(update_x * float(update_index + 1) * 0.1)
            update_scatter_x: np.ndarray = update_x[::128]
            update_scatter_y: np.ndarray = update_line_y[::128]
            assert chart.replace_xy_series_data(
                series_data=(
                    (update_x, update_line_y, "#2563eb"),
                    (update_scatter_x, update_scatter_y, "#f97316"),
                )
            )
            assert tuple(chart._series) == stable_series
            owner.resize(640 + update_index * 11, 460 + update_index * 7)
            chart.redraw()
            app.processEvents()
            image: QtGui.QImage = paint_chart_to_image(widget=chart)
            assert not image.isNull()

        # Invalid replacements must leave the existing owned series untouched.
        assert not chart.replace_xy_series_data(
            series_data=((np.array((0.0, 1.0)), np.array((0.0, 1.0)), "#2563eb"),)
        )
        assert tuple(chart._series) == stable_series

        chart.wheelEvent(make_wheel_event(widget=chart, delta_y=120))
        chart.wheelEvent(make_wheel_event(widget=chart, delta_y=120))
        assert chart.axis_x.get_zoom() > 1.0
        assert chart.axis_y.get_zoom() > 1.0
        wheel_zoom: float = chart.axis_x.get_zoom()
        plot_rect: QtCore.QRectF = chart._get_plot_rect()
        x_zoom_before_selection: float = chart.axis_x.get_zoom()
        y_zoom_before_selection: float = chart.axis_y.get_zoom()
        press_position: QtCore.QPointF = QtCore.QPointF(chart.width() * 0.45, chart.height() * 0.45)
        move_position: QtCore.QPointF = QtCore.QPointF(chart.width() * 0.62, chart.height() * 0.57)
        chart.mousePressEvent(make_mouse_event(
            event_type=QtCore.QEvent.Type.MouseButtonPress,
            widget=chart,
            local_position=press_position,
            button=QtCore.Qt.MouseButton.LeftButton,
            buttons=QtCore.Qt.MouseButton.LeftButton,
        ))
        chart.mouseMoveEvent(make_mouse_event(
            event_type=QtCore.QEvent.Type.MouseMove,
            widget=chart,
            local_position=move_position,
            button=QtCore.Qt.MouseButton.NoButton,
            buttons=QtCore.Qt.MouseButton.LeftButton,
        ))
        assert chart._zoom_selection is not None
        selection_rect: QtCore.QRectF = chart._zoom_selection
        selection_aspect: float = selection_rect.width() / selection_rect.height()
        assert not np.isclose(selection_aspect, plot_rect.width() / plot_rect.height())
        assert not paint_chart_to_image(widget=chart).isNull()
        chart.mouseReleaseEvent(make_mouse_event(
            event_type=QtCore.QEvent.Type.MouseButtonRelease,
            widget=chart,
            local_position=move_position,
            button=QtCore.Qt.MouseButton.LeftButton,
            buttons=QtCore.Qt.MouseButton.NoButton,
        ))
        assert chart.axis_x.get_zoom() > wheel_zoom
        assert chart.axis_y.get_zoom() > wheel_zoom
        adjusted_plot: QtCore.QRectF = chart._get_plot_rect()
        assert np.isclose(adjusted_plot.width(), plot_rect.width())
        assert np.isclose(adjusted_plot.height(), plot_rect.height())
        assert np.isclose(
            chart.axis_x.get_zoom() * selection_rect.width() / plot_rect.width(),
            x_zoom_before_selection,
        )
        assert np.isclose(
            chart.axis_y.get_zoom() * selection_rect.height() / plot_rect.height(),
            y_zoom_before_selection,
        )
        assert chart._zoom_selection is None
        chart.reset_viewport()
        assert chart.axis_x.get_pan() == 0.0
        assert chart.axis_y.get_pan() == 0.0

        chart.mousePressEvent(make_mouse_event(
            event_type=QtCore.QEvent.Type.MouseButtonPress,
            widget=chart,
            local_position=press_position,
            button=QtCore.Qt.MouseButton.LeftButton,
            buttons=QtCore.Qt.MouseButton.LeftButton,
            modifiers=QtCore.Qt.KeyboardModifier.ControlModifier,
        ))
        chart.mouseMoveEvent(make_mouse_event(
            event_type=QtCore.QEvent.Type.MouseMove,
            widget=chart,
            local_position=move_position,
            button=QtCore.Qt.MouseButton.NoButton,
            buttons=QtCore.Qt.MouseButton.LeftButton,
            modifiers=QtCore.Qt.KeyboardModifier.ControlModifier,
        ))
        chart.mouseReleaseEvent(make_mouse_event(
            event_type=QtCore.QEvent.Type.MouseButtonRelease,
            widget=chart,
            local_position=move_position,
            button=QtCore.Qt.MouseButton.LeftButton,
            buttons=QtCore.Qt.MouseButton.NoButton,
            modifiers=QtCore.Qt.KeyboardModifier.ControlModifier,
        ))
        assert chart._zoom_origin is None
        assert chart.axis_x.get_pan() != 0.0
        assert chart.axis_y.get_pan() != 0.0
        chart.reset_viewport()
        assert chart.axis_x.get_zoom() == 1.0
        assert chart.axis_y.get_zoom() == 1.0
        assert chart.axis_x.get_pan() == 0.0
        assert chart.axis_y.get_pan() == 0.0

        # Every renderer mode must tolerate a real paint and zoom cycle.
        assert chart.set_cumulative_area_series(
            x_values=np.array((0.0, 1.0, 2.0, 3.0), dtype=float),
            series_names=("Wind", "Solar"),
            series_values=(
                np.array((1.0, 1.5, np.nan, 2.0), dtype=float),
                np.array((0.5, 0.7, 1.2, 0.6), dtype=float),
            ),
        )
        assert chart._content_type == ChartContentType.CUMULATIVE_AREA
        chart.wheelEvent(make_wheel_event(widget=chart, delta_y=120))
        assert not paint_chart_to_image(widget=chart).isNull()

        chart.add_horizontal_bar_series(
            labels=("A", "B", "C", "D"),
            values=np.array((2.0, -1.0, np.nan, 3.0), dtype=float),
            positive_color="#0f766e",
            negative_color="#dc2626",
        )
        assert chart._content_type == ChartContentType.HORIZONTAL_BAR
        chart.wheelEvent(make_wheel_event(widget=chart, delta_y=-120))
        assert not paint_chart_to_image(widget=chart).isNull()

        assert chart.set_histogram(
            values=np.array((-3.0, -1.0, -1.0, 0.0, 2.0, 4.0, np.nan, np.inf), dtype=float),
            bin_count=5,
        )
        assert chart._content_type == ChartContentType.HISTOGRAM
        histogram_series: tuple[object, ...] = tuple(chart._series)
        assert not chart.set_histogram(values=np.array((1.0, 2.0), dtype=float), bin_count=0)
        assert tuple(chart._series) == histogram_series
        chart.wheelEvent(make_wheel_event(widget=chart, delta_y=120))
        assert not paint_chart_to_image(widget=chart).isNull()

        assert chart.set_polar_series(
            series_names=("Polar",),
            angle_values=(np.array((0.0, 90.0, 180.0, 270.0, 360.0), dtype=float),),
            radius_values=(np.array((1.0, 0.5, 1.2, np.nan, 1.0), dtype=float),),
            angle_unit=PolarAngleUnit.DEGREES,
        )
        assert chart._content_type == ChartContentType.POLAR
        chart.wheelEvent(make_wheel_event(widget=chart, delta_y=120))
        assert not paint_chart_to_image(widget=chart).isNull()

        assert chart.set_polar_series(
            series_names=("Polar points",),
            angle_values=(np.array((0.0, 90.0, 180.0, 270.0), dtype=float),),
            radius_values=(np.array((1.0, 0.6, 1.1, 0.8), dtype=float),),
            angle_unit=PolarAngleUnit.DEGREES,
            connect_points=False,
        )
        assert chart._series[0].get_series_type() == ChartSeriesType.POLAR_SCATTER
        assert not paint_chart_to_image(widget=chart).isNull()

        # Explicit disposal must empty Python buffers before Qt deletes the C++ widget.
        chart.dispose()
        assert chart._disposed
        assert len(chart._series) == 0
        chart.add_line_series(
            name="Ignored after disposal",
            x_values=np.array((0.0, 1.0)),
            y_values=np.array((0.0, 1.0)),
        )
        assert len(chart._series) == 0
        delete_chart_owner(owner=owner, chart=chart, probe=probe, app=app)


def test_chart_widget_validates_tooltips_and_rejects_invalid_mode_data(
        qt_app: QtWidgets.QApplication) -> None:
    """Verify failed public inputs cannot partly mutate an active chart.

    :param qt_app: Shared Qt application fixture.
    :return: None.
    """
    app: QtWidgets.QApplication = qt_app
    owner: QtWidgets.QDialog = QtWidgets.QDialog()
    layout: QtWidgets.QVBoxLayout = QtWidgets.QVBoxLayout(owner)
    chart: GraphsWidget = GraphsWidget(parent=owner)
    probe: ObjectDestructionProbe = ObjectDestructionProbe()
    chart.destroyed.connect(probe.mark_destroyed)
    layout.addWidget(chart)
    owner.resize(720, 520)
    owner.show()
    app.processEvents()

    chart.add_scatter_series(
        name="Buses",
        x_values=np.array((0.0, np.nan, 2.0), dtype=float),
        y_values=np.array((1.0, 2.0, 3.0), dtype=float),
        point_tooltips=("Bus A", "Dropped", "Bus C"),
    )
    assert len(chart._series) == 1
    assert chart._series[0].has_point_tooltips()
    assert chart._series[0].get_point_tooltip(point_index=0) == "Bus A"
    assert chart._series[0].get_point_tooltip(point_index=1) == "Bus C"
    assert not chart.set_series_point_tooltips(series_index=0, point_tooltips=("Only one",))
    assert not chart.set_series_point_tooltips(series_index=1, point_tooltips=("Missing", "series"))

    stable_series: tuple[object, ...] = tuple(chart._series)
    assert not chart.set_cumulative_area_series(
        x_values=np.array((0.0, 1.0), dtype=float),
        series_names=("Invalid",),
        series_values=(np.array((1.0,), dtype=float),),
    )
    assert tuple(chart._series) == stable_series
    assert not chart.set_polar_series(
        series_names=("Invalid",),
        angle_values=(np.array((0.0, 1.0), dtype=float),),
        radius_values=(np.array((-1.0, np.nan), dtype=float),),
    )
    assert tuple(chart._series) == stable_series
    assert not chart.set_polar_series(
        series_names=("Mismatched",),
        angle_values=(np.array((0.0, 1.0), dtype=float),),
        radius_values=(np.array((1.0,), dtype=float),),
    )
    assert tuple(chart._series) == stable_series

    chart.dispose()
    delete_chart_owner(owner=owner, chart=chart, probe=probe, app=app)


def test_dense_random_chart_reuses_vertices_during_zoom_and_pan(
        qt_app: QtWidgets.QApplication) -> None:
    """Stress random line batches and prove unchanged paints skip repacking.

    :param qt_app: Shared Qt application fixture.
    :return: None.
    """
    random_generator: np.random.Generator = np.random.default_rng(20260920)
    owner: QtWidgets.QDialog = QtWidgets.QDialog()
    chart: GraphsWidget = GraphsWidget(parent=owner)
    probe: ObjectDestructionProbe = ObjectDestructionProbe()
    chart.destroyed.connect(probe.mark_destroyed)
    chart.set_rhi_line_rendering(enabled=True, series_threshold=32)
    chart.resize(1100, 720)
    point_count: int = 12000
    x_values: np.ndarray = np.linspace(0.0, 120.0, point_count, dtype=float)
    series_index: int
    for series_index in range(48):
        noise: np.ndarray = random_generator.normal(0.0, 0.08, point_count)
        frequency: float = float(random_generator.uniform(0.05, 1.5))
        phase: float = float(random_generator.uniform(-np.pi, np.pi))
        y_values: np.ndarray = np.sin(x_values * frequency + phase) + noise + series_index * 0.01
        chart.add_line_series(
            name=f"random {series_index}",
            x_values=x_values,
            y_values=y_values,
            color=QtGui.QColor.fromHsv((series_index * 47) % 360, 190, 190),
        )
    plot_rect: QtCore.QRectF = chart._get_plot_rect()
    assert chart._prepare_rhi_line_layer(plot_rect=plot_rect)
    assert chart._rhi_line_widget is not None
    first_revision: int = chart._rhi_line_widget._data_revision
    repeat_index: int
    for repeat_index in range(12):
        assert chart._prepare_rhi_line_layer(plot_rect=plot_rect)
        assert chart._rhi_line_widget._data_revision == first_revision
    image: QtGui.QImage = QtGui.QImage(
        chart.size(), QtGui.QImage.Format.Format_ARGB32_Premultiplied
    )
    painter: QtGui.QPainter = QtGui.QPainter(image)
    chart.paint_to_painter(painter=painter, paint_lines=False)
    painter.end()
    assert not image.isNull()
    chart._center_from_context_menu()
    assert chart.axis_x.get_zoom() == 1.0
    assert chart.axis_y.get_zoom() == 1.0

    gesture_index: int
    for gesture_index in range(12):
        plot_rect = chart._get_plot_rect()
        x_zoom_before_selection: float = chart.axis_x.get_zoom()
        y_zoom_before_selection: float = chart.axis_y.get_zoom()
        selection_start: QtCore.QPointF = QtCore.QPointF(
            plot_rect.left() + plot_rect.width() * 0.25,
            plot_rect.top() + plot_rect.height() * 0.25,
        )
        selection_end: QtCore.QPointF = QtCore.QPointF(
            plot_rect.left() + plot_rect.width() * 0.72,
            plot_rect.top() + plot_rect.height() * 0.60,
        )
        chart.mousePressEvent(make_mouse_event(
            event_type=QtCore.QEvent.Type.MouseButtonPress,
            widget=chart,
            local_position=selection_start,
            button=QtCore.Qt.MouseButton.LeftButton,
            buttons=QtCore.Qt.MouseButton.LeftButton,
        ))
        chart.mouseMoveEvent(make_mouse_event(
            event_type=QtCore.QEvent.Type.MouseMove,
            widget=chart,
            local_position=selection_end,
            button=QtCore.Qt.MouseButton.NoButton,
            buttons=QtCore.Qt.MouseButton.LeftButton,
        ))
        assert chart._zoom_selection is not None
        selection_rect: QtCore.QRectF = chart._zoom_selection
        selection_aspect: float = selection_rect.width() / selection_rect.height()
        assert not np.isclose(selection_aspect, plot_rect.width() / plot_rect.height())
        assert chart._pan_position is None
        assert chart.axis_x.get_pan() == 0.0
        assert chart.axis_y.get_pan() == 0.0
        assert chart._rhi_selection_overlay is not None
        assert not chart._rhi_selection_overlay.isHidden()
        overlay_image: QtGui.QImage = QtGui.QImage(
            chart.size(), QtGui.QImage.Format.Format_ARGB32_Premultiplied
        )
        overlay_image.fill(QtCore.Qt.GlobalColor.transparent)
        overlay_painter: QtGui.QPainter = QtGui.QPainter(overlay_image)
        chart._rhi_selection_overlay.render(overlay_painter, QtCore.QPoint(0, 0))
        overlay_painter.end()
        overlay_probe: QtCore.QPoint = QtCore.QPoint(
            int(chart._zoom_selection.left() + chart._zoom_selection.width() * 0.35),
            int(chart._zoom_selection.top() + chart._zoom_selection.height() * 0.35),
        )
        assert overlay_image.pixelColor(overlay_probe).alpha() > 0
        assert chart._zoom_origin is not None
        assert selection_rect.width() >= 6.0
        assert selection_rect.height() >= 6.0
        image = QtGui.QImage(chart.size(), QtGui.QImage.Format.Format_ARGB32_Premultiplied)
        painter = QtGui.QPainter(image)
        chart.paint_to_painter(painter=painter, paint_lines=False)
        painter.end()
        assert not image.isNull()
        selection_probe: QtCore.QPoint = QtCore.QPoint(
            int(selection_rect.left() + selection_rect.width() * 0.35),
            int(selection_rect.top() + selection_rect.height() * 0.35),
        )
        assert image.pixelColor(selection_probe) != chart._plot_color
        chart.mouseReleaseEvent(make_mouse_event(
            event_type=QtCore.QEvent.Type.MouseButtonRelease,
            widget=chart,
            local_position=selection_end,
            button=QtCore.Qt.MouseButton.LeftButton,
            buttons=QtCore.Qt.MouseButton.NoButton,
        ))
        assert chart._rhi_selection_overlay.isHidden()
        assert chart._zoom_selection is None
        adjusted_plot: QtCore.QRectF = chart._get_plot_rect()
        assert np.isclose(adjusted_plot.width(), plot_rect.width())
        assert np.isclose(adjusted_plot.height(), plot_rect.height())
        assert np.isclose(
            chart.axis_x.get_zoom() * selection_rect.width() / plot_rect.width(),
            x_zoom_before_selection,
        )
        assert np.isclose(
            chart.axis_y.get_zoom() * selection_rect.height() / plot_rect.height(),
            y_zoom_before_selection,
        )
        chart.wheelEvent(make_wheel_event(widget=chart, delta_y=120))
        assert chart.axis_x.get_zoom() > 1.0
        assert chart.axis_y.get_zoom() > 1.0
        assert chart._prepare_rhi_line_layer(plot_rect=chart._get_plot_rect())
        assert chart._rhi_line_widget._data_revision > first_revision
        first_revision = chart._rhi_line_widget._data_revision
        chart.reset_viewport()
        plot_rect = chart._get_plot_rect()
        pan_start: QtCore.QPointF = QtCore.QPointF(
            plot_rect.left() + plot_rect.width() * 0.35,
            plot_rect.top() + plot_rect.height() * 0.4,
        )
        pan_end: QtCore.QPointF = QtCore.QPointF(
            pan_start.x() + float(random_generator.uniform(8.0, 48.0)),
            pan_start.y() + float(random_generator.uniform(-24.0, 24.0)),
        )
        chart.mousePressEvent(make_mouse_event(
            event_type=QtCore.QEvent.Type.MouseButtonPress,
            widget=chart,
            local_position=pan_start,
            button=QtCore.Qt.MouseButton.LeftButton,
            buttons=QtCore.Qt.MouseButton.LeftButton,
            modifiers=QtCore.Qt.KeyboardModifier.ControlModifier,
        ))
        chart.mouseMoveEvent(make_mouse_event(
            event_type=QtCore.QEvent.Type.MouseMove,
            widget=chart,
            local_position=pan_end,
            button=QtCore.Qt.MouseButton.NoButton,
            buttons=QtCore.Qt.MouseButton.LeftButton,
            modifiers=QtCore.Qt.KeyboardModifier.ControlModifier,
        ))
        chart.mouseReleaseEvent(make_mouse_event(
            event_type=QtCore.QEvent.Type.MouseButtonRelease,
            widget=chart,
            local_position=pan_end,
            button=QtCore.Qt.MouseButton.LeftButton,
            buttons=QtCore.Qt.MouseButton.NoButton,
            modifiers=QtCore.Qt.KeyboardModifier.ControlModifier,
        ))
        assert chart.axis_x.get_pan() != 0.0 or chart.axis_y.get_pan() != 0.0
        assert chart._prepare_rhi_line_layer(plot_rect=chart._get_plot_rect())
        assert chart._rhi_line_widget._data_revision > first_revision
        first_revision = chart._rhi_line_widget._data_revision
        image = QtGui.QImage(chart.size(), QtGui.QImage.Format.Format_ARGB32_Premultiplied)
        painter = QtGui.QPainter(image)
        chart.paint_to_painter(painter=painter, paint_lines=False)
        painter.end()
        assert not image.isNull()
        chart.reset_viewport()

    assert chart._prepare_rhi_line_layer(plot_rect=chart._get_plot_rect())
    chart.dispose()
    delete_chart_owner(owner=owner, chart=chart, probe=probe, app=qt_app)


def test_chart_colors_follow_application_palette_changes(qt_app: QtWidgets.QApplication) -> None:
    """Keep the painter theme aligned with Qt palette changes after construction.

    :param qt_app: Shared Qt application fixture.
    :return: None.
    """
    _ = qt_app
    chart: GraphsWidget = GraphsWidget()
    dark_palette: QtGui.QPalette = QtGui.QPalette(chart.palette())
    dark_palette.setColor(QtGui.QPalette.ColorRole.Window, QtGui.QColor("#202020"))
    chart.setPalette(dark_palette)
    assert chart._background_color == QtGui.QColor("#171c24")
    assert chart._plot_color == QtGui.QColor("#202834")
    assert chart._label_color == QtGui.QColor("#e7edf5")
    assert chart._grid_color == QtGui.QColor("#445164")

    light_palette: QtGui.QPalette = QtGui.QPalette(chart.palette())
    light_palette.setColor(QtGui.QPalette.ColorRole.Window, QtGui.QColor("#ffffff"))
    chart.setPalette(light_palette)
    assert chart._background_color == QtGui.QColor("#ffffff")
    assert chart._plot_color == QtGui.QColor("#f7fbff")
    assert chart._label_color == QtGui.QColor("#17324a")
    assert chart._grid_color == QtGui.QColor("#cbd5e1")

    chart.dispose()
    chart.deleteLater()
    QtWidgets.QApplication.sendPostedEvents(None)
