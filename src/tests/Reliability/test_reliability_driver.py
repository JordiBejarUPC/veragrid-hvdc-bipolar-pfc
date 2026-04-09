# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import numpy as np
import pytest
from types import SimpleNamespace

from VeraGridEngine.enumerations import ResultTypes
from VeraGridEngine.Simulations.Reliability import reliability_driver as reliability_driver_module
from VeraGridEngine.Simulations.Reliability.reliability_driver import ReliabilityStudyDriver, count_device_incidences
from VeraGridEngine.Simulations.Reliability.reliability_results import ReliabilityResults


@pytest.mark.parametrize(
    "active_states, expected",
    [
        (
            np.array(
                [
                    [True, True, True],
                    [True, True, True],
                    [True, True, True],
                ],
                dtype=bool,
            ),
            0,
        ),
        (
            np.array(
                [
                    [False, True, False],
                    [False, True, True],
                    [True, True, True],
                ],
                dtype=bool,
            ),
            2,
        ),
        (
            np.array(
                [
                    [True, True],
                    [False, True],
                    [False, False],
                    [True, False],
                    [False, True],
                ],
                dtype=bool,
            ),
            4,
        ),
    ],
)
def test_count_device_incidences(active_states: np.ndarray, expected: int) -> None:
    assert count_device_incidences(active_states) == expected


class FakeLoad:
    def __init__(self, n_customers: int):
        self.n_customers = n_customers


class FakeLoadData:
    def __init__(self, original_idx: np.ndarray, bus_idx: np.ndarray, S: np.ndarray, nbus: int):
        self.original_idx = original_idx
        self.bus_idx = bus_idx
        self.S = S
        self.nbus = nbus

    def get_array_per_bus(self, arr: np.ndarray) -> np.ndarray:
        res = np.zeros(self.nbus, dtype=float)
        for load_idx, bus_idx in enumerate(self.bus_idx):
            res[bus_idx] += arr[load_idx]
        return res


class FakeIsland:
    def __init__(self,
                 bus_indices: list[int],
                 has_generation: bool,
                 load_power: list[complex],
                 battery_active: bool = False,
                 battery_original_idx: list[int] | None = None):
        self.bus_data = SimpleNamespace(original_idx=np.array(bus_indices, dtype=int))
        self.generator_data = SimpleNamespace(active=np.array([has_generation], dtype=bool) if has_generation else
                                              np.zeros(0, dtype=bool))
        self.battery_data = SimpleNamespace(active=np.array([battery_active], dtype=bool) if battery_active else
                                            np.zeros(0, dtype=bool),
                                            original_idx=np.array(battery_original_idx or [], dtype=int))
        self.load_data = SimpleNamespace(S=np.array(load_power, dtype=complex))


class FakeNC:
    def __init__(self):
        self.nbus = 2
        self.generator_data = SimpleNamespace(mttf=np.array([10.0]), mttr=np.array([1.0]), active=np.array([True]))
        self.battery_data = SimpleNamespace(mttf=np.array([10.0]), mttr=np.array([1.0]),
                                            active=np.array([False]), enom=np.array([0.0]))
        self.passive_branch_data = SimpleNamespace(mttf=np.array([10.0]), mttr=np.array([1.0]),
                                                   active=np.array([True]))
        self.load_data = FakeLoadData(original_idx=np.array([0, 1], dtype=int),
                                      bus_idx=np.array([1, 1], dtype=int),
                                      S=np.array([1.0 + 0.0j, 2.0 + 0.0j]),
                                      nbus=self.nbus)

    def copy(self) -> "FakeNC":
        nc = FakeNC()
        nc.generator_data.active = self.generator_data.active.copy()
        nc.battery_data.active = self.battery_data.active.copy()
        nc.passive_branch_data.active = self.passive_branch_data.active.copy()
        return nc

    def split_into_islands(self, ignore_single_node_islands: bool = False) -> list[FakeIsland]:
        if self.passive_branch_data.active[0]:
            return [FakeIsland(bus_indices=[0, 1], has_generation=True, load_power=[1.0 + 0.0j, 2.0 + 0.0j])]

        return [
            FakeIsland(bus_indices=[0], has_generation=True, load_power=[]),
            FakeIsland(bus_indices=[1], has_generation=False, load_power=[1.0 + 0.0j, 2.0 + 0.0j]),
        ]


class FakeGrid:
    def __init__(self):
        self.loads = [FakeLoad(3), FakeLoad(7)]

    def get_time_number(self) -> int:
        return 3


def test_run_grid_reliability_computes_customer_metrics(monkeypatch: pytest.MonkeyPatch) -> None:
    grid = FakeGrid()
    nc = FakeNC()

    state_sequence = iter([
        (np.ones((3, 1), dtype=bool), 0),
        (np.ones((3, 1), dtype=bool), 0),
        (np.array([[False], [False], [True]], dtype=bool), 1),
    ])

    monkeypatch.setattr(reliability_driver_module, "compile_numerical_circuit_at", lambda _: nc)
    monkeypatch.setattr(reliability_driver_module, "generate_states_matrix", lambda **_: next(state_sequence))

    driver = ReliabilityStudyDriver.__new__(ReliabilityStudyDriver)
    driver.grid = grid
    driver.n_sim = 1
    driver.results = ReliabilityResults(nsim=1)
    driver.greedy_dispatch_inputs = SimpleNamespace(dt=np.array([1.0, 1.0, 1.0]))
    driver.report_progress2 = lambda current, total: None
    driver._ReliabilityStudyDriver__cancel__ = False

    driver.run_grid_reliability()

    assert driver.results.LOLE_evolution[0] == pytest.approx(2.0)
    assert driver.results.ENS_evolution[0] == pytest.approx(6.0)
    assert driver.results.LOLF_evolution[0] == pytest.approx(1.0)
    assert driver.results.LOLET_evolution[0] == pytest.approx(2.0)
    assert driver.results.LOLFT_evolution[0] == pytest.approx(1.0)
    assert driver.results.SAIDI_evolution[0] == pytest.approx(2.0)
    assert driver.results.SAIFI_evolution[0] == pytest.approx(1.0)
    assert driver.results.CAIDI_evolution[0] == pytest.approx(2.0)

    assert driver.results.mdl(ResultTypes.ReliabilitySAIDIResults).data[0] == pytest.approx(2.0)
    assert driver.results.mdl(ResultTypes.ReliabilitySAIFIResults).data[0] == pytest.approx(1.0)
    assert driver.results.mdl(ResultTypes.ReliabilityCAIDIResults).data[0] == pytest.approx(2.0)
