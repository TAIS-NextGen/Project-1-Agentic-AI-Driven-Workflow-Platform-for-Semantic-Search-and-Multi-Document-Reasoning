class NodeExecutionError(Exception):
    def __init__(self, node_type: str, node_id: str, message: str, cause: Exception | None = None):
        self.node_type = node_type
        self.node_id = node_id
        self.cause = cause
        super().__init__(f"[{node_type}:{node_id}] {message}")


class ValidationError(Exception):
    def __init__(self, message: str, field: str | None = None):
        self.field = field
        super().__init__(message)


class ConfigurationError(Exception):
    def __init__(self, node_type: str, field: str, message: str):
        self.node_type = node_type
        self.field = field
        super().__init__(f"[{node_type}] field '{field}': {message}")


class ServiceError(Exception):
    def __init__(self, service: str, message: str, cause: Exception | None = None):
        self.service = service
        self.cause = cause
        super().__init__(f"[{service}] {message}")


class GraphValidationError(Exception):
    def __init__(self, message: str, errors: list[str] | None = None):
        self.errors = errors or []
        super().__init__(message)
