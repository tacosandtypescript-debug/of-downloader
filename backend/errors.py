"""Errores comunes del backend."""


class BackendError(RuntimeError):
    """Error técnico del backend."""


class UserError(BackendError):
    """Error que el frontend puede mostrar directamente al usuario."""

