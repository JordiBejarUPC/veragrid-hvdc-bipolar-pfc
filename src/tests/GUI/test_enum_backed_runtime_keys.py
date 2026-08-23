from __future__ import annotations

from VeraGrid.Session.session import SimulationSession
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Simulations.driver_template import DriverTemplate
from VeraGridEngine.Simulations.results_template import ResultsTemplate
from VeraGridEngine.enumerations import DeviceType, ResultTypes, SimulationTypes, StudyResultsType


class RuntimeKeysDriver(DriverTemplate):
    """
    Minimal driver used to verify typed session lookup.
    """

    __slots__ = tuple()

    name = "Runtime keys driver"
    tpe = SimulationTypes.PowerFlow_run

    def __init__(self, grid: MultiCircuit) -> None:
        """
        Initialize the test driver.

        :param grid: Test circuit.
        :return: None.
        """
        DriverTemplate.__init__(self, grid=grid)

    def run(self) -> None:
        """
        Run no simulation because only session lookup is under test.

        :return: None.
        """
        return None


def test_multicircuit_runtime_device_keys_are_enums() -> None:
    """
    Verify runtime device metadata is keyed by DeviceType instead of display strings.

    :return: None.
    """
    circuit: MultiCircuit = MultiCircuit()

    assert DeviceType.BusDevice in circuit.device_type_name_dict
    assert DeviceType.BusDevice in circuit.device_associations
    assert DeviceType.BusDevice in circuit.profile_magnitudes
    assert DeviceType.BusDevice.value not in circuit.device_type_name_dict


def test_results_template_runtime_result_keys_are_enums() -> None:
    """
    Verify result metadata can be consumed without display strings.

    :return: None.
    """
    results: ResultsTemplate = ResultsTemplate(
        name="runtime result keys",
        available_results={ResultTypes.BusResults: [ResultTypes.BusVoltageModule]},
        time_array=None,
        clustering_results=None,
        study_results_type=StudyResultsType.PowerFlow,
    )

    results_tree: object = results.get_results_type_tree()
    results_dict: dict[ResultTypes, ResultTypes] = results.get_results_type_dict()

    assert results_tree == {ResultTypes.BusResults: [ResultTypes.BusVoltageModule]}
    assert results_dict[ResultTypes.BusVoltageModule] == ResultTypes.BusVoltageModule
    assert ResultTypes.BusVoltageModule.value not in results_dict


def test_session_keeps_typed_driver_lookup_and_legacy_name_lookup() -> None:
    """
    Verify typed session lookup works while legacy name lookup remains available.

    :return: None.
    """
    session: SimulationSession = SimulationSession()
    driver: RuntimeKeysDriver = RuntimeKeysDriver(grid=MultiCircuit())
    session.drivers[driver.tpe] = driver

    assert session.get_driver(driver_type=SimulationTypes.PowerFlow_run) is driver
    assert session.get_driver_by_name(study_name=SimulationTypes.PowerFlow_run.value) is driver
