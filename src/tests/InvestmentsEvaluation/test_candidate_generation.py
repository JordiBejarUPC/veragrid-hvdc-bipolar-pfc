# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import os

import VeraGridEngine.api as gce
import VeraGridEngine.Devices as dev
from VeraGridEngine.basic_structures import Logger
from VeraGridEngine.Simulations.InvestmentsEvaluation.CandidateGeneration.candidate_generation_driver import (
    CandidateGenerationDriver,
)
from VeraGridEngine.Simulations.InvestmentsEvaluation.CandidateGeneration.candidate_generation_options import (
    CandidateGenerationOptions,
)
from VeraGridEngine.Simulations.InvestmentsEvaluation.CandidateGeneration.candidate_generation_results import (
    NEW_LINE, UPGRADE,
)


def _stressed_ieee14():
    """
    Load IEEE 14 and tighten the line ratings so that single-branch outages overload other
    branches, giving the candidate generator something to work on.
    """
    fname = os.path.join('data', 'grids', 'IEEE 14 zip costs.gridcal')
    grid = gce.FileOpen(fname).open()
    for ln in grid.get_lines():
        ln.rate = ln.rate * 0.5
    return grid


def test_candidate_generation_pipeline():
    """
    End-to-end check of the candidate-investment generator pipeline: base case, N-1 screening,
    ranked candidates of both kinds, verification, and investment materialisation.
    """
    grid = _stressed_ieee14()

    drv = CandidateGenerationDriver(
        grid=grid,
        options=CandidateGenerationOptions(top_n_corridors=3, verify_top_k=1),
    )
    drv.run()
    results = drv.results

    # --- Step 1: base case ran and converged ---
    assert results.base_case_converged is True
    assert len(results.base_loading_report) > 0

    # --- Step 2: N-1 screening flagged overloads in the requested textual form ---
    assert len(results.n1_violations) > 0
    sample = results.n1_violations[0].describe()
    assert sample.startswith("outage ")
    assert "overloaded" in sample

    # --- Steps 3-4: ranked candidates of both kinds ---
    assert len(results.candidates) > 0
    kinds = {c.kind for c in results.candidates}
    assert NEW_LINE in kinds
    assert UPGRADE in kinds

    # Ranking is by descending relief score.
    scores = [c.score for c in results.candidates]
    assert scores == sorted(scores, reverse=True)
    assert scores[0] > 0.0

    # Every candidate is annotated with at least one violation it relieves.
    for c in results.candidates:
        assert len(c.relieved_violations) > 0

    # --- Step 5: verification produced a report for the top candidate ---
    assert len(results.verification_report) == 1
    assert "resolved" in results.verification_report[0]

    # Summary text carries the pipeline sections.
    summary = results.summary_text()
    assert "Base case AC power flow" in summary
    assert "N-1 screening" in summary
    assert "Ranked candidates" in summary


def test_candidate_apply_creates_investments():
    """
    Applying candidates materialises investments: a new-line candidate adds a Line and an
    investment pointing at it; an upgrade candidate adds an investment that encodes the rating
    change via prop/value without touching the base grid.
    """
    grid = _stressed_ieee14()
    drv = CandidateGenerationDriver(grid=grid, options=CandidateGenerationOptions(verify_top_k=0))
    drv.run()

    new_line_cand = next(c for c in drv.results.candidates if c.kind == NEW_LINE)
    upgrade_cand = next(c for c in drv.results.candidates if c.kind == UPGRADE)

    group = dev.InvestmentsGroup(idtag=None, name="test", category="multiple")
    grid.add_investments_group(group)
    logger = Logger()

    n_lines_before = len(grid.get_lines())
    n_inv_before = len(grid.investments)

    # New-line candidate: adds a Line and an investment pointing at it.
    created = new_line_cand.apply(circuit=grid, group=group, logger=logger)
    assert isinstance(created, dev.Line)
    assert len(grid.get_lines()) == n_lines_before + 1
    assert len(grid.investments) == n_inv_before + 1
    assert grid.investments[-1].device is created

    # Upgrade candidate: adds an investment encoding the rate change; no new device, base grid
    # rating unchanged.
    old_rate = upgrade_cand.target_branch.rate
    ret = upgrade_cand.apply(circuit=grid, group=group, logger=logger)
    assert ret is None
    up_inv = grid.investments[-1]
    assert up_inv.prop == "rate"
    assert up_inv.value == upgrade_cand.new_rate
    assert up_inv.value > old_rate
    # The base grid rating is untouched until the investment is applied.
    assert upgrade_cand.target_branch.rate == old_rate


def test_no_violations_no_candidates():
    """
    With generous ratings there are no violations and therefore no candidates, but the base case
    still runs and is reported feasible.
    """
    fname = os.path.join('data', 'grids', 'IEEE 14 zip costs.gridcal')
    grid = gce.FileOpen(fname).open()
    for ln in grid.get_lines():
        ln.rate = 100000.0
    for tr in grid.get_transformers2w():
        tr.rate = 100000.0

    drv = CandidateGenerationDriver(grid=grid)
    drv.run()
    results = drv.results

    assert results.base_case_converged is True
    assert results.base_case_feasible is True
    assert len(results.violations) == 0
    assert len(results.candidates) == 0
