"""Fachada de compatibilidad del servicio de autenticación.

La implementación real de cookies, credenciales, receptor local y verificación
de sesión vive en `ofbackup_cli`. Este módulo solo delega.

Antes existía aquí una segunda copia completa del parseo de cookies y del
receptor HTTP local: dos implementaciones de código sensible que podían
quedar desincronizadas (por ejemplo, al endurecer CORS solo se habría
corregido una). Ahora hay un único punto con esa lógica.
"""

from __future__ import annotations

from pathlib import Path

from backend import constants
from backend.constants import APP_VERSION, DEFAULT_APP_TOKEN
from backend.models import UserError

__all__ = [
    "APP_VERSION",
    "DEFAULT_APP_TOKEN",
    "AuthService",
    "configure_credentials",
    "credentials_ready",
    "get_auth_service",
    "import_credentials_file",
    "UserError",
    "receive_credentials_locally",
    "require_credentials",
    "test_credentials",
]


def _cli():
    """Importa el CLI de forma diferida para no crear ciclos al importar."""
    import ofbackup_cli

    return ofbackup_cli


class AuthService:
    """Compatibilidad: cada método delega en la función equivalente del CLI."""

    APP_VERSION = constants.APP_VERSION
    DEFAULT_APP_TOKEN = constants.DEFAULT_APP_TOKEN
    AUTH_EXPORT_FORMAT = constants.AUTH_EXPORT_FORMAT
    AUTH_EXPORT_VERSION = constants.AUTH_EXPORT_VERSION
    AUTH_EXPORT_FILENAME = constants.AUTH_EXPORT_FILENAME
    MAX_AUTH_EXPORT_SIZE = constants.MAX_AUTH_EXPORT_SIZE

    def __init__(self, config_service=None):
        self._config = config_service

    @property
    def home(self) -> Path:
        return _cli().HOME

    @property
    def auth_path(self) -> Path:
        return _cli().AUTH_PATH

    @property
    def default_export_path(self) -> Path:
        return _cli().EXPORTED_AUTH_PATH

    def parse_cookie_header(self, raw: str) -> dict[str, str]:
        return _cli().parse_cookie_header(raw)

    def validate_auth_values(self, values: dict[str, str]) -> dict[str, str]:
        return _cli().validate_auth_values(values)

    def parse_auth_export(self, data: object) -> dict[str, str]:
        return _cli().parse_auth_export(data)

    def load_auth_export(self, path: Path) -> tuple[dict[str, str], str]:
        return _cli().load_auth_export(Path(path))

    def credentials_payload(self, values: dict[str, str]) -> dict[str, str]:
        return _cli().credentials_payload(values)

    def save_credentials(self, values: dict[str, str]) -> None:
        _cli().save_credentials(values)

    def credentials_ready(self) -> bool:
        return _cli().credentials_ready()

    def import_credentials(self, path: Path) -> None:
        _cli().import_credentials_file(Path(path))

    def test_credentials(self, timeout: int = 60) -> int:
        return _cli().test_credentials(timeout=timeout)

    def start_local_receiver(
        self, port: int = 8765, timeout: int = 300, *, show_qr: bool = False
    ) -> int:
        return _cli().receive_credentials_locally(
            port=port, timeout=timeout, show_qr=show_qr
        )


_auth_service: AuthService | None = None


def get_auth_service() -> AuthService:
    global _auth_service
    if _auth_service is None:
        _auth_service = AuthService()
    return _auth_service


def configure_credentials() -> int:
    return _cli().configure_credentials()


def credentials_ready() -> bool:
    return _cli().credentials_ready()


def require_credentials() -> None:
    _cli().require_credentials()


def import_credentials_file(path) -> None:
    _cli().import_credentials_file(Path(path))


def test_credentials(timeout: int = 60) -> int:
    return _cli().test_credentials(timeout=timeout)


def receive_credentials_locally(*, port: int = 8765, show_qr: bool = False) -> int:
    return _cli().receive_credentials_locally(port=port, show_qr=show_qr)
