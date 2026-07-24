# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from dataclasses import dataclass

from VeraGridEngine.Utils.Symbolic.SugiyamaLayered.model import SugiyamaGraph
from VeraGridEngine.Utils.Symbolic.SugiyamaLayered.options import SugiyamaOptionResolver
from VeraGridEngine.Utils.Symbolic.SugiyamaLayered.phases import (
    ConnectedComponentsPhase,
    CrossingMinimizationPhase,
    CycleBreakingPhase,
    EdgeRoutingPhase,
    LabelPlacementPhase,
    LayeringPhase,
    LongEdgePhase,
    NodePlacementPhase,
)
from VeraGridEngine.Utils.Symbolic.SugiyamaLayered.pipeline import LayoutContext, LayoutPipeline, PipelineReport


@dataclass
class EngineResult:
    graph: SugiyamaGraph
    report: PipelineReport


class SugiyamaLayeredPythonEngine:
    """
    Python-native layered layout engine scaffold.

    The current implementation establishes the architecture and a deterministic
    baseline pipeline. Additional heuristics and advanced options can still be
    implemented phase by phase.
    """

    def __init__(self, option_resolver: SugiyamaOptionResolver | None = None):
        self.option_resolver = option_resolver or SugiyamaOptionResolver()
        self.pipeline = LayoutPipeline(
            phases=[
                ConnectedComponentsPhase(),
                CycleBreakingPhase(),
                LayeringPhase(),
                LongEdgePhase(),
                CrossingMinimizationPhase(),
                NodePlacementPhase(),
                EdgeRoutingPhase(),
                LabelPlacementPhase(),
            ]
        )

    def compute(self, graph: SugiyamaGraph) -> EngineResult:
        context = LayoutContext(graph=graph, option_resolver=self.option_resolver)
        report = self.pipeline.run(context)
        return EngineResult(graph=graph, report=report)
