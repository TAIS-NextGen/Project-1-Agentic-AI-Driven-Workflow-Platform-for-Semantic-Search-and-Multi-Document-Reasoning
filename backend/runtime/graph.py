from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class GraphNode:
    node_id: str
    node_type: str
    config: dict[str, Any] = field(default_factory=dict)


@dataclass
class Edge:
    source_id: str
    source_port: str
    target_id: str
    target_port: str
    is_dynamic: bool = False
    condition: str | None = None
    kind: str = "data"


class WorkflowGraph:
    def __init__(self):
        self._nodes: dict[str, GraphNode] = {}
        self._edges: list[Edge] = []

    def add_node(self, node_id: str, node_type: str, config: dict[str, Any] | None = None) -> GraphNode:
        if node_id in self._nodes:
            raise ValueError(f"Node '{node_id}' already exists")
        node = GraphNode(node_id=node_id, node_type=node_type, config=config or {})
        self._nodes[node_id] = node
        return node

    def remove_node(self, node_id: str) -> None:
        self._nodes.pop(node_id, None)
        self._edges = [
            e for e in self._edges
            if e.source_id != node_id and e.target_id != node_id
        ]

    def add_edge(self, source_id: str, source_port: str, target_id: str, target_port: str,
                 condition: str | None = None, kind: str = "data") -> Edge:
        if source_id not in self._nodes:
            raise ValueError(f"Source node '{source_id}' not found")
        if target_id not in self._nodes:
            raise ValueError(f"Target node '{target_id}' not found")
        edge = Edge(source_id, source_port, target_id, target_port,
                    condition=condition, kind=kind)
        self._edges.append(edge)
        return edge

    def add_dynamic_edge(self, source_id: str, source_port: str, target_id: str, target_port: str,
                         condition: str | None = None, kind: str = "data") -> Edge:
        edge = Edge(source_id, source_port, target_id, target_port, is_dynamic=True,
                    condition=condition, kind=kind)
        self._edges.append(edge)
        return edge

    def remove_edge(self, source_id: str, target_id: str) -> None:
        self._edges = [
            e for e in self._edges
            if not (e.source_id == source_id and e.target_id == target_id)
        ]

    def get_node(self, node_id: str) -> GraphNode | None:
        return self._nodes.get(node_id)

    def get_edges(self, node_id: str) -> tuple[list[Edge], list[Edge]]:
        incoming = [e for e in self._edges if e.target_id == node_id]
        outgoing = [e for e in self._edges if e.source_id == node_id]
        return incoming, outgoing

    def get_upstream(self, node_id: str) -> list[str]:
        incoming, _ = self.get_edges(node_id)
        return [e.source_id for e in incoming]

    def get_downstream(self, node_id: str) -> list[str]:
        _, outgoing = self.get_edges(node_id)
        return [e.target_id for e in outgoing]

    @property
    def nodes(self) -> dict[str, GraphNode]:
        return dict(self._nodes)

    @property
    def edges(self) -> list[Edge]:
        return list(self._edges)

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": [
                {"id": n.node_id, "type": n.node_type, "config": n.config}
                for n in self._nodes.values()
            ],
            "edges": [
                {
                    "source": e.source_id,
                    "source_port": e.source_port,
                    "target": e.target_id,
                    "target_port": e.target_port,
                    "is_dynamic": e.is_dynamic,
                    "condition": e.condition,
                    "kind": e.kind,
                }
                for e in self._edges
            ],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WorkflowGraph:
        graph = cls()
        for n in data.get("nodes", []):
            graph.add_node(n["id"], n["type"], n.get("config"))
        for e in data.get("edges", []):
            graph.add_edge(e["source"], e.get("source_port", "output"),
                           e["target"], e.get("target_port", "input"),
                           condition=e.get("condition"), kind=e.get("kind", "data"))
        return graph
