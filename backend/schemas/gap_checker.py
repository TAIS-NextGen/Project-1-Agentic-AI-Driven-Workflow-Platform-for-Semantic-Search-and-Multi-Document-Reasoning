from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class GapFieldDetail(BaseModel):
    key: str
    label: str
    required: bool
    status: str
    severity: str
    value: str | None = None
    method: str = "regex"
    recommended_action: str | None = None


class GapScore(BaseModel):
    percentage: float
    total_fields: int
    matched: int
    missing_critical: int
    missing_warning: int
    threshold_exceeded: bool


class LLMFieldResponse(BaseModel):
    requirement_key: str
    found: bool
    evidence: str = ""
    severity: str = "WARNING"


class GapReport(BaseModel):
    fields: list[GapFieldDetail]
    score: GapScore
    missing: list[str]
    has_critical_gaps: bool
