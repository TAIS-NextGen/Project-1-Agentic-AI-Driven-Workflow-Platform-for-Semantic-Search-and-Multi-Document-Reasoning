from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class GraphNodeSchema(BaseModel):
    id: str = Field(..., description="Unique node identifier")
    type: str = Field(..., description="Node type (matches BaseNode.type)")
    config: dict[str, Any] = Field(default_factory=dict, description="Node configuration")


class EdgeSchema(BaseModel):
    source: str = Field(..., description="Source node ID")
    source_port: str = Field("output", description="Source port name")
    target: str = Field(..., description="Target node ID")
    target_port: str = Field("input", description="Target port name")
    condition: str | None = Field(None, description="Route condition for control edges")
    kind: str = Field("data", description="Edge kind: 'data' or 'control'")


class ExecuteWorkflowRequest(BaseModel):
    id: str | None = Field(None, description="Workflow ID")
    nodes: list[GraphNodeSchema] = Field(..., min_length=1)
    edges: list[EdgeSchema] = Field(default_factory=list)
    validate_mode: str | None = Field("strict", description="Validation mode: strict, relaxed, or null to skip")


class NodeResultSchema(BaseModel):
    node_id: str
    status: str
    outputs: dict[str, Any] = {}
    error: str | None = None
    metadata: dict[str, Any] = {}
    started_at: str | None = None
    completed_at: str | None = None
    duration_ms: float | None = None


class ExecuteWorkflowResponse(BaseModel):
    workflow_id: str
    status: str
    total_nodes: int
    succeeded: int
    failed: int
    results: dict[str, NodeResultSchema]


class NodeDefinitionSchema(BaseModel):
    type: str
    name: str
    category: str
    icon: str
    color: str
    description: str
    version: str
    inputs: list[dict[str, Any]]
    outputs: list[dict[str, Any]]
    config_fields: list[dict[str, Any]]


class NodeListResponse(BaseModel):
    nodes: list[NodeDefinitionSchema]
    total: int


class CategoriesResponse(BaseModel):
    categories: dict[str, list[NodeDefinitionSchema]]
