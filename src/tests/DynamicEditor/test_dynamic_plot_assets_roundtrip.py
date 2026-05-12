from __future__ import annotations

from pathlib import Path

import numpy as np
from PySide6 import QtCore

from VeraGrid.Gui.Main.SubClasses.Results.dynamics_results_handler import DynamicsResultsHandler, DynamicPlotCandidate
from VeraGridEngine.Devices.Events.rms_events_group import RmsEventsGroup
from VeraGridEngine.Devices.Events.dynamic_plot import DynamicPlot
from VeraGridEngine.Devices.Events.dynamic_plot_entry import DynamicPlotEntry
from VeraGridEngine.Devices.Injections.generator import Generator
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.IO.file_open import FileOpen
from VeraGridEngine.IO.file_save import FileSavingOptions, save_veragrid_circuit
from VeraGridEngine.Simulations.Rms.rms_results import RmsResults
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Var
from VeraGridEngine.enumerations import DeviceType, FileType, PlotSimulationType


def ensure_qt_application() -> QtCore.QCoreApplication:
    """
    Ensure a Qt core application exists for Qt model creation.

    :return: Existing or newly created Qt core application.
    """
    application: QtCore.QCoreApplication | None = QtCore.QCoreApplication.instance()
    if application is None:
        application = QtCore.QCoreApplication(list())
    else:
        pass
    return application


def build_pre_simulation_rms_circuit() -> MultiCircuit:
    """
    Build one minimal circuit with declarative RMS dynamic variables.

    :return: Circuit configured for the pre-simulation dynamic plot editor.
    """
    circuit: MultiCircuit = MultiCircuit(name="pre-sim-rms")
    generator: Generator = Generator(name="Generator A", idtag="gen-a")
    omega_var: Var = circuit.var_factory.add_var(name="omega", uid=1)
    efd_var: Var = circuit.var_factory.add_var(name="efd", uid=2)
    generator.rms_model = Block(
        state_vars=[omega_var],
        algebraic_vars=[efd_var],
    )
    circuit.set_elements_list_by_type(device_type=DeviceType.GeneratorDevice, devices=[generator])
    circuit.add_rms_events_group(obj=RmsEventsGroup(idtag="rms-group-a", name="RMS Group A"))
    return circuit


def build_rms_results_from_generator(generator: Generator,
                                     variable_name: str,
                                     variable_uid: int) -> RmsResults:
    """
    Build one minimal RMS results object for the given generator.

    :param generator: Generator that owns the result variable.
    :param variable_name: Result variable name.
    :param variable_uid: Result variable uid.
    :return: Minimal RMS results object.
    """
    variable: Var = Var(name=variable_name, uid=variable_uid)
    results: RmsResults = RmsResults(
        time_array=np.array([0.0, 1.0], dtype=float),
        rms_events_group_names=np.array(["RMS Group A"], dtype=str),
        rms_events_group_idtags=np.array(["rms-group-a"], dtype=str),
        variables=[variable],
        uid2idx={variable_uid: 0},
        vars_glob_name2uid={generator.idtag + ":" + variable_name + ":" + str(variable_uid): variable_uid},
        devices_vars_info={generator: [variable]},
    )
    results.values[:, :, 0] = np.array([[0.0], [1.0]], dtype=float)
    return results


def test_dynamic_plot_asset_roundtrip_preserves_semantic_fields(tmp_path: Path) -> None:
    """
    Verify that persistent dynamic plot assets survive a ``.veragrid`` roundtrip.

    :param tmp_path: Temporary directory provided by pytest.
    :return: None.
    """
    circuit: MultiCircuit = MultiCircuit(name="dynamic-plot-assets")
    plot_asset: DynamicPlot = DynamicPlot(name="Plot 1", simulation_type=PlotSimulationType.RMS)
    circuit.add_dynamic_plot(obj=plot_asset)

    curve_asset: DynamicPlotEntry = DynamicPlotEntry(
        variable=None,
        plot=plot_asset,
        group=None,
        device=None,
        simulation_type=PlotSimulationType.RMS,
        event_group_idtag="rms-group-a",
        event_group_name="RMS Group A",
        curve_device_type=DeviceType.LoadDevice,
        device_idtag="load-a",
        device_name_hint="Load A",
        variable_name="p_load",
        result_path_kind="values",
        curve_label="Load A - p_load - RMS Group A",
        enabled=True,
        runtime_series_key_payload="payload",
        name="Curve 1",
    )
    circuit.add_dynamic_plot_entry(obj=curve_asset)

    file_name: Path = tmp_path / "dynamic_plot_assets.veragrid"
    options: FileSavingOptions = FileSavingOptions(file_type=FileType.VeraGrid)
    save_veragrid_circuit(circuit=circuit, file_name=str(file_name), options=options)

    loader: FileOpen = FileOpen(file_name=str(file_name))
    loaded_circuit: MultiCircuit | None = loader.open()

    assert loaded_circuit is not None
    assert len(loaded_circuit.dynamic_plots) == 1
    assert len(loaded_circuit.dynamic_plot_entries) == 1

    loaded_plot: DynamicPlot = loaded_circuit.dynamic_plots[0]
    loaded_entry: DynamicPlotEntry = loaded_circuit.dynamic_plot_entries[0]

    assert loaded_plot.name == "Plot 1"
    assert loaded_plot.simulation_type == PlotSimulationType.RMS
    assert loaded_entry.plot is loaded_plot
    assert loaded_entry.variable is None
    assert loaded_entry.group is None
    assert loaded_entry.simulation_type == PlotSimulationType.RMS
    assert loaded_entry.event_group_idtag == "rms-group-a"
    assert loaded_entry.event_group_name == "RMS Group A"
    assert loaded_entry.curve_device_type == DeviceType.LoadDevice
    assert loaded_entry.device_idtag == "load-a"
    assert loaded_entry.device_name_hint == "Load A"
    assert loaded_entry.variable_name == "p_load"
    assert loaded_entry.result_path_kind == "values"
    assert loaded_entry.curve_label == "Load A - p_load - RMS Group A"
    assert loaded_entry.enabled is True
    assert loaded_entry.runtime_series_key_payload == "payload"


