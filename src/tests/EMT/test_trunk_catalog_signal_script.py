from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
else:
    pass

from trunk.dynamics_emt.scripting_catalog_signal_blocks_emt import run_lookup_table_case
from trunk.dynamics_emt.scripting_catalog_signal_blocks_emt import run_triangle_pulse_case


def test_trunk_catalog_signal_blocks_script_runs_without_plots() -> None:
    lookup_traces = run_lookup_table_case(enable_plots=False)
    triangle_traces = run_triangle_pulse_case(enable_plots=False)

    assert len(lookup_traces["time"]) > 100
    assert len(triangle_traces["time"]) > 100
