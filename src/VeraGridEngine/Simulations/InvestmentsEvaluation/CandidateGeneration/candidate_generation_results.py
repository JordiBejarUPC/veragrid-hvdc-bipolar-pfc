# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations
from typing import List, Optional, TYPE_CHECKING

import VeraGridEngine.Devices as dev
from VeraGridEngine.basic_structures import Logger

if TYPE_CHECKING:
    from VeraGridEngine.Devices.multi_circuit import MultiCircuit


# Candidate kinds
NEW_LINE = "New line"
UPGRADE = "Upgrade"


class ViolationRecord:
    """
    A single overloaded branch, either in the base case or under a branch outage.
    """

    def __init__(self,
                 monitored_idx: int,
                 monitored_name: str,
                 flow: float,
                 limit: float,
                 outage_idx: int = -1,
                 outage_name: str = ""):
        """
        :param monitored_idx: Branch index (compiled order) of the overloaded branch.
        :param monitored_name: Name of the overloaded branch.
        :param flow: Signed active-power flow on the monitored branch (MW).
        :param limit: Rating the flow is compared against (MW).
        :param outage_idx: Branch index of the outaged branch, or -1 for a base-case violation.
        :param outage_name: Name of the outaged branch ("" for base case).
        """
        self.monitored_idx = monitored_idx
        self.monitored_name = monitored_name
        self.flow = flow
        self.limit = limit
        self.outage_idx = outage_idx
        self.outage_name = outage_name

    @property
    def is_base_case(self) -> bool:
        """Whether this is a base-case (N) violation rather than an N-1 one."""
        return self.outage_idx < 0

    @property
    def loading(self) -> float:
        """Loading fraction (|flow| / limit)."""
        return abs(self.flow) / (self.limit + 1e-9)

    @property
    def excess(self) -> float:
        """MW by which |flow| exceeds the limit (>= 0)."""
        return max(abs(self.flow) - self.limit, 0.0)

    def describe(self) -> str:
        """One-line description in the requested 'outage X -> branch Y overloaded (Z%)' form."""
        pct = self.loading * 100.0
        if self.is_base_case:
            return f"base case -> branch {self.monitored_name} overloaded ({pct:.1f}%)"
        return f"outage {self.outage_name} -> branch {self.monitored_name} overloaded ({pct:.1f}%)"


class ReinforcementCandidate:
    """
    A candidate reinforcement: either a new line on a corridor, or a rating upgrade of an
    existing branch. Carries enough to be scored, annotated with the violations it relieves,
    and materialised as an ``Investment``.
    """

    def __init__(self, kind: str):
        """
        :param kind: ``NEW_LINE`` or ``UPGRADE``.
        """
        self.kind: str = kind

        # New-line fields
        self.bus_from: Optional[dev.Bus] = None
        self.bus_to: Optional[dev.Bus] = None
        self.bus_from_idx: int = -1
        self.bus_to_idx: int = -1
        self.r: float = 0.0
        self.x: float = 1e-5
        self.b: float = 0.0
        self.rate: float = 0.0
        self.name: str = ""

        # Upgrade fields
        self.target_branch: Optional[dev.EditableDevice] = None
        self.branch_idx: int = -1
        self.old_rate: float = 0.0
        self.new_rate: float = 0.0

        # Scoring / annotation
        self.relieved_violations: List[ViolationRecord] = list()
        self.score: float = 0.0
        self.capex: float = 0.0

        # Verification outcome (populated only for the top-k candidates that are verified in step 5)
        self.verified: bool = False
        self.verification_converged: bool = False
        self.n_targeted: int = 0
        self.n_resolved: int = 0
        self.n_new_violations: int = 0

    @property
    def verified_ok(self) -> bool:
        """
        Whether this candidate was verified with a converged AC power flow and introduced no new
        violations. This is the gate for displaying a candidate in the GUI shortlist.
        """
        return self.verified and self.verification_converged and self.n_new_violations == 0

    def group_name(self) -> str:
        """Name of the investments group this candidate goes into: the asset it represents."""
        if self.kind == NEW_LINE:
            return f"New line {self.bus_from.name} - {self.bus_to.name}"
        return f"Upgrade {self.target_branch.name} rate {self.new_rate:.0f}"

    def label(self) -> str:
        """Human-readable one-line label for the candidate list in the GUI."""
        n = len(self.relieved_violations)
        if self.kind == NEW_LINE:
            what = f"New line {self.bus_from.name} - {self.bus_to.name} (rate {self.rate:.0f} MVA)"
        else:
            what = f"Upgrade {self.target_branch.name} rate {self.old_rate:.0f} -> {self.new_rate:.0f} MVA"
        return f"{what} | relieves {n} violation(s) | score {self.score:.1f} MW"

    def apply(self, circuit: "MultiCircuit", group: dev.InvestmentsGroup, logger: Logger) -> Optional[dev.Line]:
        """
        Materialise this candidate on the given circuit as an ``Investment`` belonging to ``group``.

        For a new-line candidate a new ``Line`` device is added to the circuit and the investment
        points at it. For an upgrade the investment points at the existing branch and encodes the
        rating change through the ``prop``/``value`` mechanism, so the base grid is left untouched
        until the investment is applied.

        :param circuit: The circuit to add to (the same one the generator ran on).
        :param group: The investments group to attach to.
        :param logger: Logger for messages.
        :return: The newly created ``Line`` (for drawing), or ``None`` for an upgrade.
        """
        if self.kind == NEW_LINE:
            line = dev.Line(bus_from=self.bus_from,
                            bus_to=self.bus_to,
                            name=self.name,
                            r=self.r,
                            x=self.x,
                            b=self.b,
                            rate=self.rate)
            circuit.add_line(line)
            circuit.add_investment(dev.Investment(device=line,
                                                  code=line.code,
                                                  name="New line: " + line.name,
                                                  CAPEX=self.capex,
                                                  group=group))
            return line
        else:
            # Upgrade: point at the existing branch and set its rate to the new value.
            circuit.add_investment(dev.Investment(device=self.target_branch,
                                                  code=self.target_branch.code,
                                                  name="Upgrade: " + self.target_branch.name,
                                                  CAPEX=self.capex,
                                                  prop="rate",
                                                  value=self.new_rate,
                                                  group=group))
            return None


