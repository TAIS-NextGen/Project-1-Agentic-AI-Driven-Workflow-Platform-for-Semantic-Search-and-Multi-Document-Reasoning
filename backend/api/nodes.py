from fastapi import APIRouter

from backend.sdk import NodeRegistry

router = APIRouter(prefix="/api/nodes", tags=["Nodes"])

_registry = NodeRegistry()


@router.on_event("startup")
async def discover_nodes():
    _registry.discover("backend.nodes")


@router.get("")
async def list_nodes():
    return {
        "nodes": _registry.get_all_definitions(),
        "total": _registry.count,
    }


@router.get("/categories")
async def list_categories():
    return {
        "categories": _registry.get_categories(),
    }


@router.get("/{node_type}")
async def get_node(node_type: str):
    definitions = _registry.get_all_definitions()
    for d in definitions:
        if d["type"] == node_type:
            return d
    return {"error": f"Node type '{node_type}' not found"}, 404
