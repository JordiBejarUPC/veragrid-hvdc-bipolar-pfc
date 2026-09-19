# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""Native graphic-device profile and result-plot integration coverage."""

from __future__ import annotations

import numpy as np
from PySide6 import QtCore, QtWidgets

from VeraGrid.Gui.Diagrams.base_diagram_widget import BaseDiagramWidget
from VeraGrid.Gui.PlotDialogue.plot_dialogue import PlotDialogue
from VeraGridEngine.enumerations import DeviceType, ResultTypes, StudyResultsType
from VeraGridEngine.Simulations.results_table import ResultsTable
from VeraGridEngine.Simulations.results_template import ResultsTemplate


class ProfileBuffer:
    """Keep one immutable numeric profile used by the graphic-plot test."""

    __slots__ = ("_values",)

    def __init__(self, values: np.ndarray) -> None:
        """Store one source profile buffer.

        :param values: Numeric values to copy into the native chart.
        :return: None.
        """
        self._values: np.ndarray = values

    def toarray(self) -> np.ndarray:
        """Return the source profile array expected by editable devices.

        :return: Source numeric profile values.
        """
        return self._values


class ProfileProperty:
    """Describe one profile-capable editable-device property."""

    __slots__ = ("name", "units", "_profile")

    def __init__(self, name: str, units: str, profile: ProfileBuffer) -> None:
        """Store one profile descriptor.

        :param name: Visible property name.
        :param units: Shared axis units.
        :param profile: Buffer exposed through the editable device.
        :return: None.
        """
        self.name: str = name
        self.units: str = units
        self._profile: ProfileBuffer = profile

    def has_profile(self) -> bool:
        """Report that this descriptor has a profile buffer.

        :return: ``True`` for the fixed test profile.
        """
        return True


class GraphicDevice:
    """Minimal device object accepted by the graphic plotting helpers."""

    __slots__ = ("name", "registered_properties")

    def __init__(self) -> None:
        """Create power and reactive-power profiles with separate units.

        :return: None.
        """
        active_power: ProfileProperty = ProfileProperty(
            name="P",
            units="MW",
            profile=ProfileBuffer(np.array((1.0, 2.0, 3.0), dtype=float)),
        )
        active_limit: ProfileProperty = ProfileProperty(
            name="Pmax",
            units="MW",
            profile=ProfileBuffer(np.array((4.0, 4.0, 4.0), dtype=float)),
        )
        reactive_power: ProfileProperty = ProfileProperty(
            name="Q",
            units="MVAr",
            profile=ProfileBuffer(np.array((0.5, 0.7, 0.9), dtype=float)),
        )
        self.name: str = "Generator A"
        self.registered_properties: dict[str, ProfileProperty] = dict(
            P=active_power,
            Pmax=active_limit,
            Q=reactive_power,
        )

    def get_profile_by_prop(self, prop: ProfileProperty) -> ProfileBuffer:
        """Return the fixed buffer associated with one property descriptor.

        :param prop: Descriptor selected by the graphic plotting helper.
        :return: Associated numeric profile buffer.
        """
        return prop._profile


class GraphicResults(ResultsTemplate):
    """Provide one time-series generator result table for the graphic test."""

    __slots__ = ("_table",)

    def __init__(self) -> None:
        """Create a results template with a single generator-power result.

        :return: None.
        """
        ResultsTemplate.__init__(
            self,
            name="Power flow",
            available_results=[ResultTypes.GeneratorPower],
            time_array=None,
            clustering_results=None,
            study_results_type=StudyResultsType.PowerFlowTimeSeries,
        )
        self._table: ResultsTable = ResultsTable(
            data=np.array(((2.0,), (2.5,), (3.5,)), dtype=float),
            columns=np.array(("Generator A",)),
            index=np.array(("2026-01-01", "2026-01-02", "2026-01-03"), dtype="datetime64[ns]"),
            title=ResultTypes.GeneratorPower.value,
            cols_device_type=DeviceType.GeneratorDevice,
            idx_device_type=DeviceType.TimeDevice,
            xlabel="Time",
            ylabel="MW",
        )

    def mdl(self, result_type: ResultTypes) -> ResultsTable:
        """Return the matching native result table.

        :param result_type: Requested result type.
        :return: Fixed generator-power table.
        """
        assert result_type == ResultTypes.GeneratorPower
        return self._table