class CandidateGenerationResults:
    """
    Results of the candidate-investment generator pipeline.
    """

    def __init__(self):
        self.base_case_converged: bool = False
        self.base_case_feasible: bool = False
        self.base_loading_report: List[str] = list()
        self.violations: List[ViolationRecord] = list()
        self.candidates: List[ReinforcementCandidate] = list()
        self.verification_report: List[str] = list()

    @property
    def base_violations(self) -> List[ViolationRecord]:
        """Base-case (N) violations."""
        return [v for v in self.violations if v.is_base_case]

    @property
    def n1_violations(self) -> List[ViolationRecord]:
        """N-1 violations."""
        return [v for v in self.violations if not v.is_base_case]

    @property
    def verified_candidates(self) -> List[ReinforcementCandidate]:
        """
        Candidates that passed verification: verified with a converged AC power flow and no new
        violations introduced. This is the shortlist offered to the user in the GUI.
        """
        return [c for c in self.candidates if c.verified_ok]

    def summary_text(self) -> str:
        """
        Assemble the textual report shown in the GUI: base-case status, per-branch loading extract,
        the N-1 violation list, and the verification outcome for the top candidate(s).
        """
        lines: List[str] = list()

        # Step 1: base case
        lines.append("=== Base case AC power flow ===")
        lines.append("Converged: " + ("yes" if self.base_case_converged else "no"))
        lines.append("Feasible (no base-case overloads): " + ("yes" if self.base_case_feasible else "no"))
        if len(self.base_violations):
            lines.append("Base-case overloads:")
            for v in self.base_violations:
                lines.append("  " + v.describe())
        lines.append("")

        # Step 2: N-1 screening
        lines.append("=== N-1 screening (LODF) ===")
        if len(self.n1_violations):
            for v in self.n1_violations:
                lines.append("  " + v.describe())
        else:
            lines.append("  No N-1 overloads found.")
        lines.append("")

        # Steps 3-4: candidates
        lines.append(f"=== Ranked candidates ({len(self.candidates)}) ===")
        if len(self.candidates) == 0:
            lines.append("  No candidates generated.")
        lines.append("")

        # Step 5: verification
        if len(self.verification_report):
            lines.append("=== Verification (AC PF + N-1) ===")
            lines.extend("  " + r for r in self.verification_report)

        return "\n".join(lines)
