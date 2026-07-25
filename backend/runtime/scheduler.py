from __future__ import annotations

from collections import deque
from typing import Any

from .graph import WorkflowGraph


class WorkflowScheduler:
    def __init__(self, graph: WorkflowGraph):
        self.graph = graph

    def topological_sort(self) -> list[str]:
        adj: dict[str, list[str]] = {nid: [] for nid in self.graph.nodes}
        in_deg: dict[str, int] = {nid: 0 for nid in self.graph.nodes}
        for e in self.graph.edges:
            if e.source_id in adj and e.target_id in adj:
                adj[e.source_id].append(e.target_id)
                in_deg[e.target_id] = in_deg.get(e.target_id, 0) + 1

        q = deque([nid for nid, d in in_deg.items() if d == 0])
        ordered: list[str] = []
        while q:
            node = q.popleft()
            ordered.append(node)
            for neighbor in adj.get(node, []):
                in_deg[neighbor] -= 1
                if in_deg[neighbor] == 0:
                    q.append(neighbor)

        if len(ordered) != len(self.graph.nodes):
            raise ValueError("Graph contains a cycle — cannot produce topological order")

        return ordered

    def parallel_groups(self) -> list[list[str]]:
        adj: dict[str, list[str]] = {nid: [] for nid in self.graph.nodes}
        in_deg: dict[str, int] = {nid: 0 for nid in self.graph.nodes}
        for e in self.graph.edges:
            if e.source_id in adj and e.target_id in adj:
                adj[e.source_id].append(e.target_id)
                in_deg[e.target_id] = in_deg.get(e.target_id, 0) + 1

        in_deg_copy = dict(in_deg)
        groups: list[list[str]] = []

        while True:
            current = [nid for nid, d in in_deg_copy.items() if d == 0]
            if not current:
                break
            groups.append(current)
            for node in current:
                del in_deg_copy[node]
                for neighbor in adj.get(node, []):
                    if neighbor in in_deg_copy:
                        in_deg_copy[neighbor] -= 1

        all_processed = sum(len(g) for g in groups)
        if all_processed != len(self.graph.nodes):
            raise ValueError("Graph contains a cycle")

        return groups

    def get_dependency_order(self, node_id: str) -> list[str]:
        ordered = self.topological_sort()
        try:
            idx = ordered.index(node_id)
            return ordered[:idx]
        except ValueError:
            return []

    def is_parallelizable(self, node_id_a: str, node_id_b: str) -> bool:
        groups = self.parallel_groups()
        a_group = next((i for i, g in enumerate(groups) if node_id_a in g), -1)
        b_group = next((i for i, g in enumerate(groups) if node_id_b in g), -1)
        return a_group == b_group and a_group != -1
