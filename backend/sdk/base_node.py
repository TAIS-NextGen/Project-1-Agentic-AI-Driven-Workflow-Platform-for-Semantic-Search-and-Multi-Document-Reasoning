from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar

from .config import ConfigField
from .context import ExecutionContext
from .exceptions import ConfigurationError
from .ports import Port
from .result import NodeResult, NodeStatus


class BaseNode(ABC):
    type: ClassVar[str]
    name: ClassVar[str]
    category: ClassVar[str]
    icon: ClassVar[str] = "⚙️"
    color: ClassVar[str] = "#6b7280"
    description: ClassVar[str] = ""
    version: ClassVar[str] = "1.0.0"

    inputs: ClassVar[list[Port]] = []
    outputs: ClassVar[list[Port]] = []
    config_fields: ClassVar[list[ConfigField]] = []

    def __init__(self, node_id: str, config: dict[str, Any] | None = None):
        self.node_id = node_id
        self._config = config or {}
        self._validate_config()

    def _validate_config(self) -> None:
        for field in self.config_fields:
            value = self._config.get(field.key, field.default)
            error = field.validate(value)
            if error:
                raise ConfigurationError(self.type, field.key, error)

    def get_resolved_config(self) -> dict[str, Any]:
        resolved = {}
        for field in self.config_fields:
            value = self._config.get(field.key, field.default)
            if value is not None:
                resolved[field.key] = value
        return resolved

    @abstractmethod
    async def execute(self, ctx: ExecutionContext) -> NodeResult:
        ...

    def to_definition(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "name": self.name,
            "category": self.category,
            "icon": self.icon,
            "color": self.color,
            "description": self.description,
            "version": self.version,
            "inputs": [p.to_dict() for p in self.inputs],
            "outputs": [p.to_dict() for p in self.outputs],
            "config_fields": [f.to_dict() for f in self.config_fields],
        }

    @classmethod
    def get_definition(cls) -> dict[str, Any]:
        return {
            "type": cls.type,
            "name": cls.name,
            "category": cls.category,
            "icon": cls.icon,
            "color": cls.color,
            "description": cls.description,
            "version": cls.version,
            "inputs": [p.to_dict() for p in cls.inputs],
            "outputs": [p.to_dict() for p in cls.outputs],
            "config_fields": [f.to_dict() for f in cls.config_fields],
        }

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(id={self.node_id}, type={self.type})"