def test_pre_simulation_handler_creates_persistent_assets() -> None:
    """
    Verify that the pre-simulation handler writes plot definitions into circuit assets.

    :return: None.
    """
    ensure_qt_application()
    circuit: MultiCircuit = build_pre_simulation_rms_circuit()
    handler: DynamicsResultsHandler = DynamicsResultsHandler(results=None, circuit=circuit, simulation_type="RMS")

    created: bool = handler.create_plot_group(name="Plot 1")
    assert created is True

    first_candidate_list = handler.series_by_var_uid[1]
    first_candidate: DynamicPlotCandidate = first_candidate_list[0]
    inserted: bool = handler.add_candidate_to_group(group_name="Plot 1", candidate=first_candidate)

    assert inserted is True
    assert len(circuit.dynamic_plots) == 1
    assert len(circuit.dynamic_plot_entries) == 1
    assert circuit.dynamic_plots[0].simulation_type == PlotSimulationType.RMS
    assert circuit.dynamic_plot_entries[0].event_group_idtag == "rms-group-a"
    assert circuit.dynamic_plot_entries[0].device_idtag == "gen-a"
    assert circuit.dynamic_plot_entries[0].variable_name == "omega"


def test_pre_simulation_dynamic_plot_assets_survive_roundtrip_without_results(tmp_path: Path) -> None:
    """
    Verify that handler-created pre-simulation plot assets survive save/open.

    :param tmp_path: Temporary directory provided by pytest.
    :return: None.
    """
    ensure_qt_application()
    circuit: MultiCircuit = build_pre_simulation_rms_circuit()
    handler: DynamicsResultsHandler = DynamicsResultsHandler(results=None, circuit=circuit, simulation_type="RMS")
    assert handler.create_plot_group(name="Plot 1") is True

    first_candidate_list = handler.series_by_var_uid[1]
    first_candidate: DynamicPlotCandidate = first_candidate_list[0]
    assert handler.add_candidate_to_group(group_name="Plot 1", candidate=first_candidate) is True

    file_name: Path = tmp_path / "pre_simulation_dynamic_plot_assets.veragrid"
    options: FileSavingOptions = FileSavingOptions(file_type=FileType.VeraGrid)
    save_veragrid_circuit(circuit=circuit, file_name=str(file_name), options=options)

    loader: FileOpen = FileOpen(file_name=str(file_name))
    loaded_circuit: MultiCircuit | None = loader.open()

    assert loaded_circuit is not None
    assert len(loaded_circuit.dynamic_plots) == 1
    assert len(loaded_circuit.dynamic_plot_entries) == 1
    assert loaded_circuit.dynamic_plots[0].name == "Plot 1"
    assert loaded_circuit.dynamic_plots[0].simulation_type == PlotSimulationType.RMS
    assert loaded_circuit.dynamic_plot_entries[0].variable_name == "omega"
    assert loaded_circuit.dynamic_plot_entries[0].event_group_idtag == "rms-group-a"


def test_pre_simulation_created_asset_binds_after_results_exist() -> None:
    """
    Verify that a pre-simulation plot definition binds automatically after RMS results exist.

    :return: None.
    """
    ensure_qt_application()
    circuit: MultiCircuit = build_pre_simulation_rms_circuit()
    handler: DynamicsResultsHandler = DynamicsResultsHandler(results=None, circuit=circuit, simulation_type="RMS")
    assert handler.create_plot_group(name="Plot 1") is True

    first_candidate_list = handler.series_by_var_uid[1]
    first_candidate: DynamicPlotCandidate = first_candidate_list[0]
    assert handler.add_candidate_to_group(group_name="Plot 1", candidate=first_candidate) is True

    generator: Generator = circuit.get_elements_by_type(device_type=DeviceType.GeneratorDevice)[0]
    results: RmsResults = build_rms_results_from_generator(generator=generator, variable_name="omega", variable_uid=101)
    results_handler: DynamicsResultsHandler = DynamicsResultsHandler(results=results, circuit=circuit)

    group = results_handler.plot_groups.get_group(name="Plot 1")
    assert group is not None
    restored_entries = group.get_series()
    assert len(restored_entries) == 1
    assert results_handler.get_plots_model() is not None
    assert restored_entries[0].get_var().uid == 101
