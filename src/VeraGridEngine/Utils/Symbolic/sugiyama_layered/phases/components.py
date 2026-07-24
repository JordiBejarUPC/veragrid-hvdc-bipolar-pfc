# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from collections import deque

from ..pipeline import LayoutContext


def _owner_of_endpoint(node_ids: set[str], port_to_owner: dict[str, str], endpoint_id: str) -> str | None:
    if endpoint_id in node_ids:
        return endpoint_id
    return port_to_owner.get(endpoint_id)


class ConnectedComponentsPhase:
    name = "connected-components"

    def run(self, context: LayoutContext) -> None:
        node_ids = {node.identifier for node in context.graph.children}
        port_to_owner: dict[str, str] = {}
        for node in context.graph.children:
            for port in node.ports:
                port_to_owner[port.identifier] = node.identifier

        adjacency: dict[str, set[str]] = {node.identifier: set() for node in context.graph.children}
        for edge in context.graph.edges:
            for src in edge.sources:
                for dst in edge.targets:
                    src_node = _owner_of_endpoint(node_ids, port_to_owner, src)
                    dst_node = _owner_of_endpoint(node_ids, port_to_owner, dst)
                    if src_node is None or dst_node is None:
                        continue
                    adjacency.setdefault(src_node, set()).add(dst_node)
                    adjacency.setdefault(dst_node, set()).add(src_node)

        components: list[list[str]] = []
        visited: set[str] = set()
        for node_id in adjacency:
            if node_id in visited:
                continue
            queue = deque([node_id])
            visited.add(node_id)
            component: list[str] = []
            while queue:
                current = queue.popleft()
                component.append(current)
                for neighbor in sorted(adjacency.get(current, set())):
                    if neighbor not in visited:
                        visited.add(neighbor)
                        queue.append(neighbor)
            components.append(component)

        context.phase_state["components"] = components
        context.report.notes.append(f"Detected {len(components)} connected component(s).")
