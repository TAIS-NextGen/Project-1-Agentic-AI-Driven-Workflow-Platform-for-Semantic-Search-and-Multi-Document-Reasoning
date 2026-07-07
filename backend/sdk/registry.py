from __future__ import annotations

import importlib
import inspect
import pkgutil
from typing import Any

from .base_node import BaseNode


class NodeRegistry:
    _instance: NodeRegistry | None = None
    _nodes: dict[str, type[BaseNode]] = {}

    def __new__(cls) -> NodeRegistry:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def register(self, node_cls: type[BaseNode]) -> None:
        if not inspect.isclass(node_cls) or not issubclass(node_cls, BaseNode):
            raise TypeError(f"{node_cls} must be a subclass of BaseNode")
        if node_cls is BaseNode:
            return
        type_name = getattr(node_cls, "type", None)
        if not type_name:
            raise ValueError(f"{node_cls.__name__} must define a 'type' class variable")
        self._nodes[type_name] = node_cls

    def register_from_module(self, module_name: str) -> None:
        module = importlib.import_module(module_name)
        for _, obj_name, _ in pkgutil.walk_packages(module.__path__, module.__name__ + "."):
            try:
                sub_module = importlib.import_module(obj_name)
                for name, cls in inspect.getmembers(sub_module, inspect.isclass):
                    if cls is not BaseNode and issubclass(cls, BaseNode) and hasattr(cls, "type"):
                        self.register(cls)
            except Exception:
                continue

    def discover(self, base_package: str = "backend.nodes") -> None:
        try:
            package = importlib.import_module(base_package)
            self.register_from_module(base_package)
            for _, name, is_pkg in pkgutil.walk_packages(package.__path__, package.__name__ + "."):
                if is_pkg:
                    self.register_from_module(name)
        except ModuleNotFoundError:
            pass

    def get(self, type_name: str) -> type[BaseNode] | None:
        return self._nodes.get(type_name)

    def get_instance(self, type_name: str, node_id: str, config: dict[str, Any] | None = None) -> BaseNode | None:
        cls = self.get(type_name)
        if cls is None:
            return None
        return cls(node_id=node_id, config=config)

    def get_all_definitions(self) -> list[dict[str, Any]]:
        return [cls.get_definition() for cls in self._nodes.values()]

    def get_by_category(self, category: str) -> list[dict[str, Any]]:
        return [
            cls.get_definition()
            for cls in self._nodes.values()
            if getattr(cls, "category", None) == category
        ]

    def get_categories(self) -> dict[str, list[dict[str, Any]]]:
        categories: dict[str, list[dict[str, Any]]] = {}
        for cls in self._nodes.values():
            cat = getattr(cls, "category", "Uncategorized")
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(cls.get_definition())
        return categories

    def clear(self) -> None:
        self._nodes.clear()

    @property
    def count(self) -> int:
        return len(self._nodes)
