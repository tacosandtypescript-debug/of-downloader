"""Errores comunes del backend.

`UserError` vive en `backend.models` para que CLI, dashboard y servicios
compartan la misma clase.
"""

from backend.models import UserError

__all__ = ["BackendError", "UserError"]


class BackendError(RuntimeError):
    """Error técnico del backend."""
