from fastapi import APIRouter

from backend.sdk import NodeRegistry

router = APIRouter(prefix="/api/nodes", tags=["Nodes"])

_registry = NodeRegistry()


def _ready_registry() -> NodeRegistry:
    # Lazy discovery works during normal startup, tests and embedded deployments.
    if _registry.count == 0:
        _registry.discover("backend.nodes")
    return _registry


@router.get("")
async def list_nodes():
    registry = _ready_registry()
    return {
        "nodes": registry.get_all_definitions(),
        "total": registry.count,
    }


@router.get("/categories")
async def list_categories():
    return {
        "categories": _ready_registry().get_categories(),
    }


@router.get("/{node_type}")
async def get_node(node_type: str):
    definitions = _ready_registry().get_all_definitions()
    for definition in definitions:
        if definition["type"] == node_type:
            return definition
    return {"error": f"Node type '{node_type}' not found"}, 404
