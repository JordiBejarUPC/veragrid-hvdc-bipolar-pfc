# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""
Regression tests for the Power Flow Controller (PFC) in bipolar MT-HVDC grids.

Each test runs one of the paper case studies in ``src/trunk/Paper_CaseStudies``
and compares the power flow results against reference values produced with the
code published with the paper (branch ``paper-release`` v1.0.0).

They are meant to be run after every integration of upstream (eRoots) code:

    python -m pytest tests/PowerFlow/test_pfc_bipolar.py -v

To regenerate the reference file (only when a change of results is intended):

    python tests/PowerFlow/test_pfc_bipolar.py --regenerate
"""
from __future__ import annotations

import builtins
import contextlib
import io
import json
import runpy
import shutil
import sys
from pathlib import Path
from typing import Any, Dict

import numpy as np
import pytest

CASES_DIR: Path = Path(__file__).resolve().parents[2] / "trunk" / "Paper_CaseStudies"
REFERENCE_FILE: Path = Path(__file__).resolve().parents[1] / "data" / "pfc_bipolar_reference.json"

CASES: Dict[str, str] = {
    "case1_bipolar_no_pfc": "CaseStudy1_Bipolar.py",
    "case2_bipolar_with_pfc": "CaseStudy2_Bipolar_WithPfc.py",
    "case3_4terminal_with_pfc": "CaseStudy3_4TerminalBipolarSystem.py",
    "case3_4terminal_no_pfc": "CaseStudy3_4TerminalBipolarSystem_NOPFC.py",
}

# results attributes compared against the reference
FIELDS = ("voltage", "Sf", "St", "Pfp_vsc", "Pfn_vsc", "St_vsc", "losses_vsc",
          "Iq_pfc", "Ir_pfc", "Is_pfc", "Pq_pfc", "Pr_pfc", "Ps_pfc", "Vr_pfc", "Vs_pfc",
          "KCL_pfc", "PB_pfc", "P_Vr_pfc", "P_Vs_pfc", "Vqr_pfc", "Vqs_pfc")

RTOL = 1e-6
ATOL = 1e-8


def run_case(script: str, workdir: Path) -> Dict[str, Any]:
    """
    Run a paper case study script in an isolated copy of the case-studies folder
    (so the files the scripts export do not pollute the repository), answering
    the interactive prompts with the defaults (Enter).
    :param script: script file name
    :param workdir: folder where the case studies are copied
    :return: globals of the executed script (contains ``grid`` and ``results``)
    """
    shutil.copy(CASES_DIR / script, workdir / script)
    if not (workdir / "grids").exists():
        shutil.copytree(CASES_DIR / "grids", workdir / "grids")

    original_input = builtins.input
    builtins.input = lambda *args, **kwargs: ""
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            return runpy.run_path(str(workdir / script), run_name="__main__")
    finally:
        builtins.input = original_input


def extract(results) -> Dict[str, Any]:
    """
    Get the compared magnitudes as JSON-serializable data
    :param results: PowerFlowResults
    :return: dictionary {field: {"re": [...], "im": [...]}}
    """
    data: Dict[str, Any] = {"converged": bool(results.converged)}
    for field in FIELDS:
        arr = np.asarray(getattr(results, field), dtype=complex).ravel()
        data[field] = {"re": arr.real.tolist(), "im": arr.imag.tolist()}
    return data


@pytest.fixture(scope="module")
def reference() -> Dict[str, Any]:
    with open(REFERENCE_FILE, encoding="utf-8") as f:
        return json.load(f)


@pytest.mark.parametrize("case_name", list(CASES.keys()))
def test_pfc_case_study_matches_paper(case_name: str, reference: Dict[str, Any], tmp_path: Path) -> None:
    """
    The paper case studies must converge and reproduce the published results
    """
    ns = run_case(CASES[case_name], tmp_path)
    results = ns["results"]
    ref = reference[case_name]

    assert results.converged, f"{case_name} did not converge (error={results.error})"

    current = extract(results)
    for field in FIELDS:
        expected = np.array(ref[field]["re"]) + 1j * np.array(ref[field]["im"])
        actual = np.array(current[field]["re"]) + 1j * np.array(current[field]["im"])
        assert actual.shape == expected.shape, f"{case_name}.{field}: shape {actual.shape} != {expected.shape}"
        assert np.allclose(actual, expected, rtol=RTOL, atol=ATOL), (
            f"{case_name}.{field}: max |diff| = {np.max(np.abs(actual - expected)):.3e}"
        )


def test_pfc_tracks_current_setpoint(tmp_path: Path) -> None:
    """
    Case 2: both PFCs control Is, so the solved Is must equal the setpoint
    and the PFC must satisfy its internal power balance and KCL.
    """
    ns = run_case(CASES["case2_bipolar_with_pfc"], tmp_path)
    results = ns["results"]
    is_set = ns["Is_set_pu"]

    assert results.converged
    assert np.allclose(results.Is_pfc, [is_set, -is_set], atol=1e-6)
    assert np.allclose(results.PB_pfc, 0.0, atol=1e-6)
    assert np.allclose(results.KCL_pfc, 0.0, atol=1e-6)


def test_pfc_does_not_affect_grids_without_pfc(tmp_path: Path) -> None:
    """
    Grids without PFC must still be solvable and return empty PFC results
    """
    ns = run_case(CASES["case1_bipolar_no_pfc"], tmp_path)
    results = ns["results"]
    assert results.converged
    assert len(results.Is_pfc) == 0


def regenerate() -> None:
    """
    Regenerate the reference file from the current code
    """
    import tempfile
    data: Dict[str, Any] = {}
    with tempfile.TemporaryDirectory() as tmp:
        for name, script in CASES.items():
            data[name] = extract(run_case(script, Path(tmp))["results"])
            print(name, "converged:", data[name]["converged"])
    REFERENCE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(REFERENCE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1)
    print("Reference written to", REFERENCE_FILE)


if __name__ == "__main__":
    if "--regenerate" in sys.argv:
        regenerate()
    else:
        print(__doc__)
