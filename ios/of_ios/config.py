"""Configuración y credenciales locales del cliente nativo de iOS."""

from __future__ import annotations

import json
import os
from http.cookies import SimpleCookie
from pathlib import Path
from typing import Any


APP_HOME = Path(os.environ.get("OF_IOS_HOME", Path.home() / "OFDownloader"))
PRIVATE_DIR = APP_HOME / ".private"
AUTH_PATH = PRIVATE_DIR / "auth.json"
RULES_PATH = PRIVATE_DIR / "dynamic-rules.json"
DOWNLOAD_DIR = APP_HOME / "Descargas"
MAX_AUTH_SIZE = 64 * 1024
REQUIRED_AUTH_KEYS = ("sess", "auth_id", "x-bc", "user_agent")
AUTH_FIELD_LIMITS = {
    "sess": 4096,
    "auth_id": 32,
    "x-bc": 512,
    "user_agent": 1024,
}


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


def _cookie_values(raw: str) -> dict[str, str]:
    """Extrae solo nombres de autenticación de un header Cookie."""
    raw = raw.strip()
    if raw.lower().startswith("cookie:"):
        raw = raw.split(":", 1)[1].strip()

    values: dict[str, str] = {}
    jar = SimpleCookie()
    try:
        jar.load(raw)
    except Exception:
        # Algunos exportadores no escapan exactamente como SimpleCookie espera;
        # el parseo por partes de abajo cubre ese caso sin fallar toda la carga.
        pass
    for name, morsel in jar.items():
        values[name] = morsel.value

    for part in raw.split(";"):
        if "=" not in part:
            continue
        name, value = part.split("=", 1)
        name = name.strip()
        if name:
            values.setdefault(name, value.strip().strip('"'))
    return values


def _put_value(values: dict[str, str], target: str, value: Any) -> None:
    """Añade un valor compatible sin aceptar booleanos ni objetos."""
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        return
    text = str(value).strip()
    if text:
        values[target] = text


def _merge_dict_values(values: dict[str, str], source: dict[str, Any]) -> None:
    """Normaliza las variantes de nombres emitidas por los exportadores."""
    for source_key, target_key in (
        ("sess", "sess"),
        ("auth_id", "auth_id"),
        ("x-bc", "x-bc"),
        ("x_bc", "x-bc"),
        ("bcToken", "x-bc"),
        ("bc_token", "x-bc"),
        ("user_agent", "user_agent"),
        ("userAgent", "user_agent"),
        ("User-Agent", "user_agent"),
    ):
        _put_value(values, target_key, source.get(source_key))


def _is_onlyfans_domain(value: Any) -> bool:
    domain = str(value or "").lower().lstrip(".")
    return domain == "onlyfans.com" or domain.endswith(".onlyfans.com")


def _validate_auth_values(values: dict[str, str]) -> dict[str, str]:
    """Valida y limita los cuatro valores que se guardarán localmente."""
    missing = [key for key in REQUIRED_AUTH_KEYS if not values.get(key)]
    if missing:
        readable = ["User-Agent" if key == "user_agent" else key for key in missing]
        raise ConfigError(
            "El archivo no trae todos los datos necesarios. "
            f"Faltan: {', '.join(readable)}."
        )

    cleaned: dict[str, str] = {}
    for key, limit in AUTH_FIELD_LIMITS.items():
        value = values.get(key)
        if not isinstance(value, str):
            raise ConfigError(f"El campo {key} no es válido.")
        value = value.strip()
        if not value or len(value) > limit or any(ord(char) < 32 for char in value):
            raise ConfigError(f"El campo {key} no tiene un formato válido.")
        cleaned[key] = value
    if not cleaned["auth_id"].isdigit():
        raise ConfigError("auth_id debe contener únicamente números.")
    return cleaned


