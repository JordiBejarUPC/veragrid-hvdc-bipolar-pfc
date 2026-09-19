from __future__ import annotations

from pathlib import Path

import numpy as np
from PySide6 import QtCore, QtWidgets

from VeraGrid.Gui.PlotDialogue.plot_dialogue import PlotDialogue
from VeraGrid.Gui.Widgets.qt_chart_widget import ChartContentType, PolarAngleUnit


def close_plot_dialogue(dialog: PlotDialogue, app: QtWidgets.QApplication) -> None:
    """Close one plot dialog through its real Qt ownership lifecycle.

    :param dialog: Dialog whose chart buffers must be released before deletion.
    :param app: Application processing the deferred native deletion event.
    :return: None.
    """
    dialog.reject()
    assert dialog.chart._disposed
    dialog.deleteLater()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)
    app.processEvents()


def test_plot_dialogue_time_area_polar_export_and_lifecycle(
        qt_app: QtWidgets.QApplication,
        tmp_path: Path) -> None:
    """Exercise every native plot mode through repeated open and close cycles.

    :param qt_app: Shared Qt application fixture.
    :param tmp_path: Temporary output folder provided by pytest.
    :return: None.
    """
    app: QtWidgets.QApplication = qt_app
    cycle_index: int
    for cycle_index in range(8):
        dialog: PlotDialogue = PlotDialogue(title=f'Chart cycle {cycle_index}')
        dialog.resize(900, 620)
        dialog.show()
        app.processEvents()

        time_values: np.ndarray = np.array(
            ('2026-01-01T00:00', '2026-01-01T01:00', '2026-01-01T02:00', '2026-01-01T03:00'),
            dtype='datetime64[m]',
        )
        assert dialog.set_time_series(
            time_values=time_values,
            series_names=('Active power', 'Reactive power'),
            series_values=(np.array((1.0, 2.0, 3.0, 2.0)), np.array((0.2, 0.4, 0.6, 0.4))),
            colors=('#2563eb', '#f97316'),
            title='Time plot',
            y_axis_title='MW',
        )
        assert dialog.chart._x_is_datetime
        dialog.chart.axis_x.set_zoom(4.0)
        dialog.chart.axis_y.set_zoom(4.0)
        dialog.ui.actionResetView.trigger()
        assert dialog.chart.axis_x.get_zoom() == 1.0
        assert dialog.chart.axis_y.get_zoom() == 1.0

        assert dialog.set_cumulative_area_series(
            x_values=time_values,
            series_names=('Wind', 'Solar'),
            series_values=(np.array((1.0, 1.5, 1.1, 0.9)), np.array((0.5, 0.7, 1.2, 0.6))),
            colors=('#2563eb', '#f97316'),
            title='Cumulative generation',
            x_axis_title='Time',
            y_axis_title='MW',
        )
        assert dialog.chart._content_type == ChartContentType.CUMULATIVE_AREA
        dialog.repaint()
        app.processEvents()

        assert dialog.set_polar_series(
            series_names=('Impedance',),
            angle_values=(np.array((0.0, 90.0, 180.0, 270.0, 360.0)),),
            radius_values=(np.array((1.0, 0.8, 1.2, 0.9, 1.0)),),
            colors=('#7c3aed',),
            title='Polar plot',
            radius_title='Per unit',
            angle_unit=PolarAngleUnit.DEGREES,
        )
        assert dialog.chart._content_type == ChartContentType.POLAR
        dialog.repaint()
        app.processEvents()

        png_path: Path = tmp_path / f'plot-{cycle_index}.png'
        svg_path: Path = tmp_path / f'plot-{cycle_index}.svg'
        assert dialog.save_image_to_file(file_name=str(png_path))
        assert dialog.save_image_to_file(file_name=str(svg_path))
        assert png_path.stat().st_size > 0
        assert svg_path.stat().st_size > 0
        assert '<svg' in svg_path.read_text(encoding='utf-8')

        close_plot_dialogue(dialog=dialog, app=app)
