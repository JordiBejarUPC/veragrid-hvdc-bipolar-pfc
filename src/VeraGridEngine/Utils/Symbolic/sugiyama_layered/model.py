# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


PrimitiveId = str


@dataclass
class SugiyamaPrimitive:
    identifier: PrimitiveId
    layout_options: dict[str, Any] = field(default_factory=dict)
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass
class SugiyamaLabel(SugiyamaPrimitive):
    text: str = ""
    width: float = 0.0
    height: float = 0.0
    x: float | None = None
    y: float | None = None


@dataclass
class SugiyamaPort(SugiyamaPrimitive):
    width: float = 0.0
    height: float = 0.0
    x: float | None = None
    y: float | None = None
    labels: list[SugiyamaLabel] = field(default_factory=list)


@dataclass
class SugiyamaNode(SugiyamaPrimitive):
    width: float = 0.0
    height: float = 0.0
    x: float | None = None
    y: float | None = None
    labels: list[SugiyamaLabel] = field(default_factory=list)
    ports: list[SugiyamaPort] = field(default_factory=list)
    children: list["SugiyamaNode"] = field(default_factory=list)
    parent: PrimitiveId | None = None

    def iter_descendants(self) -> list["SugiyamaNode"]:
        result: list[SugiyamaNode] = []
        stack = list(self.children)
        while stack:
            child = stack.pop(0)
            result.append(child)
            stack[0:0] = child.children
        return result


@dataclass
class SugiyamaEdgeSection:
    start_point: tuple[float, float] | None = None
    end_point: tuple[float, float] | None = None
    bend_points: list[tuple[float, float]] = field(default_factory=list)


@dataclass
class SugiyamaEdge(SugiyamaPrimitive):
    sources: list[PrimitiveId] = field(default_factory=list)
    targets: list[PrimitiveId] = field(default_factory=list)
    labels: list[SugiyamaLabel] = field(default_factory=list)
    sections: list[SugiyamaEdgeSection] = field(default_factory=list)


@dataclass
class SugiyamaGraph(SugiyamaPrimitive):
    width: float = 0.0
    height: float = 0.0
    children: list[SugiyamaNode] = field(default_factory=list)
    edges: list[SugiyamaEdge] = field(default_factory=list)
    labels: list[SugiyamaLabel] = field(default_factory=list)

    def all_nodes(self) -> list[SugiyamaNode]:
        result: list[SugiyamaNode] = []
        stack = list(self.children)
        while stack:
            node = stack.pop(0)
            result.append(node)
            stack[0:0] = node.children
        return result

    def all_ports(self) -> list[SugiyamaPort]:
        result: list[SugiyamaPort] = []
        for node in self.all_nodes():
            result.extend(node.ports)
        return result

    def node_by_id(self) -> dict[PrimitiveId, SugiyamaNode]:
        return {node.identifier: node for node in self.all_nodes()}

    def port_by_id(self) -> dict[PrimitiveId, SugiyamaPort]:
        return {port.identifier: port for port in self.all_ports()}

    def clone_shallow(self) -> "SugiyamaGraph":
        return SugiyamaGraph(
            identifier=self.identifier,
            layout_options=dict(self.layout_options),
            properties=dict(self.properties),
            width=self.width,
            height=self.height,
            children=list(self.children),
            edges=list(self.edges),
            labels=list(self.labels),
        )