def parse_auth_export(data: Any) -> dict[str, str]:
    values: dict[str, str] = {}

    if isinstance(data, dict):
        source = data.get("auth", data)
        if not isinstance(source, dict):
            raise ConfigError("El bloque auth del archivo no es válido.")
        cookie = source.get("cookie")
        if not isinstance(cookie, str):
            cookie = data.get("cookie")
        if isinstance(cookie, str):
            _merge_dict_values(values, _cookie_values(cookie))
        _merge_dict_values(values, source)
        # Un exportador puede dejar User-Agent fuera del bloque auth.
        if source is not data:
            _merge_dict_values(values, data)
    elif isinstance(data, list):
        allowed = {
            "sess": "sess",
            "auth_id": "auth_id",
            "x-bc": "x-bc",
            "x_bc": "x-bc",
            "bcToken": "x-bc",
            "bc_token": "x-bc",
            "user_agent": "user_agent",
            "userAgent": "user_agent",
            "User-Agent": "user_agent",
        }
        for item in data:
            if not isinstance(item, dict):
                continue
            # Las listas de cookies se aceptan únicamente si el dominio es
            # OnlyFans; así no se importa por accidente una cookie ajena.
            name = str(item.get("name", ""))
            if _is_onlyfans_domain(item.get("domain")) and name in allowed:
                _put_value(values, allowed[name], item.get("value"))
            # Algunos exportadores colocan User-Agent como propiedad del
            # elemento y no como una cookie; esa propiedad no necesita dominio.
            for source_key in ("user_agent", "userAgent", "User-Agent"):
                _put_value(values, "user_agent", item.get(source_key))
    elif isinstance(data, str):
        _merge_dict_values(values, _cookie_values(data))
    else:
        raise ConfigError("El archivo de acceso no contiene un JSON compatible.")

    return _validate_auth_values(values)


def auth_candidates() -> list[Path]:
    """Rutas habituales de Archivos/a-Shell, incluyendo nombres personalizados."""
    configured = os.environ.get("OF_IOS_AUTH")
    directories = [
        Path.cwd(),
        Path.cwd() / "Downloads",
        Path.home(),
        Path.home() / "Downloads",
        Path.home() / "Documents",
    ]
    candidates: list[Path | None] = [
        Path(configured).expanduser() if configured else None,
    ]
    for directory in directories:
        candidates.append(directory / "OFBackup-auth.json")
        try:
            # El nombre exportado puede ser un UUID u otro nombre elegido en
            # Archivos. Solo se inspecciona un nivel y luego se valida el JSON.
            candidates.extend(sorted(directory.glob("*.json"), key=lambda item: item.name.lower()))
        except (OSError, RuntimeError):
            continue

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
        try:
            if not candidate.is_file() or candidate.stat().st_size <= 0:
                continue
            data = json.loads(candidate.read_text(encoding="utf-8"))
            parse_auth_export(data)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ConfigError):
            continue
        return candidate
    return None


def import_auth(path: Path | None = None) -> Path:
    if path is not None:
        path = path.expanduser().resolve()
        values = _read_auth_file(path)
        _secure_write(AUTH_PATH, values)
        return AUTH_PATH

    existing = False
    valid: list[tuple[Path, dict[str, str]]] = []
    for candidate in auth_candidates():
        try:
            if not candidate.is_file():
                continue
            existing = True
            values = _read_auth_file(candidate)
        except ConfigError:
            continue
        valid.append((candidate, values))

    if len(valid) == 1:
        _secure_write(AUTH_PATH, valid[0][1])
        return AUTH_PATH
    if len(valid) > 1:
        names = ", ".join(candidate.name for candidate, _ in valid[:5])
        if len(valid) > 5:
            names += ", …"
        raise ConfigError(
            f"Se encontraron {len(valid)} JSON de acceso ({names}). "
            "Indica la ruta exacta: of importar RUTA"
        )

    if existing:
        raise ConfigError(
            "Se encontraron JSON, pero ninguno contiene los cuatro campos de acceso. "
            "Indica la ruta correcta: of importar RUTA"
        )
    raise ConfigError(
        "No se encontró un JSON de acceso. Ponlo en la carpeta de a-Shell "
        "o indica la ruta: of importar RUTA"
    )


def _read_auth_file(path: Path) -> dict[str, str]:
    """Lee y valida un archivo sin conservar su contenido completo."""
    if not path.is_file():
        raise ConfigError("No se encontró el archivo JSON indicado.")
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise ConfigError("No se pudo consultar el archivo JSON.") from exc
    if size <= 0 or size > MAX_AUTH_SIZE:
        raise ConfigError("El archivo JSON está vacío o es demasiado grande.")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ConfigError("No se pudo leer el archivo JSON.") from exc
    return parse_auth_export(data)


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
