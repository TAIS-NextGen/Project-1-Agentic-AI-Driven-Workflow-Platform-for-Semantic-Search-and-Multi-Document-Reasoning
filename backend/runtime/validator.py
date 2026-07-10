from __future__ import annotations

from collections import deque
from typing import Any

from backend.sdk import BaseNode, Port, PortType, registry
from backend.sdk.exceptions import GraphValidationError

from .graph import WorkflowGraph


class WorkflowValidator:
    def __init__(self, graph: WorkflowGraph, node_map: dict[str, type[BaseNode]] | None = None):
        self.graph = graph
        self._node_map = node_map or {}

    def validate(self, mode: str = "strict") -> list[str]:
        errors: list[str] = []

        errors.extend(self._validate_node_existence())
        errors.extend(self._validate_cycles())
        errors.extend(self._validate_port_compatibility())
        errors.extend(self._validate_required_inputs())

        if mode == "strict":
            errors.extend(self._validate_orphan_nodes())

        return errors

    def _validate_node_existence(self) -> list[str]:
        errors = []
        for n in self.graph.nodes.values():
            if n.node_type not in {cls.type for cls in self._node_map.values()}:
                errors.append(f"Node '{n.node_id}': unknown type '{n.node_type}'")
        return errors

    def _validate_cycles(self) -> list[str]:
        adj: dict[str, list[str]] = {nid: [] for nid in self.graph.nodes}
        in_deg: dict[str, int] = {nid: 0 for nid in self.graph.nodes}
        for e in self.graph.edges:
            if e.source_id in adj and e.target_id in adj:
                adj[e.source_id].append(e.target_id)
                in_deg[e.target_id] = in_deg.get(e.target_id, 0) + 1

        q = deque([nid for nid, d in in_deg.items() if d == 0])
        visited = 0
        while q:
            node = q.popleft()
            visited += 1
            for neighbor in adj.get(node, []):
                in_deg[neighbor] -= 1
                if in_deg[neighbor] == 0:
                    q.append(neighbor)

        if visited != len(self.graph.nodes):
            return ["Graph contains a cycle"]
        return []

    def _validate_port_compatibility(self) -> list[str]:
        errors = []
        for e in self.graph.edges:
            source_node = self.graph.get_node(e.source_id)
            target_node = self.graph.get_node(e.target_id)
            if not source_node or not target_node:
                continue

            source_cls = self._node_map.get(source_node.node_type)
            target_cls = self._node_map.get(target_node.node_type)

            if not source_cls or not target_cls:
                continue

            source_port = next((p for p in source_cls.outputs if p.name == e.source_port), None)
            target_port = next((p for p in target_cls.inputs if p.name == e.target_port), None)

            if source_port and target_port:
                if not source_port.can_connect_to(target_port):
                    errors.append(
                        f"Edge '{e.source_id}.{e.source_port}' → '{e.target_id}.{e.target_port}': "
                        f"type mismatch ({source_port.type.value} → {target_port.type.value})"
                    )
        return errors

    def _validate_required_inputs(self) -> list[str]:
        errors = []
        for nid, node in self.graph.nodes.items():
            node_cls = self._node_map.get(node.node_type)
            if not node_cls:
                continue
            connected_inputs = {
                e.target_port
                for e in self.graph.edges
                if e.target_id == nid
            }
            for inp in node_cls.inputs:
                if inp.required and inp.name not in connected_inputs:
                    errors.append(f"Node '{nid}' ({node.node_type}): required input '{inp.name}' is not connected")
        return errors

    def _validate_orphan_nodes(self) -> list[str]:
        errors = []
        for nid in self.graph.nodes:
            incoming, outgoing = self.graph.get_edges(nid)
            if not incoming and not outgoing:
                node_cls = self._node_map.get(nid)
                if node_cls and all(not inp.required for inp in node_cls.inputs):
                    continue
                errors.append(f"Node '{nid}' is orphaned (no connections)")
        return errors

    def validate_and_raise(self, mode: str = "strict") -> None:
        errors = self.validate(mode)
        if errors:
            raise GraphValidationError(f"Workflow validation failed with {len(errors)} error(s)", errors)
