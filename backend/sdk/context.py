from __future__ import annotations

import logging
from typing import Any


class ExecutionContext:
    def __init__(
        self,
        workflow_id: str,
        node_id: str,
        inputs: dict[str, Any] | None = None,
        config: dict[str, Any] | None = None,
        logger: logging.Logger | None = None,
        services: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        self.workflow_id = workflow_id
        self.node_id = node_id
        self.inputs = inputs or {}
        self.config = config or {}
        self.logger = logger or logging.getLogger(f"workflow.{workflow_id}.{node_id}")
        self.services = services or {}
        self.metadata = metadata or {}

    def get_input(self, name: str, default: Any = None) -> Any:
        return self.inputs.get(name, default)

    def get_config(self, key: str, default: Any = None) -> Any:
        return self.config.get(key, default)

    def get_service(self, name: str) -> Any:
        service = self.services.get(name)
        if service is None:
            raise RuntimeError(f"Service '{name}' not available in execution context")
        return service

    def to_dict(self) -> dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "node_id": self.node_id,
            "inputs": self.inputs,
            "config": self.config,
            "metadata": self.metadata,
        }
