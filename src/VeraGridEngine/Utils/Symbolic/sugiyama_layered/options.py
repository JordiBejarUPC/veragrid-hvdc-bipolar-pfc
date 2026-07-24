# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class OptionDefinition:
    identifier: str
    default: Any
    value_type: type | tuple[type, ...]
    applies_to: tuple[str, ...]


SUGIYAMA_LAYERED_DEFAULTS: dict[str, OptionDefinition] = {
    "org.vera.sugiyama.algorithm": OptionDefinition(
        identifier="org.vera.sugiyama.algorithm",
        default="layered",
        value_type=str,
        applies_to=("graph",),
    ),
    "org.vera.sugiyama.direction": OptionDefinition(
        identifier="org.vera.sugiyama.direction",
        default="UNDEFINED",
        value_type=str,
        applies_to=("graph", "node"),
    ),
    "org.vera.sugiyama.edgeRouting": OptionDefinition(
        identifier="org.vera.sugiyama.edgeRouting",
        default="ORTHOGONAL",
        value_type=str,
        applies_to=("graph",),
    ),
    "org.vera.sugiyama.spacing.nodeNode": OptionDefinition(
        identifier="org.vera.sugiyama.spacing.nodeNode",
        default=20.0,
        value_type=(int, float),
        applies_to=("graph", "node"),
    ),
    "org.vera.sugiyama.spacing.componentComponent": OptionDefinition(
        identifier="org.vera.sugiyama.spacing.componentComponent",
        default=40.0,
        value_type=(int, float),
        applies_to=("graph",),
    ),
    "org.vera.sugiyama.layered.spacing.nodeNodeBetweenLayers": OptionDefinition(
        identifier="org.vera.sugiyama.layered.spacing.nodeNodeBetweenLayers",
        default=20.0,
        value_type=(int, float),
        applies_to=("graph",),
    ),
    "org.vera.sugiyama.layered.layering.strategy": OptionDefinition(
        identifier="org.vera.sugiyama.layered.layering.strategy",
        default="NETWORK_SIMPLEX",
        value_type=str,
        applies_to=("graph",),
    ),
    "org.vera.sugiyama.layered.cycleBreaking.strategy": OptionDefinition(
        identifier="org.vera.sugiyama.layered.cycleBreaking.strategy",
        default="GREEDY",
        value_type=str,
        applies_to=("graph",),
    ),
    "org.vera.sugiyama.layered.nodePlacement.strategy": OptionDefinition(
        identifier="org.vera.sugiyama.layered.nodePlacement.strategy",
        default="BRANDES_KOEPF",
        value_type=str,
        applies_to=("graph",),
    ),
    "org.vera.sugiyama.layered.nodePlacement.bk.fixedAlignment": OptionDefinition(
        identifier="org.vera.sugiyama.layered.nodePlacement.bk.fixedAlignment",
        default="NONE",
        value_type=str,
        applies_to=("graph",),
    ),
    "org.vera.sugiyama.layered.crossingMinimization.strategy": OptionDefinition(
        identifier="org.vera.sugiyama.layered.crossingMinimization.strategy",
        default="LAYER_SWEEP",
        value_type=str,
        applies_to=("graph",),
    ),
    "org.vera.sugiyama.portConstraints": OptionDefinition(
        identifier="org.vera.sugiyama.portConstraints",
        default="UNDEFINED",
        value_type=str,
        applies_to=("node",),
    ),
    "org.vera.sugiyama.port.side": OptionDefinition(
        identifier="org.vera.sugiyama.port.side",
        default="UNDEFINED",
        value_type=str,
        applies_to=("port",),
    ),
    "org.vera.sugiyama.portAlignment.default": OptionDefinition(
        identifier="org.vera.sugiyama.portAlignment.default",
        default="CENTER",
        value_type=str,
        applies_to=("graph", "node"),
    ),
    "org.vera.sugiyama.portAlignment.west": OptionDefinition(
        identifier="org.vera.sugiyama.portAlignment.west",
        default="CENTER",
        value_type=str,
        applies_to=("graph", "node"),
    ),
    "org.vera.sugiyama.portAlignment.east": OptionDefinition(
        identifier="org.vera.sugiyama.portAlignment.east",
        default="CENTER",
        value_type=str,
        applies_to=("graph", "node"),
    ),
    "org.vera.sugiyama.portAlignment.north": OptionDefinition(
        identifier="org.vera.sugiyama.portAlignment.north",
        default="CENTER",
        value_type=str,
        applies_to=("graph", "node"),
    ),
    "org.vera.sugiyama.portAlignment.south": OptionDefinition(
        identifier="org.vera.sugiyama.portAlignment.south",
        default="CENTER",
        value_type=str,
        applies_to=("graph", "node"),
    ),
    "org.vera.sugiyama.layered.considerModelOrder.strategy": OptionDefinition(
        identifier="org.vera.sugiyama.layered.considerModelOrder.strategy",
        default="NONE",
        value_type=str,
        applies_to=("graph",),
    ),
    "org.vera.sugiyama.layered.edgeRouting.selfLoopDistribution": OptionDefinition(
        identifier="org.vera.sugiyama.layered.edgeRouting.selfLoopDistribution",
        default="NORTH",
        value_type=str,
        applies_to=("graph",),
    ),
    "org.vera.sugiyama.layered.feedbackEdges": OptionDefinition(
        identifier="org.vera.sugiyama.layered.feedbackEdges",
        default=False,
        value_type=(bool, str),
        applies_to=("graph",),
    ),
}


class SugiyamaOptionResolver:
    """
    Minimal Sugiyama-like option resolver.

    Vera Sugiyama supports inheritance and resolution on different graph elements. This
    class implements the same idea with a narrow first slice of options.
    """

    def __init__(self, registry: dict[str, OptionDefinition] | None = None):
        self.registry = registry or SUGIYAMA_LAYERED_DEFAULTS

    def validate(self, option_id: str, value: Any) -> bool:
        definition = self.registry.get(option_id)
        if definition is None:
            return True
        if isinstance(value, definition.value_type):
            return True
        if isinstance(value, str) and definition.value_type in ((int, float),):
            try:
                float(value)
                return True
            except ValueError:
                return False
        return False

    def resolve_for_element(
        self,
        graph_options: dict[str, Any],
        element_options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        resolved: dict[str, Any] = {
            option_id: definition.default
            for option_id, definition in self.registry.items()
        }
        resolved.update(graph_options)
        if element_options:
            resolved.update(element_options)
        return resolved
