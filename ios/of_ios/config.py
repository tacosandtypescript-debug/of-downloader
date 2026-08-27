"""Configuración y credenciales locales del cliente nativo de iOS."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


APP_HOME = Path(os.environ.get("OF_IOS_HOME", Path.home() / "OFDownloader"))
PRIVATE_DIR = APP_HOME / ".private"
AUTH_PATH = PRIVATE_DIR / "auth.json"
RULES_PATH = PRIVATE_DIR / "dynamic-rules.json"
DOWNLOAD_DIR = APP_HOME / "Descargas"
MAX_AUTH_SIZE = 32 * 1024
REQUIRED_AUTH_KEYS = ("sess", "auth_id", "x-bc", "user_agent")


class ConfigError(RuntimeError):
    """Error seguro de configuración; nunca debe incluir valores secretos."""


def _secure_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    try:
        os.chmod(temporary, 0o600)
    except OSError:
        pass
    temporary.replace(path)


def parse_auth_export(data: Any) -> dict[str, str]:
    if not isinstance(data, dict):
        raise ConfigError("El archivo de acceso no contiene un objeto JSON.")
    source = data.get("auth", data)
    if not isinstance(source, dict):
        raise ConfigError("El bloque auth del archivo no es válido.")

    values: dict[str, str] = {}
    for key in REQUIRED_AUTH_KEYS:
        value = source.get(key)
        if not isinstance(value, (str, int)) or not str(value).strip():
            raise ConfigError(f"Falta el campo obligatorio: {key}.")
        values[key] = str(value).strip()
    if not values["auth_id"].isdigit():
        raise ConfigError("auth_id debe contener únicamente números.")
    return values


def auth_candidates() -> list[Path]:
    """Rutas habituales de Archivos/a-Shell, en orden de preferencia."""
    configured = os.environ.get("OF_IOS_AUTH")
    candidates = [
        Path(configured).expanduser() if configured else None,
        Path.cwd() / "OFBackup-auth.json",
        Path.cwd() / "Downloads" / "OFBackup-auth.json",
        Path.home() / "OFBackup-auth.json",
        Path.home() / "Downloads" / "OFBackup-auth.json",
        Path.home() / "Documents" / "OFBackup-auth.json",
    ]
    seen: set[Path] = set()
    result: list[Path] = []
    for candidate in candidates:
        if candidate is not None:
            resolved = candidate.expanduser()
            if resolved not in seen:
                seen.add(resolved)
                result.append(resolved)
    return result


def find_auth_export() -> Path | None:
    for candidate in auth_candidates():
        if candidate.is_file():
            return candidate
    return None


def import_auth(path: Path | None = None) -> Path:
    path = (path or find_auth_export())
    if path is None:
        raise ConfigError(
            "No se encontró OFBackup-auth.json. Ponlo en la carpeta de a-Shell "
            "o indica la ruta: of importar RUTA"
        )
    path = path.expanduser().resolve()
    if not path.is_file():
        raise ConfigError("No se encontró el archivo JSON indicado.")
    size = path.stat().st_size
    if size <= 0 or size > MAX_AUTH_SIZE:
        raise ConfigError("El archivo JSON está vacío o es demasiado grande.")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ConfigError("No se pudo leer el archivo JSON.") from exc
    values = parse_auth_export(data)
    _secure_write(AUTH_PATH, values)
    return AUTH_PATH


def load_auth() -> dict[str, str]:
    if not AUTH_PATH.is_file():
        raise ConfigError(
            "No hay acceso importado. Ejecuta: of-ios importar RUTA_DEL_JSON"
        )
    try:
        data = json.loads(AUTH_PATH.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ConfigError("La configuración privada no se puede leer.") from exc
    return parse_auth_export(data)
