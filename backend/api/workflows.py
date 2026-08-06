from fastapi import APIRouter, Depends

from backend.runtime.executor import WorkflowExecutor
from backend.runtime.graph import WorkflowGraph
from backend.sdk import NodeRegistry
from backend.schemas.models import ExecuteWorkflowRequest, ExecuteWorkflowResponse

router = APIRouter(prefix="/api/workflows", tags=["Workflows"])


def get_registry() -> NodeRegistry:
    """Return a registry that is ready even when startup hooks were skipped.

    This is important for direct API tests and for deployments that import the
    router without triggering the nodes router startup event first. Discovery
    is idempotent because registering the same type replaces the same class.
    """
    registry = NodeRegistry()
    if registry.count == 0:
        registry.discover("backend.nodes")
    return registry


@router.post("/execute", response_model=ExecuteWorkflowResponse)
async def execute_workflow(
    request: ExecuteWorkflowRequest,
    registry: NodeRegistry = Depends(get_registry),
):
    graph = WorkflowGraph.from_dict(request.model_dump())

    executor = WorkflowExecutor(
        graph=graph,
        registry=registry,
        services={},
    )

    results = await executor.execute(validate_mode=request.validate_mode or "strict")

    return ExecuteWorkflowResponse(
        workflow_id=request.id or "anonymous",
        status="completed" if not executor.has_errors else "failed",
        total_nodes=len(graph.nodes),
        succeeded=sum(1 for r in results.values() if r.status.value == "success"),
        failed=sum(1 for r in results.values() if r.status.value == "failure"),
        results={nid: r.to_dict() for nid, r in results.items()},
    )


@router.post("/validate")
async def validate_workflow(request: ExecuteWorkflowRequest):
    graph = WorkflowGraph.from_dict(request.model_dump())
    registry = get_registry()

    executor = WorkflowExecutor(graph=graph, registry=registry)
    errors = executor.validate(mode=request.validate_mode or "strict")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "node_count": len(graph.nodes),
        "edge_count": len(graph.edges),
    }