class GraphicCircuit:
    """Resolve the one generator device in the same order as its result table."""

    __slots__ = ("_device",)

    def __init__(self, device: GraphicDevice) -> None:
        """Store the device used by result-column resolution.

        :param device: Generator represented by the graphic.
        :return: None.
        """
        self._device: GraphicDevice = device

    def get_elements_by_type(self, device_type: DeviceType) -> list[GraphicDevice]:
        """Return the test generator for generator result columns.

        :param device_type: Requested table device type.
        :return: Ordered generator device list.
        """
        assert device_type == DeviceType.GeneratorDevice
        return [self._device]


class GraphicSession:
    """Expose one result object through the GUI session iterator contract."""

    __slots__ = ("_results",)

    def __init__(self, results: GraphicResults) -> None:
        """Store the time-series result source.

        :param results: Native table provider.
        :return: None.
        """
        self._results: GraphicResults = results

    def drivers_results_iter(self) -> list[tuple[object, GraphicResults]]:
        """Return the single available result source.

        :return: Driver-result pairs consumed by diagram graphics.
        """
        return [(object(), self._results)]


class GraphicGui:
    """Hold the session attribute consumed by the diagram helper."""

    __slots__ = ("session",)

    def __init__(self, session: GraphicSession) -> None:
        """Store the result-bearing session.

        :param session: Session exposing driver results.
        :return: None.
        """
        self.session: GraphicSession = session


class GraphicPlotOwner:
    """Supply the two diagram attributes used by the private tab builders."""

    __slots__ = ("circuit", "gui")

    def __init__(self, circuit: GraphicCircuit, gui: GraphicGui) -> None:
        """Store the circuit and GUI session for an unbound helper call.

        :param circuit: Circuit used for result-column ordering.
        :param gui: GUI session owning the results.
        :return: None.
        """
        self.circuit: GraphicCircuit = circuit
        self.gui: GraphicGui = gui

    def tr(self, text: str) -> str:
        """Return the untranslated test string used by the chart helper.

        :param text: Source string requested by the diagram helper.
        :return: Untranslated test string.
        """
        return text


def test_graphic_device_tabs_group_profiles_and_attach_result_columns(
        qt_app: QtWidgets.QApplication) -> None:
    """Verify graphic-device tabs retain grouped profiles and mapped result buffers.

    :param qt_app: Shared Qt application fixture.
    :return: None.
    """
    owner: QtWidgets.QDialog = QtWidgets.QDialog()
    device: GraphicDevice = GraphicDevice()
    results: GraphicResults = GraphicResults()
    circuit: GraphicCircuit = GraphicCircuit(device=device)
    gui: GraphicGui = GraphicGui(session=GraphicSession(results=results))
    diagram: GraphicPlotOwner = GraphicPlotOwner(circuit=circuit, gui=gui)
    plot_dialogue: PlotDialogue = PlotDialogue(title="Device plot", parent=owner)
    time_values: np.ndarray = np.array(("2026-01-01", "2026-01-02", "2026-01-03"), dtype="datetime64[ns]")

    profiles_added: bool = BaseDiagramWidget._add_device_profile_tabs(
        diagram,
        plot_dialogue=plot_dialogue,
        api_object=device,
        time_values=time_values,
        has_existing_tabs=False,
    )
    assert profiles_added
    assert len(plot_dialogue._tab_charts) == 2
    assert len(plot_dialogue._tab_charts[0]._series) == 2
    assert len(plot_dialogue._tab_charts[1]._series) == 1

    results_added: bool = BaseDiagramWidget._add_device_result_tabs(
        diagram,
        plot_dialogue=plot_dialogue,
        api_object=device,
        has_existing_tabs=profiles_added,
    )
    assert results_added
    assert len(plot_dialogue._tab_charts) == 3
    result_chart = plot_dialogue._tab_charts[2]
    assert len(result_chart._series) == 1
    assert np.array_equal(result_chart._series[0].get_y_data(), np.array((2.0, 2.5, 3.5)))

    plot_dialogue.reject()
    owner.deleteLater()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)
    qt_app.processEvents()
