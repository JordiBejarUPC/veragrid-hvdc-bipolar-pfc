from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
else:
    pass

from VeraGridEngine.enumerations import DynamicEventTransitionType
from trunk.dynamics_emt.scripting_emt_ramp_event import build_ramp_event_demo_problem
from trunk.dynamics_emt.scripting_emt_ramp_event import run_ramp_event_case


def test_ramp_event_demo_problem_uses_ramp_transition() -> None:
    problem, event_group, _parameter = build_ramp_event_demo_problem()
    matching_events = [evt for evt in problem.grid.emt_events if evt.group is event_group]

    assert len(matching_events) == 1
    assert matching_events[0].transition_type == DynamicEventTransitionType.Ramp
    assert matching_events[0].end_time == 0.5


def test_ramp_event_case_runs_and_ramps_runtime_parameter() -> None:
    traces = run_ramp_event_case(enable_plots=False)
    time_values = traces["time"]
    ramp_values = traces["u_input"]

    idx_before = int(np.searchsorted(time_values, 0.15))
    idx_mid = int(np.searchsorted(time_values, 0.35))
    idx_after = int(np.searchsorted(time_values, 0.7))

    assert float(ramp_values[idx_before]) < 0.05
    assert 0.45 < float(ramp_values[idx_mid]) < 0.55
    assert float(ramp_values[idx_after]) > 0.95
    assert float(np.max(traces["x_state"])) > 0.5
