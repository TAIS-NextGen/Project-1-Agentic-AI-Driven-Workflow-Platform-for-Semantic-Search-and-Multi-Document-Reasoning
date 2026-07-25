from __future__ import annotations

from enum import Enum
from typing import Any


class PortDirection(Enum):
    INPUT = "input"
    OUTPUT = "output"


class PortType(Enum):
    DOCUMENT = "document"
    DOCUMENT_COLLECTION = "document[]"
    TEXT = "text"
    EMBEDDING = "embedding"
    CHUNKS = "chunks"
    TABLE = "table"
    IMAGE = "image"
    CORPUS = "corpus"
    JSON = "json"
    ANY = "any"


_PORT_TYPE_MAP: dict[PortType, set[PortType]] = {
    PortType.ANY: set(PortType),
    PortType.DOCUMENT: {PortType.DOCUMENT, PortType.DOCUMENT_COLLECTION, PortType.IMAGE, PortType.ANY},
    PortType.DOCUMENT_COLLECTION: {PortType.DOCUMENT_COLLECTION, PortType.ANY},
    PortType.TEXT: {PortType.TEXT, PortType.CHUNKS, PortType.ANY},
    PortType.EMBEDDING: {PortType.EMBEDDING, PortType.ANY},
    PortType.CHUNKS: {PortType.CHUNKS, PortType.TEXT, PortType.ANY},
    PortType.TABLE: {PortType.TABLE, PortType.ANY},
    PortType.IMAGE: {PortType.IMAGE, PortType.DOCUMENT, PortType.ANY},
    PortType.CORPUS: {PortType.CORPUS, PortType.ANY},
    PortType.JSON: {PortType.JSON, PortType.ANY},
}


class Port:
    def __init__(
        self,
        name: str,
        type: PortType | str,
        label: str = "",
        description: str = "",
        required: bool = True,
    ):
        self.name = name
        self.type = type if isinstance(type, PortType) else PortType(type)
        self.label = label or name
        self.description = description
        self.required = required

    def can_connect_to(self, other: Port) -> bool:
        compatible = _PORT_TYPE_MAP.get(self.type, set())
        return other.type in compatible

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "type": self.type.value,
            "label": self.label,
            "description": self.description,
            "required": self.required,
        }

    def __repr__(self) -> str:
        return f"Port({self.name}: {self.type.value})"
