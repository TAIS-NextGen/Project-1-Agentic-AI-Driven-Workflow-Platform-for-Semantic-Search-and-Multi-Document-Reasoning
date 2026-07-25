from __future__ import annotations

from typing import Any


class ConfigField:
    def __init__(
        self,
        key: str,
        label: str,
        type: str = "text",
        required: bool = False,
        default: Any = None,
        options: list[str] | None = None,
        description: str = "",
        placeholder: str = "",
        depends_on: dict[str, Any] | None = None,
    ):
        valid_types = {"text", "number", "select", "boolean", "file", "json", "password", "secret", "slider", "tags"}
        if type not in valid_types:
            raise ValueError(f"Invalid config field type '{type}'. Must be one of: {valid_types}")

        self.key = key
        self.label = label
        self.type = type
        self.required = required
        self.default = default
        self.options = options
        self.description = description
        self.placeholder = placeholder
        self.depends_on = depends_on

    def validate(self, value: Any) -> str | None:
        if self.required and value is None:
            return f"Field '{self.label}' is required"
        if self.type == "select" and self.options and value is not None and value not in self.options:
            return f"Field '{self.label}' must be one of: {self.options}"
        if self.type == "number" and value is not None:
            try:
                float(value)
            except (TypeError, ValueError):
                return f"Field '{self.label}' must be a number"
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "type": self.type,
            "required": self.required,
            "default": self.default,
            "options": self.options,
            "description": self.description,
            "placeholder": self.placeholder,
            "depends_on": self.depends_on,
        }

    def __repr__(self) -> str:
        return f"ConfigField({self.key}: {self.type})"
