from __future__ import annotations

from datetime import datetime
from typing import Any


class FeedbackRecord:
    def __init__(
        self,
        workflow_id: str,
        node_id: str,
        rating: int,
        comment: str = "",
        metadata: dict[str, Any] | None = None,
    ):
        self.workflow_id = workflow_id
        self.node_id = node_id
        self.rating = rating
        self.comment = comment
        self.metadata = metadata or {}
        self.created_at = datetime.utcnow()

    def to_dict(self) -> dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "node_id": self.node_id,
            "rating": self.rating,
            "comment": self.comment,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
        }
