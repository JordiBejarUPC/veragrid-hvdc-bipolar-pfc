# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter
from typing import Protocol

from .model import SugiyamaGraph
from .options import SugiyamaOptionResolver


@dataclass
class PhaseTiming:
    name: str
    seconds: float


@dataclass
class PipelineReport:
    timings: list[PhaseTiming] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


@dataclass
class LayoutContext:
    graph: SugiyamaGraph
    option_resolver: SugiyamaOptionResolver
    report: PipelineReport = field(default_factory=PipelineReport)
    phase_state: dict[str, object] = field(default_factory=dict)


class LayoutPhase(Protocol):
    name: str

    def run(self, context: LayoutContext) -> None:
        ...


class LayoutPipeline:
    def __init__(self, phases: list[LayoutPhase]):
        self.phases = phases

    def run(self, context: LayoutContext) -> PipelineReport:
        for phase in self.phases:
            start = perf_counter()
            phase.run(context)
            elapsed = perf_counter() - start
            context.report.timings.append(PhaseTiming(name=phase.name, seconds=elapsed))
        return context.report
