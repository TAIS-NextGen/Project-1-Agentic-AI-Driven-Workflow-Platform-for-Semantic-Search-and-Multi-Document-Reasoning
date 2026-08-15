from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any


class NodeStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILURE = "failure"
    SKIPPED = "skipped"


class NodeResult:
    def __init__(
        self,
        node_id: str,
        status: NodeStatus = NodeStatus.PENDING,
        outputs: dict[str, Any] | None = None,
        error: str | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        self.node_id = node_id
        self.status = status
        self.outputs = outputs or {}
        self.error = error
        self.metadata = metadata or {}
        self.started_at: datetime | None = None
        self.completed_at: datetime | None = None

    def start(self) -> None:
        self.status = NodeStatus.RUNNING
        self.started_at = datetime.utcnow()

    def succeed(self, outputs: dict[str, Any] | None = None) -> None:
        self.status = NodeStatus.SUCCESS
        if outputs:
            self.outputs.update(outputs)
        self.completed_at = datetime.utcnow()

    def fail(self, error: str) -> None:
        self.status = NodeStatus.FAILURE
        self.error = error
        self.completed_at = datetime.utcnow()

    def skip(self, reason: str = "") -> None:
        self.status = NodeStatus.SKIPPED
        if reason:
            self.error = reason
        self.completed_at = datetime.utcnow()

    def get_output(self, name: str, default: Any = None) -> Any:
        return self.outputs.get(name, default)

    @property
    def duration_ms(self) -> float | None:
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds() * 1000
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "status": self.status.value,
            "outputs": self.outputs,
            "error": self.error,
            "metadata": self.metadata,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_ms": self.duration_ms,
        }
