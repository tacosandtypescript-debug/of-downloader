#!/usr/bin/env python3
"""Interfaz de terminal de OF Downloader para Termux, Linux y Windows."""

from __future__ import annotations

import getpass
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import re
import secrets
import shutil
import socket
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from http.cookies import SimpleCookie
from pathlib import Path
from urllib.parse import urlparse


APP_VERSION = "2.13.0"
OFSCRAPER_VERSION = "3.14.7"
DEFAULT_APP_TOKEN = "33d57ade8c02dbc5a333db99ff9ae26a"
AUTH_EXPORT_FORMAT = "ofbackup-auth"
AUTH_EXPORT_VERSION = 1
AUTH_EXPORT_FILENAME = "OFBackup-auth.json"
MAX_AUTH_EXPORT_SIZE = 64 * 1024
IMPORT_REQUEST_EXIT = 42
APP_UPDATE_REQUEST_EXIT = 43

HOME = Path.home()
APP_DIR = HOME / ".config" / "ofbackup"
STATE_PATH = APP_DIR / "settings.json"
OFSCRAPER_DIR = HOME / ".config" / "ofscraper"
OFSCRAPER_CONFIG_PATH = OFSCRAPER_DIR / "config.json"
AUTH_PATH = OFSCRAPER_DIR / "main_profile" / "auth.json"
DOWNLOAD_LOG_PATH = APP_DIR / "ultima-descarga.log"
PUBLIC_DOWNLOAD_LOG_NAME = "ultima-descarga.log"
PROFILE_TEST_LOG_NAME = "prueba-perfil.log"
SUBSCRIPTIONS_LOG_NAME = "perfiles-suscritos.log"
SUBSCRIPTIONS_SENTINEL = "OFDOWNLOADER_SUBSCRIPTIONS_JSON:"
DRIVE_LOG_NAME = "google-drive.log"
DRIVE_QUEUE_PATH = APP_DIR / "drive-pending.json"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".avif"}
VIDEO_EXTENSIONS = {".mp4", ".m4v", ".mov", ".webm", ".mkv", ".avi", ".ts"}
PARTIAL_EXTENSIONS = {".part", ".partial", ".tmp", ".temp", ".download"}

AUTH_TEST_SCRIPT = r"""
import sys

try:
    from ofscraper.main.open import load
    import ofscraper.managers.manager as manager
    from ofscraper.data.api import me

    load.systemSet()
    load.settings_loader()
    load.setdate()
    load.readConfig()
    load.make_folder()
    manager.Manager = manager.mainManager()
    account = me.scrape_user()
    if isinstance(account, dict) and account.get("isAuth") is True:
        print("OFBACKUP_AUTH_OK")
        raise SystemExit(0)
    print("OFBACKUP_AUTH_REJECTED")
    raise SystemExit(3)
except SystemExit:
    raise
except Exception as exc:
    print(f"OFBACKUP_AUTH_ERROR:{type(exc).__name__}", file=sys.stderr)
    raise SystemExit(4)
"""

PROFILE_TEST_SCRIPT = r"""
import sys

username = sys.argv[1]

try:
    from ofscraper.main.open import load
    import ofscraper.managers.manager as manager
    from ofscraper.data.api import archive, highlights, pinned, profile, streams, timeline

    load.systemSet()
    load.settings_loader()
    load.setdate()
    load.readConfig()
    load.make_folder()
    manager.Manager = manager.mainManager()
    data = profile.scrape_profile(username)
    if not isinstance(data, dict) or not data.get("id"):
        print("OFDOWNLOADER_PROFILE_EMPTY")
        raise SystemExit(3)
    if data.get("username") == "deleted":
        print("OFDOWNLOADER_PROFILE_DELETED")
        raise SystemExit(4)

    seen = set()
    counts = {"photos": 0, "videos": 0}
    counted_posts = set()
    partial_errors = []

    def walk_media(value):
        if isinstance(value, dict):
            media = value.get("media")
            if isinstance(media, list):
                for item in media:
                    yield item
            for key in ("preview", "linkedPost", "post"):
                nested = value.get(key)
                if isinstance(nested, (dict, list)):
                    yield from walk_media(nested)
        elif isinstance(value, list):
            for item in value:
                yield from walk_media(item)

    def count_posts(area, posts):
        if not isinstance(posts, list):
            return
        for post in posts:
            if isinstance(post, dict) and post.get("id") is not None:
                counted_posts.add(str(post.get("id")))
            for media in walk_media(post):
                if not isinstance(media, dict):
                    continue
                media_id = media.get("id") or media.get("media_id") or media.get("source", {}).get("source")
                media_type = str(media.get("type") or media.get("media_type") or media.get("mediatype") or "").lower()
                key = str(media_id or f"{area}:{media_type}:{len(seen)}")
                if key in seen:
                    continue
                seen.add(key)
                if media_type in {"photo", "image", "images"}:
                    counts["photos"] += 1
                elif media_type in {"video", "videos"}:
                    counts["videos"] += 1

    def try_area(area, func, *args, **kwargs):
        try:
            count_posts(area, func(*args, **kwargs))
        except Exception as exc:
            partial_errors.append(f"{area}:{type(exc).__name__}")

    model_id = data.get("id")
    model_username = data.get("username") or username
    with manager.Manager.session.get_ofsession() as c:
        try_area("timeline", timeline.get_timeline_posts, model_id, model_username, c=c)
        try_area("archived", archive.get_archived_posts, model_id, model_username, c=c)
        try_area("pinned", pinned.get_pinned_posts, model_id, c=c)
        try_area("stories", highlights.get_stories_post, model_id, c=c)
        try_area("streams", streams.get_streams_posts, model_id, model_username, c=c)

    photos = counts["photos"] if seen else data.get("photosCount", 0)
    videos = counts["videos"] if seen else data.get("videosCount", 0)
    posts = len(counted_posts) if counted_posts else data.get("postsCount", 0)
    print(
        "OFDOWNLOADER_PROFILE_OK "
        f"username={data.get('username', '')} "
        f"id={data.get('id', '')} "
        f"posts={posts} "
        f"photos={photos} "
        f"videos={videos} "
        f"archived={data.get('archivedPostsCount', 0)} "
        f"counted={len(seen)} "
        f"partial={1 if partial_errors else 0}"
    )
    raise SystemExit(0)
except SystemExit:
    raise
except Exception as exc:
    print(f"OFDOWNLOADER_PROFILE_ERROR:{type(exc).__name__}", file=sys.stderr)
    raise SystemExit(5)
"""

SUBSCRIPTIONS_LIST_SCRIPT = r"""
import json
import sys

try:
    from ofscraper.main.open import load
    import ofscraper.managers.manager as manager
    from ofscraper.data.api.subscriptions import subscriptions

    load.systemSet()
    load.settings_loader()
    load.setdate()
    load.readConfig()
    load.make_folder()
    manager.Manager = manager.mainManager()
    data = subscriptions.get_all_subscriptions(0, account="active")
    if not isinstance(data, list):
        data = []
    payload = "OFDOWNLOADER_SUBSCRIPTIONS_JSON:" + json.dumps(data, ensure_ascii=False) + "\n"
    sys.stdout.buffer.write(payload.encode("utf-8", errors="replace"))
    sys.stdout.flush()
    raise SystemExit(0)
except SystemExit:
    raise
except Exception as exc:
    print(f"OFDOWNLOADER_SUBSCRIPTIONS_ERROR:{type(exc).__name__}", file=sys.stderr)
    raise SystemExit(5)
"""


class UserError(RuntimeError):
    """Error que se puede mostrar directamente al usuario."""


def _chmod(path: Path, mode: int) -> None:
    if os.name != "nt":
        path.chmod(mode)


def secure_write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _chmod(path.parent, 0o700)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    _chmod(temporary, 0o600)
    temporary.replace(path)
    _chmod(path, 0o600)


def read_json(path: Path, default: dict | None = None) -> dict:
    if not path.exists():
        return dict(default or {})
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise UserError(f"No se pudo leer {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise UserError(f"El archivo {path} no contiene un objeto JSON válido.")
    return value


def default_download_dir() -> Path:
    configured = os.getenv("OFDOWNLOADER_DOWNLOAD_DIR")
    if configured:
        return Path(configured).expanduser()
    shared = HOME / "storage" / "downloads"
    desktop = HOME / "Downloads"
    return (shared if shared.exists() else desktop) / "OFDownloader"


def default_auth_export_path() -> Path:
    configured = os.getenv("OFDOWNLOADER_AUTH_EXPORT")
    if configured:
        return Path(configured).expanduser()
    if os.name == "nt":
        return HOME / "Downloads" / AUTH_EXPORT_FILENAME
    return HOME / "storage" / "downloads" / AUTH_EXPORT_FILENAME


EXPORTED_AUTH_PATH = default_auth_export_path()


def get_state() -> dict:
    state = read_json(STATE_PATH)
    state.setdefault("download_dir", str(default_download_dir()))
    state.setdefault("username", "")
    state.setdefault("drive_enabled", False)
    state.setdefault("drive_remote", "gdrive")
    state.setdefault("drive_folder", "OFDownloader")
    state.setdefault("drive_upload_after_download", True)
    state.setdefault("drive_delete_after_upload", False)
    return state


def save_state(state: dict) -> None:
    secure_write_json(STATE_PATH, state)


def parse_cookie_header(raw: str) -> dict[str, str]:
    raw = raw.strip()

    # Formato JSON exportado por extensiones y administradores de cookies.
    # Solo se aceptan cookies de OnlyFans y solo se conservan los dos valores
    # necesarios para autenticar OF-Scraper.
    try:
        exported = json.loads(raw)
    except json.JSONDecodeError:
        exported = None
    if isinstance(exported, dict):
        source = exported.get("auth", exported)
        if not isinstance(source, dict):
            return {}
        values = {}
        cookie = source.get("cookie")
        if isinstance(cookie, str):
            values.update(parse_cookie_header(cookie))
        for source_key, target_key in (
            ("sess", "sess"),
            ("auth_id", "auth_id"),
            ("x-bc", "x-bc"),
            ("x_bc", "x-bc"),
            ("user_agent", "user_agent"),
        ):
            value = source.get(source_key)
            if isinstance(value, str) and value.strip():
                values[target_key] = value.strip()
        return values

    if isinstance(exported, list):
        allowed_names = {"sess", "auth_id"}
        values = {}
        for item in exported:
            if not isinstance(item, dict):
                continue
            domain = str(item.get("domain", "")).lower().lstrip(".")
            name = str(item.get("name", ""))
            value = item.get("value")
            if domain == "onlyfans.com" and name in allowed_names and isinstance(value, str):
                values[name] = value
        return values

    raw = re.sub(r"^cookie\s*:\s*", "", raw, flags=re.IGNORECASE)
    values: dict[str, str] = {}
    jar = SimpleCookie()
    try:
        jar.load(raw)
        values.update({key: morsel.value for key, morsel in jar.items()})
    except Exception:
        pass

    # Algunos valores copiados desde navegadores no cumplen por completo RFC 6265.
    for part in raw.split(";"):
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        key = key.strip()
        if key:
            values.setdefault(key, value.strip().strip('"'))
    return values


def _clean_auth_value(name: str, value: object, max_length: int) -> str:
    if not isinstance(value, str):
        raise UserError(f"El campo {name} no es texto.")
    value = value.strip()
    if not value:
        raise UserError(f"Falta el campo {name}.")
    if len(value) > max_length or any(ord(char) < 32 for char in value):
        raise UserError(f"El campo {name} no tiene un formato válido.")
    return value


def validate_auth_values(values: dict[str, str]) -> dict[str, str]:
    required = ("sess", "auth_id", "x-bc", "user_agent")
    missing = [key for key in required if not values.get(key)]
    if missing:
        readable = ["User-Agent" if key == "user_agent" else key for key in missing]
        raise UserError(
            "El archivo no trae todos los datos necesarios. "
            f"Falta: {', '.join(readable)}. "
            "Exporta de nuevo con OF Downloader Exporter desde la misma sesion."
        )
    cleaned = {
        "sess": _clean_auth_value("sess", values.get("sess"), 4096),
        "auth_id": _clean_auth_value("auth_id", values.get("auth_id"), 32),
        "x-bc": _clean_auth_value("x-bc", values.get("x-bc"), 512),
        "user_agent": _clean_auth_value("user_agent", values.get("user_agent"), 1024),
    }
    if not cleaned["auth_id"].isdigit():
        raise UserError("auth_id debe contener Ãºnicamente nÃºmeros.")
    return cleaned


def parse_auth_export(data: object) -> dict[str, str]:
    if not isinstance(data, dict):
        cookies = parse_cookie_header(json.dumps(data, ensure_ascii=False))
        return validate_auth_values(cookies)
    if data.get("format") != AUTH_EXPORT_FORMAT:
        cookies = parse_cookie_header(json.dumps(data, ensure_ascii=False))
        if cookies:
            return validate_auth_values(cookies)
        raise UserError("El archivo no fue creado por OF Downloader Exporter.")
    if data.get("version") != AUTH_EXPORT_VERSION:
        raise UserError("La versión del archivo de acceso no es compatible.")
    created_at = data.get("created_at")
    if not isinstance(created_at, str) or len(created_at) > 64:
        raise UserError("El archivo no contiene una fecha de creación válida.")
    try:
        datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise UserError("La fecha de creación del archivo no es válida.") from exc
    auth = data.get("auth")
    if not isinstance(auth, dict):
        raise UserError("El archivo no contiene la sección auth.")

    values = {
        "sess": _clean_auth_value("sess", auth.get("sess"), 4096),
        "auth_id": _clean_auth_value("auth_id", auth.get("auth_id"), 32),
        "x-bc": _clean_auth_value("x-bc", auth.get("x-bc"), 512),
        "user_agent": _clean_auth_value(
            "user_agent", auth.get("user_agent"), 1024
        ),
    }
    if not values["auth_id"].isdigit():
        raise UserError("auth_id debe contener únicamente números.")
    return values


def load_auth_export(path: Path) -> tuple[dict[str, str], str]:
    path = path.expanduser()
    try:
        if not path.is_file():
            raise UserError("El archivo seleccionado no existe.")
        size = path.stat().st_size
        if size <= 0 or size > MAX_AUTH_EXPORT_SIZE:
            raise UserError("El archivo seleccionado está vacío o es demasiado grande.")
        raw = path.read_bytes()
        data = json.loads(raw.decode("utf-8"))
    except UserError:
        raise
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise UserError(f"No se pudo leer el archivo de acceso: {exc}") from exc
    return parse_auth_export(data), hashlib.sha256(raw).hexdigest()


def credentials_payload(values: dict[str, str]) -> dict[str, str]:
    return {
        "sess": values["sess"],
        "auth_id": values["auth_id"],
        "auth_uid": "",
        "user_agent": values["user_agent"],
        "x-bc": values["x-bc"],
        "app-token": DEFAULT_APP_TOKEN,
    }


def save_credentials(values: dict[str, str], username: str = "") -> None:
    secure_write_json(AUTH_PATH, credentials_payload(values))
    state = get_state()
    if username:
        state["username"] = username
    save_state(state)
    write_ofscraper_config(state)


def _file_sha256(path: Path) -> str | None:
    try:
        if not path.is_file() or path.stat().st_size > MAX_AUTH_EXPORT_SIZE:
            return None
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def import_credentials_file(path: Path) -> None:
    values, selected_hash = load_auth_export(path)
    save_credentials(values)

    original_removed = False
    if _file_sha256(EXPORTED_AUTH_PATH) == selected_hash:
        try:
            EXPORTED_AUTH_PATH.unlink()
            original_removed = True
        except OSError:
            pass

    print("\n✓ Archivo válido y datos de acceso guardados.")
    print("Solo se conservaron sess, auth_id, x-bc y User-Agent.")
    if original_removed:
        print("El archivo original se eliminó de Descargas.")
    else:
        print(
            f"AVISO: elimina manualmente {AUTH_EXPORT_FILENAME} de Descargas "
            "si todavía aparece."
        )
    print("Comprueba ahora la sesión ejecutando: of probar")


def local_network_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def receive_credentials_locally(port: int = 8765, timeout: int = 300) -> int:
    code = f"{secrets.randbelow(1_000_000):06d}"
    received: dict[str, object] = {"done": False, "error": ""}

    class ReceiverHandler(BaseHTTPRequestHandler):
        server_version = "OFDownloaderCookieReceiver/1.0"

        def log_message(self, _format: str, *_args: object) -> None:
            return

        def _send_json(self, status: int, payload: dict[str, object]) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_OPTIONS(self) -> None:  # noqa: N802
            self._send_json(200, {"ok": True})

        def do_GET(self) -> None:  # noqa: N802
            self._send_json(
                200,
                {
                    "ok": True,
                    "app": "OF Downloader",
                    "version": APP_VERSION,
                    "message": "Receptor activo. Envia POST /upload con code y auth.",
                },
            )

        def do_POST(self) -> None:  # noqa: N802
            if self.path.rstrip("/") != "/upload":
                self._send_json(404, {"ok": False, "error": "ruta invalida"})
                return
            length_header = self.headers.get("Content-Length", "0")
            try:
                length = int(length_header)
            except ValueError:
                self._send_json(400, {"ok": False, "error": "tamano invalido"})
                return
            if length <= 0 or length > MAX_AUTH_EXPORT_SIZE:
                self._send_json(413, {"ok": False, "error": "archivo demasiado grande"})
                return
            try:
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                self._send_json(400, {"ok": False, "error": "json invalido"})
                return
            if not isinstance(payload, dict) or str(payload.get("code", "")) != code:
                self._send_json(403, {"ok": False, "error": "codigo incorrecto"})
                return
            try:
                values = parse_auth_export(payload.get("auth"))
                save_credentials(values)
            except UserError as exc:
                message = str(exc)
                received["error"] = message
                self._send_json(400, {"ok": False, "error": message})
                return
            received["done"] = True
            self._send_json(
                200,
                {
                    "ok": True,
                    "message": "Datos guardados. Ejecuta of probar.",
                },
            )

    host = "0.0.0.0"
    try:
        server = ThreadingHTTPServer((host, port), ReceiverHandler)
    except OSError as exc:
        raise UserError(f"No se pudo abrir el receptor local en puerto {port}: {exc}") from exc

    server.timeout = 0.5
    ip = local_network_ip()
    expires_at = time.monotonic() + timeout
    print("\nRECIBIR COOKIE LOCAL")
    print("1. Abre OnlyFans en el navegador donde esta la extension.")
    print("2. Pulsa la extension y usa Enviar a OF Downloader.")
    print("3. Escribe esta URL y este codigo.")
    print()
    print(f"URL local: http://{ip}:{port}")
    print(f"Codigo:    {code}")
    print(f"Tiempo:    {timeout // 60} minutos")
    print()
    print("Seguridad: un solo uso, no imprime secretos y se apaga solo.")
    print("Usalo en Wi-Fi de confianza o en hotspot propio.")
    try:
        while time.monotonic() < expires_at and not received["done"]:
            server.handle_request()
    finally:
        server.server_close()
    if received["done"]:
        print("\n✓ Archivo recibido y datos de acceso guardados.")
        print("Solo se conservaron sess, auth_id, x-bc y User-Agent.")
        print("Comprueba ahora la sesion ejecutando: of probar")
        return 0
    print("\nNo se recibio ningun archivo antes de que venciera el tiempo.")
    return 1


def user_supplied_path(value: str) -> Path:
    value = value.strip().strip('"').strip("'")
    return Path(os.path.expandvars(value)).expanduser()


def select_auth_export_file() -> Path | None:
    """Abre un selector nativo para elegir el JSON exportado por la extension."""
    try:
        import tkinter as tk
        from tkinter import filedialog
    except Exception:
        return None

    try:
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        downloads = HOME / "Downloads"
        initial_dir = downloads if downloads.exists() else HOME
        selected = filedialog.askopenfilename(
            title="Selecciona OFBackup-auth.json",
            initialdir=str(initial_dir),
            filetypes=(
                ("OF Downloader auth", "OFBackup-auth*.json"),
                ("Archivos JSON", "*.json"),
                ("Todos los archivos", "*.*"),
            ),
        )
        root.destroy()
    except Exception:
        return None
    if not selected:
        return None
    return Path(selected)


def import_default_auth_export(*, prompt_if_missing: bool = True) -> None:
    selected = select_auth_export_file()
    if selected is not None:
        import_credentials_file(selected)
        return

    default_path = default_auth_export_path()
    if default_path.is_file():
        import_credentials_file(default_path)
        return
    if not prompt_if_missing:
        import_credentials_file(default_path)
        return
    print(f"No encontre el archivo en: {default_path}")
    print("Si lo guardaste con otro nombre o en otra carpeta, pega la ruta completa.")
    print(r"Ejemplo Windows: C:\Users\TU_USUARIO\Downloads\OFBackup-auth.json")
    value = input("Ruta del archivo o Enter para cancelar: ").strip()
    if not value:
        raise UserError(
            f"Pon {AUTH_EXPORT_FILENAME} en Descargas o usa: of importar RUTA_DEL_ARCHIVO"
        )
    import_credentials_file(user_supplied_path(value))


def hidden_prompt(label: str) -> str:
    try:
        return getpass.getpass(label).strip()
    except (EOFError, KeyboardInterrupt):
        raise
    except Exception:
        return input(label).strip()


def json_cookie_prompt(*, allow_object: bool = False) -> str:
    print("\nPega ahora el JSON completo.")
    print("Puede ocupar muchas líneas; el programa detectará automáticamente el final.")
    lines: list[str] = []
    while True:
        try:
            line = input()
        except EOFError as exc:
            raise UserError("El JSON terminó antes de estar completo.") from exc
        lines.append(line)
        raw = "\n".join(lines).strip()
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            continue
        accepted = (list, dict) if allow_object else (list,)
        if not isinstance(value, accepted):
            raise UserError("El formato del JSON no es compatible.")
        return raw


def configure_credentials() -> int:
    print("\nCONECTAR MI CUENTA")
    print("Usa el archivo OFBackup-auth.json creado por la extension del navegador.")
    print("Si necesitas instrucciones para sacarlo y moverlo, ejecuta: of cookie ayuda")
    platform_name = os.getenv("OFDOWNLOADER_PLATFORM", "TERMUX").upper()
    if platform_name in {"LINUX", "WINDOWS"}:
        print("Abriendo el explorador para elegir OFBackup-auth.json...")
        import_default_auth_export()
        return 0
    print("Abriendo el selector Android para elegir OFBackup-auth.json...")
    return IMPORT_REQUEST_EXIT


def write_ofscraper_config(state: dict | None = None) -> None:
    state = state or get_state()
    destination = Path(state["download_dir"]).expanduser()
    destination.mkdir(parents=True, exist_ok=True)

    data = read_json(OFSCRAPER_CONFIG_PATH, {"main_profile": "main_profile"})
    data["main_profile"] = "main_profile"
    # OF-Scraper 3.14.7 llama por error a of_env.getattr() con dos argumentos
    # cuando falta esta clave. Guardar el valor vacío evita ese fallo upstream
    # sin modificar los archivos del paquete instalado.
    if data.get("discord") is None:
        data["discord"] = ""
    file_options = data.setdefault("file_options", {})
    file_options.update(
        {
            "save_location": str(destination),
            "dir_format": "{model_username}/{mediatype}/",
            "file_format": "{date}_{post_id}_{media_id}.{ext}",
            "date": "YYYY-MM-DD",
        }
    )
    secure_write_json(OFSCRAPER_CONFIG_PATH, data)


def credentials_ready() -> bool:
    try:
        data = read_json(AUTH_PATH)
    except UserError:
        return False
    return all(data.get(key) for key in ("sess", "auth_id", "x-bc", "user_agent"))


def require_credentials() -> None:
    if credentials_ready():
        return
    print("Todavía no hay credenciales configuradas.")
    if configure_credentials() == IMPORT_REQUEST_EXIT:
        raise UserError("Vuelve al menú y usa Conectar mi cuenta para abrir el selector.")


def _status_text(message: str, color: str) -> str:
    return styled(message, color)


PALETTE = {
    "cyan": "38;2;0;175;240",
    "blue": "38;2;0;140;207",
    "navy": "38;2;0;92;143",
    "white": "38;2;245;250;255",
    "muted": "38;2;148;180;200",
    "green": "38;2;32;213;166",
    "yellow": "38;2;255;200;87",
    "red": "38;2;255;77;103",
}

MENU_LOGO_LINES = (
    "⣠⣾⣿⣷⣦⣴⣿⣿⣿⠟",
    "⣿⣿⠁⠈⣿⣿⣿⡿⠋",
    "⢿⣿⣦⣴⣿⣿⣿⣶⡄",
    "⠀⠻⣿⣿⡿⠟⠉",
)


def ansi_supported() -> bool:
    if os.getenv("NO_COLOR"):
        return False
    if not sys.stdout.isatty():
        return False
    if os.name != "nt":
        return True
    return bool(
        os.getenv("WT_SESSION")
        or os.getenv("ANSICON")
        or os.getenv("ConEmuANSI", "").upper() == "ON"
        or os.getenv("TERM_PROGRAM")
    )


def colors_enabled() -> bool:
    return ansi_supported()


def styled(message: str, color: str = "white", *, bold: bool = False) -> str:
    if not colors_enabled():
        return message
    weight = "1;" if bold else ""
    return f"\033[{weight}{PALETTE[color]}m{message}\033[0m"


def menu_option(number: str, label: str) -> None:
    badge = styled(f"[{number}]", "cyan", bold=True)
    print(f"  {badge} {styled(label, 'white')}")


def menu_banner_line(message: str, color: str = "cyan", *, bold: bool = False) -> None:
    if len(message) > 44:
        raise ValueError("La línea del encabezado supera 44 caracteres.")
    border = styled("│", "cyan", bold=True)
    print(border + styled(message.ljust(44), color, bold=bold) + border)


def menu_brand_line(label: str, logo_line: str) -> None:
    """Deja espacio extra al emblema para fuentes Android de ancho doble."""
    left = f"  {label}".ljust(20)
    print(styled(left, "white", bold=bool(label)) + styled(logo_line, "blue", bold=True))


def repository_update_badge(status: str | None = None) -> str:
    status = status or os.getenv("OFDOWNLOADER_UPDATE_STATUS", "unknown")
    if status == "available":
        return styled("● ACTUALIZACIÓN DISPONIBLE", "yellow", bold=True)
    if status == "current":
        return styled("● AL DÍA", "green", bold=True)
    if status == "diverged":
        return styled("● REVISAR REPOSITORIO", "yellow", bold=True)
    return styled("● NO COMPROBADA", "muted")


def test_credentials(timeout: int = 60) -> int:
    """Comprueba la sesión con una consulta mínima y sin descargar contenido."""
    if not credentials_ready():
        print("Todavía no hay credenciales configuradas.")
        print("Abriré el selector para que elijas OFBackup-auth.json.")
        return IMPORT_REQUEST_EXIT
    write_ofscraper_config()
    ofscraper_binary()
    print("\n✓ Archivo cargado: contiene los 4 datos necesarios.")
    print("Probando la sesión con OnlyFans…")
    print("No se descargará contenido ni se mostrarán datos privados.")

    try:
        process = subprocess.Popen(
            [sys.executable, "-c", AUTH_TEST_SCRIPT],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError as exc:
        raise UserError(f"No se pudo iniciar la prueba de acceso: {exc}") from exc

    deadline = time.monotonic() + timeout
    frames = ("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏")
    frame = 0
    interactive = sys.stdout.isatty()
    if not interactive:
        print("Esperando respuesta (máximo 60 segundos)…")

    while process.poll() is None and time.monotonic() < deadline:
        if interactive:
            remaining = max(0, int(deadline - time.monotonic()))
            print(
                f"\r{frames[frame % len(frames)]} Consultando… {remaining:02d}s ",
                end="",
                flush=True,
            )
            frame += 1
        time.sleep(0.25)

    if process.poll() is None:
        process.terminate()
        try:
            stdout, stderr = process.communicate(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()
        if interactive:
            print("\r" + " " * 38 + "\r", end="", flush=True)
        print(_status_text("\n✗ LA PRUEBA TARDÓ DEMASIADO", "red"))
        print("La cookie sí está cargada, pero OnlyFans no respondió a tiempo.")
        print("Comprueba Internet y vuelve a ejecutar: of probar")
        return 1

    stdout, stderr = process.communicate()
    if interactive:
        print("\r" + " " * 38 + "\r", end="", flush=True)
    output = f"{stdout}\n{stderr}"
    if process.returncode == 0 and "OFBACKUP_AUTH_OK" in output:
        print(_status_text("\n✓ COOKIE VÁLIDA", "green"))
        print("OnlyFans aceptó la sesión. OF Downloader está listo para descargar.")
        return 0

    if "OFBACKUP_AUTH_REJECTED" in output:
        print(_status_text("\n✗ COOKIE RECHAZADA O VENCIDA", "red"))
        print("Genera un nuevo OFBackup-auth.json desde una sesión abierta,")
        print("impórtalo con 'of importar' y repite 'of probar'.")
        return 1

    print(_status_text("\n✗ NO SE PUDO COMPROBAR LA COOKIE", "red"))
    error_type = "desconocido"
    marker = "OFBACKUP_AUTH_ERROR:"
    if marker in output:
        error_type = output.split(marker, 1)[1].splitlines()[0].strip()
    print(f"La cookie está cargada, pero falló el motor de prueba ({error_type}).")
    print("Ejecuta 'of diagnostico' y vuelve a intentar 'of probar'.")
    return 1


def find_ofscraper_binary() -> str | None:
    configured = os.getenv("OFSCRAPER_BIN")
    if configured:
        resolved = shutil.which(configured) or configured
        if Path(resolved).is_file():
            return str(Path(resolved))

    on_path = shutil.which("ofscraper")
    if on_path:
        return on_path

    # El lanzador de Termux ejecuta directamente el Python del entorno virtual
    # sin activarlo. En ese caso su carpeta bin no aparece en PATH, aunque el
    # ejecutable de OF-Scraper esté correctamente instalado junto a Python.
    # No usar resolve(): el Python del venv suele ser un enlace a /usr/bin y
    # seguirlo haría que buscásemos ofscraper en la carpeta equivocada.
    scripts_dir = Path(sys.executable).parent
    for name in ("ofscraper", "ofscraper.exe"):
        candidate = scripts_dir / name
        if candidate.is_file():
            return str(candidate)
    return None


def ofscraper_binary() -> str:
    executable = find_ofscraper_binary()
    if not executable:
        raise UserError(
            "No se encontró ofscraper. Ejecuta instalar-termux.sh o elige "
            "'Actualizar motor' en el menú."
        )
    return executable


def find_ffmpeg_binary() -> str | None:
    configured = os.getenv("FFMPEG_BIN") or os.getenv("IMAGEIO_FFMPEG_EXE")
    if configured:
        resolved = shutil.which(configured) or configured
        if Path(resolved).is_file():
            return str(Path(resolved))

    on_path = shutil.which("ffmpeg")
    if on_path:
        return on_path

    if os.name == "nt":
        candidates: list[Path] = []
        roots = [
            os.getenv("ProgramFiles"),
            os.getenv("ProgramFiles(x86)"),
            os.getenv("LOCALAPPDATA"),
        ]
        for root in roots:
            if not root:
                continue
            base = Path(root)
            candidates.extend(
                [
                    base / "ffmpeg" / "bin" / "ffmpeg.exe",
                    base / "Gyan" / "FFmpeg" / "bin" / "ffmpeg.exe",
                    base / "Programs" / "FFmpeg" / "bin" / "ffmpeg.exe",
                    base / "Microsoft" / "WinGet" / "Packages",
                ]
            )
        for candidate in candidates:
            if candidate.is_file():
                return str(candidate)
            if candidate.is_dir():
                try:
                    matches = sorted(
                        candidate.rglob("ffmpeg.exe"),
                        key=lambda path: path.stat().st_mtime,
                        reverse=True,
                    )
                except OSError:
                    matches = []
                for match in matches:
                    if match.is_file():
                        return str(match)
    return None


def build_ofscraper_command(executable: str, arguments: list[str]) -> list[str]:
    if arguments and arguments[0] == "manual":
        return [executable, "manual", "--auth-fail", *arguments[1:]]
    return [executable, "--auth-fail", *arguments]


def format_command_for_log(command: list[str]) -> str:
    executable = Path(command[0]).name if command else ""
    return " ".join([executable, *command[1:]])


def ofscraper_environment() -> dict[str, str]:
    """Evita que la comprobación externa de CDM bloquee mucho el inicio."""
    environment = os.environ.copy()
    environment["PYTHONIOENCODING"] = "utf-8"
    environment["OFSC_CDM_TEST_TIMEOUT"] = "8"
    environment["OFSC_CDM_TEST_NUM_TRIES"] = "1"
    ffmpeg = find_ffmpeg_binary()
    if ffmpeg:
        ffmpeg_dir = str(Path(ffmpeg).parent)
        environment["PATH"] = ffmpeg_dir + os.pathsep + environment.get("PATH", "")
        environment.setdefault("FFMPEG_BIN", ffmpeg)
        environment.setdefault("IMAGEIO_FFMPEG_EXE", ffmpeg)
    return environment


def extract_download_percent(line: str) -> int | None:
    matches = re.findall(r"(?<!\d)(\d{1,3})(?:\.\d+)?%", line)
    if not matches:
        return None
    return min(100, max(0, int(matches[-1])))


@dataclass
class MediaCounts:
    images: int = 0
    videos: int = 0
    other: int = 0

    @property
    def total(self) -> int:
        return self.images + self.videos + self.other


@dataclass
class DownloadStats:
    detected_images: int | None = None
    detected_videos: int | None = None
    downloaded: MediaCounts = field(default_factory=MediaCounts)
    failed: int = 0
    skipped: int = 0
    seen_events: set[str] = field(default_factory=set, repr=False)

    def label(self, stage: str) -> str:
        parts = [stage]
        if self.detected_images is not None or self.downloaded.images:
            if self.detected_images is None:
                parts.append(f"Fotos {self.downloaded.images}")
            else:
                parts.append(f"Fotos {self.downloaded.images}/{self.detected_images}")
        if self.detected_videos is not None or self.downloaded.videos:
            if self.detected_videos is None:
                parts.append(f"Videos {self.downloaded.videos}")
            else:
                parts.append(f"Videos {self.downloaded.videos}/{self.detected_videos}")
        if self.failed:
            parts.append(f"Fallos {self.failed}")
        if self.skipped:
            parts.append(f"Omitidos {self.skipped}")
        return " · ".join(parts)


@dataclass
class ProfileDetection:
    username: str
    profile_id: str = ""
    posts: int | None = None
    photos: int | None = None
    videos: int | None = None
    archived: int | None = None
    counted: int | None = None
    partial: bool = False


@dataclass
class SubscriptionProfile:
    username: str
    display_name: str = ""
    profile_id: str = ""
    status: str = "activo"
    posts: int | None = None
    photos: int | None = None
    videos: int | None = None
    archived: int | None = None


def media_kind(path: Path) -> str | None:
    suffix = path.suffix.lower()
    if suffix in PARTIAL_EXTENSIONS:
        return None
    if suffix in IMAGE_EXTENSIONS:
        return "images"
    if suffix in VIDEO_EXTENSIONS:
        return "videos"
    return None


def media_snapshot(root: Path) -> dict[str, tuple[int, int]]:
    root = root.expanduser()
    if not root.exists():
        return {}
    snapshot: dict[str, tuple[int, int]] = {}
    try:
        paths = root.rglob("*")
        for path in paths:
            try:
                if not path.is_file() or media_kind(path) is None:
                    continue
                stat = path.stat()
            except OSError:
                continue
            snapshot[str(path)] = (stat.st_size, stat.st_mtime_ns)
    except OSError:
        return snapshot
    return snapshot


def count_changed_media(
    before: dict[str, tuple[int, int]], after: dict[str, tuple[int, int]]
) -> MediaCounts:
    counts = MediaCounts()
    for raw_path, signature in after.items():
        if before.get(raw_path) == signature:
            continue
        kind = media_kind(Path(raw_path))
        if kind == "images":
            counts.images += 1
        elif kind == "videos":
            counts.videos += 1
        else:
            counts.other += 1
    return counts


def changed_media_files(
    before: dict[str, tuple[int, int]], after: dict[str, tuple[int, int]]
) -> list[Path]:
    files: list[Path] = []
    for raw_path, signature in after.items():
        if before.get(raw_path) == signature:
            continue
        if media_kind(Path(raw_path)) is not None:
            files.append(Path(raw_path))
    return sorted(files, key=lambda path: str(path).lower())


def extract_media_totals(line: str) -> tuple[int | None, int | None]:
    image_patterns = (
        r"\b(?:images?|photos?|fotos?)\b\s*[:=]\s*(\d+)",
        r"\b(\d+)\s*(?:images?|photos?|fotos?)\b",
    )
    video_patterns = (
        r"\b(?:videos?|v[ií]deos?)\b\s*[:=]\s*(\d+)",
        r"\b(\d+)\s*(?:videos?|v[ií]deos?)\b",
    )

    def first_match(patterns: tuple[str, ...]) -> int | None:
        for pattern in patterns:
            match = re.search(pattern, line, flags=re.IGNORECASE)
            if match:
                return int(match.group(1))
        return None

    return first_match(image_patterns), first_match(video_patterns)


def update_download_stats_from_line(stats: DownloadStats, line: str) -> bool:
    changed = False
    images, videos = extract_media_totals(line)
    if images is not None and images > (stats.detected_images or 0):
        stats.detected_images = images
        changed = True
    if videos is not None and videos > (stats.detected_videos or 0):
        stats.detected_videos = videos
        changed = True

    lowered = line.lower()
    event_key = lowered.strip()
    if not event_key or event_key in stats.seen_events:
        return changed
    stats.seen_events.add(event_key)

    if "download" in lowered and any(
        phrase in lowered
        for phrase in (
            "failed to download",
            "download failed",
            "error downloading",
            "download error",
            "could not download",
        )
    ):
        stats.failed += 1
        changed = True
    elif any(phrase in lowered for phrase in ("already downloaded", "skipped", "skip media")):
        stats.skipped += 1
        changed = True
    return changed


def print_download_summary(
    stats: DownloadStats, destination: Path, *, completed: bool
) -> None:
    detected_parts = []
    if stats.detected_images is not None:
        detected_parts.append(f"{stats.detected_images} fotos")
    if stats.detected_videos is not None:
        detected_parts.append(f"{stats.detected_videos} videos")

    print("\nRESUMEN")
    if detected_parts:
        print(f"Detectados por el motor: {', '.join(detected_parts)}")
    else:
        print("Detectados por el motor: no informado")
    print(
        "Archivos nuevos: "
        f"{stats.downloaded.images} fotos, {stats.downloaded.videos} videos"
    )
    if stats.downloaded.other:
        print(f"Otros archivos nuevos: {stats.downloaded.other}")
    print(f"Fallos detectados: {stats.failed}")
    if stats.skipped:
        print(f"Omitidos porque ya existian: {stats.skipped}")
    if completed and detected_parts and not stats.failed:
        detected_total = (stats.detected_images or 0) + (stats.detected_videos or 0)
        if stats.downloaded.total < detected_total:
            print(
                "Aviso: se detectaron mas elementos que archivos nuevos. "
                "Puede que algunos ya existieran, fueran DRM o no estuvieran "
                "permitidos por la cuenta."
            )
    print(f"Carpeta: {destination}")


def public_download_log_path(destination: Path) -> Path:
    return destination.expanduser() / PUBLIC_DOWNLOAD_LOG_NAME


def mirror_download_log(destination: Path) -> Path | None:
    source = DOWNLOAD_LOG_PATH
    if not source.exists():
        return None
    target = public_download_log_path(destination)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        _chmod(target, 0o600)
    except OSError:
        return None
    return target


def write_visible_log(destination: Path, filename: str, content: str) -> Path | None:
    target = destination.expanduser() / filename
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        _chmod(target, 0o600)
    except OSError:
        return None
    return target


def find_rclone_binary() -> str | None:
    configured = os.getenv("RCLONE_BIN")
    if configured:
        resolved = shutil.which(configured) or configured
        if Path(resolved).is_file():
            return str(Path(resolved))
    return shutil.which("rclone")


def drive_remote_target(state: dict, relative_path: Path | None = None) -> str:
    remote = str(state.get("drive_remote") or "gdrive").rstrip(":")
    folder = str(state.get("drive_folder") or "OFDownloader").strip().strip("/\\")
    parts = [part for part in (folder, relative_path.as_posix() if relative_path else "") if part]
    return f"{remote}:{'/'.join(parts)}"


def drive_queue() -> list[dict[str, str]]:
    data = read_json(DRIVE_QUEUE_PATH, {"items": []})
    items = data.get("items", [])
    return items if isinstance(items, list) else []


def save_drive_queue(items: list[dict[str, str]]) -> None:
    secure_write_json(DRIVE_QUEUE_PATH, {"items": items})


def enqueue_drive_files(files: list[Path], destination: Path, state: dict | None = None) -> int:
    state = state or get_state()
    destination = destination.expanduser()
    queued = drive_queue()
    seen = {(item.get("local"), item.get("remote")) for item in queued}
    added = 0
    for file in files:
        try:
            relative = file.expanduser().resolve().relative_to(destination.resolve())
        except (OSError, ValueError):
            relative = Path(file.name)
        item = {
            "local": str(file),
            "remote": drive_remote_target(state, relative),
        }
        key = (item["local"], item["remote"])
        if key in seen:
            continue
        queued.append(item)
        seen.add(key)
        added += 1
    if added:
        save_drive_queue(queued)
    return added


def rclone_remote_configured(remote: str) -> bool:
    executable = find_rclone_binary()
    if not executable:
        return False
    completed = subprocess.run(
        [executable, "listremotes"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode:
        return False
    wanted = remote.rstrip(":") + ":"
    return wanted in {line.strip() for line in completed.stdout.splitlines()}


def drive_configured(state: dict | None = None) -> bool:
    state = state or get_state()
    return rclone_remote_configured(str(state.get("drive_remote") or "gdrive"))


def drive_status_text(state: dict | None = None) -> str:
    state = state or get_state()
    if not find_rclone_binary():
        return "rclone no instalado"
    if not drive_configured(state):
        return f"remote {state.get('drive_remote', 'gdrive')} no configurado"
    return "configurado"


def upload_drive_queue(*, quiet: bool = False) -> int:
    state = get_state()
    destination = Path(state["download_dir"]).expanduser()
    executable = find_rclone_binary()
    if not executable:
        if not quiet:
            print("rclone no esta instalado. Instala/configura Google Drive primero.")
        return 2
    if not drive_configured(state):
        if not quiet:
            print(f"Google Drive no esta configurado como remote '{state['drive_remote']}'.")
        return 2

    items = drive_queue()
    if not items:
        if not quiet:
            print("No hay archivos pendientes para Google Drive.")
        return 0

    remaining: list[dict[str, str]] = []
    uploaded = 0
    failed = 0
    log_lines = [f"OF Downloader {APP_VERSION}", "Google Drive upload", ""]
    for item in items:
        local = Path(str(item.get("local", ""))).expanduser()
        remote = str(item.get("remote", ""))
        if not local.is_file() or not remote:
            continue
        completed = subprocess.run(
            [executable, "copyto", str(local), remote, "--create-empty-src-dirs"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        log_lines.append(f"LOCAL: {local}")
        log_lines.append(f"REMOTE: {remote}")
        log_lines.append(f"CODIGO: {completed.returncode}")
        if completed.stdout:
            log_lines.append(completed.stdout)
        if completed.stderr:
            log_lines.append(completed.stderr)
        log_lines.append("")
        if completed.returncode == 0:
            uploaded += 1
            if state.get("drive_delete_after_upload"):
                try:
                    local.unlink()
                except OSError as exc:
                    log_lines.append(f"No se pudo borrar local: {exc}")
        else:
            failed += 1
            remaining.append(item)

    save_drive_queue(remaining)
    visible = write_visible_log(destination, DRIVE_LOG_NAME, "\n".join(log_lines))
    if not quiet:
        print(f"Google Drive: {uploaded} subidos, {failed} fallidos.")
        if remaining:
            print(f"Pendientes: {len(remaining)}")
        if visible:
            print(f"Log visible: {visible}")
    return 0 if failed == 0 else 1


def show_drive_pending() -> int:
    items = drive_queue()
    if not items:
        print("No hay archivos pendientes para Google Drive.")
        return 0
    print(f"Pendientes para Google Drive: {len(items)}")
    for index, item in enumerate(items, start=1):
        local = Path(str(item.get("local", ""))).expanduser()
        remote = str(item.get("remote", ""))
        status = "existe" if local.is_file() else "no existe local"
        print(f"{index}. {status}")
        print(f"   Local:  {local}")
        print(f"   Drive:  {remote or 'sin destino'}")
    return 0


def clean_drive_queue(*, all_items: bool = False) -> int:
    items = drive_queue()
    if not items:
        print("No hay pendientes para limpiar.")
        return 0
    if all_items:
        save_drive_queue([])
        print(f"Cola de Google Drive limpiada: {len(items)} pendientes borrados.")
        return 0
    remaining = [
        item
        for item in items
        if Path(str(item.get("local", ""))).expanduser().is_file()
    ]
    removed = len(items) - len(remaining)
    save_drive_queue(remaining)
    print(f"Pendientes sin archivo local eliminados: {removed}.")
    print(f"Pendientes restantes: {len(remaining)}.")
    if remaining:
        print("Para borrar toda la cola usa: of drive limpiar todo")
    return 0


def maybe_upload_to_drive(files: list[Path], destination: Path) -> None:
    if not files:
        return
    state = get_state()
    if not state.get("drive_enabled") or not state.get("drive_upload_after_download", True):
        return
    added = enqueue_drive_files(files, destination, state)
    if added:
        print(f"\nGoogle Drive: {added} archivos nuevos en cola.")
    upload_drive_queue(quiet=False)


def configure_drive() -> int:
    state = get_state()
    executable = find_rclone_binary()
    if not executable:
        print("No encontre rclone.")
        print("Instalalo con el instalador de la app o con las instrucciones oficiales:")
        print("https://rclone.org/install/")
        return 2
    remote = input(f"Nombre del remote de Google Drive [{state['drive_remote']}]: ").strip() or state["drive_remote"]
    folder = input(f"Carpeta en Drive [{state['drive_folder']}]: ").strip() or state["drive_folder"]
    state["drive_remote"] = remote.rstrip(":")
    state["drive_folder"] = folder.strip().strip("/\\") or "OFDownloader"
    save_state(state)
    if not rclone_remote_configured(state["drive_remote"]):
        print("\nSe abrira la configuracion de rclone.")
        print("Crea un remote tipo Google Drive con este nombre:")
        print(f"  {state['drive_remote']}")
        print("Si ya existe con otro nombre, vuelve y escribe ese nombre.")
        subprocess.run([executable, "config"], check=False)
    state["drive_enabled"] = drive_configured(state)
    save_state(state)
    print(f"Google Drive: {drive_status_text(state)}")
    return 0 if state["drive_enabled"] else 1


def drive_menu() -> int:
    while True:
        state = get_state()
        print("\nGOOGLE DRIVE")
        print(f"Estado: {drive_status_text(state)}")
        print(f"Subida automatica: {'activada' if state.get('drive_enabled') else 'desactivada'}")
        print(f"Destino: {drive_remote_target(state)}")
        print(f"Pendientes: {len(drive_queue())}")
        print("1. Configurar Google Drive")
        print("2. Activar/desactivar subida automatica")
        print("3. Subir pendientes ahora")
        print("4. Ver estado")
        print("5. Ver pendientes")
        print("6. Limpiar pendientes sin archivo local")
        print("7. Limpiar toda la cola")
        print("0. Volver")
        choice = input("Elige una opcion: ").strip()
        if choice == "1":
            configure_drive()
        elif choice == "2":
            state = get_state()
            state["drive_enabled"] = not bool(state.get("drive_enabled"))
            save_state(state)
            print(f"Subida automatica: {'activada' if state['drive_enabled'] else 'desactivada'}")
        elif choice == "3":
            upload_drive_queue()
        elif choice == "4":
            print(f"rclone: {find_rclone_binary() or 'NO ENCONTRADO'}")
            print(f"Google Drive: {drive_status_text()}")
            print(f"Remote: {state.get('drive_remote')}")
            print(f"Carpeta: {state.get('drive_folder')}")
            print(f"Pendientes: {len(drive_queue())}")
        elif choice == "5":
            show_drive_pending()
        elif choice == "6":
            clean_drive_queue()
        elif choice == "7":
            confirm = input("Borrar toda la cola pendiente? Escribe SI: ").strip()
            if confirm == "SI":
                clean_drive_queue(all_items=True)
            else:
                print("No se borro la cola.")
        elif choice == "0":
            return 0
        else:
            print("Opcion no valida.")


def drive_command(args: list[str]) -> int:
    action = (args[0].lower() if args else "estado")
    if action in {"configurar", "config"}:
        return configure_drive()
    if action in {"activar", "on"}:
        state = get_state()
        state["drive_enabled"] = True
        save_state(state)
        print("Subida automatica a Google Drive activada.")
        return 0
    if action in {"desactivar", "off"}:
        state = get_state()
        state["drive_enabled"] = False
        save_state(state)
        print("Subida automatica a Google Drive desactivada.")
        return 0
    if action in {"subir", "upload"}:
        return upload_drive_queue()
    if action in {"pendientes", "pending"}:
        return show_drive_pending()
    if action in {"limpiar", "clean"}:
        all_items = len(args) > 1 and args[1].lower() in {"todo", "all"}
        return clean_drive_queue(all_items=all_items)
    if action in {"estado", "status"}:
        state = get_state()
        print(f"rclone: {find_rclone_binary() or 'NO ENCONTRADO'}")
        print(f"Google Drive: {drive_status_text(state)}")
        print(f"Subida automatica: {'activada' if state.get('drive_enabled') else 'desactivada'}")
        print(f"Destino: {drive_remote_target(state)}")
        print(f"Pendientes: {len(drive_queue())}")
        return 0
    raise UserError(
        "Uso: of drive configurar|activar|desactivar|subir|pendientes|limpiar|estado"
    )


def optional_int(value: object) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(str(value)))
    except (TypeError, ValueError):
        return None


def first_present(data: dict, keys: tuple[str, ...]) -> object:
    for key in keys:
        if key in data and data[key] not in (None, ""):
            return data[key]
    return None


def subscription_status(data: dict) -> str:
    for key in ("isFree", "free", "subscribedIsFree"):
        value = data.get(key)
        if isinstance(value, bool):
            return "gratis" if value else "pagado"
    price = first_present(
        data,
        (
            "subscribePrice",
            "subscriptionPrice",
            "regularPrice",
            "price",
        ),
    )
    numeric = optional_int(price)
    if numeric == 0:
        return "gratis"
    if numeric and numeric > 0:
        return "pagado"
    return "activo"


def normalize_subscription_profile(data: dict) -> SubscriptionProfile | None:
    username = str(first_present(data, ("username", "name", "model_username")) or "").strip()
    username = profile_username(username) or username.lstrip("@")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", username):
        return None
    return SubscriptionProfile(
        username=username,
        display_name=str(
            first_present(data, ("displayName", "name", "rawText", "username")) or ""
        ).strip(),
        profile_id=str(first_present(data, ("id", "userId", "model_id")) or "").strip(),
        status=subscription_status(data),
        posts=optional_int(first_present(data, ("postsCount", "post_count", "posts"))),
        photos=optional_int(first_present(data, ("photosCount", "photo_count", "photos"))),
        videos=optional_int(first_present(data, ("videosCount", "video_count", "videos"))),
        archived=optional_int(
            first_present(data, ("archivedPostsCount", "archived_count", "archived"))
        ),
    )


def parse_subscriptions_stdout(stdout: str) -> list[SubscriptionProfile]:
    raw_payload = None
    for line in stdout.splitlines():
        if line.startswith(SUBSCRIPTIONS_SENTINEL):
            raw_payload = line[len(SUBSCRIPTIONS_SENTINEL) :]
    if raw_payload is None:
        return []
    try:
        payload = json.loads(raw_payload)
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, list):
        return []
    profiles: list[SubscriptionProfile] = []
    seen: set[str] = set()
    for item in payload:
        if not isinstance(item, dict):
            continue
        profile = normalize_subscription_profile(item)
        if profile is None:
            continue
        key = profile.profile_id or profile.username.lower()
        if key in seen:
            continue
        seen.add(key)
        profiles.append(profile)
    return sorted(profiles, key=lambda profile: profile.username.lower())


def run_profile_lookup_process(
    username: str, destination: Path, timeout: int
) -> tuple[int, str, str, Path | None]:
    code = 1
    stdout = ""
    stderr = ""
    try:
        process = subprocess.Popen(
            [sys.executable, "-c", PROFILE_TEST_SCRIPT, username],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=ofscraper_environment(),
        )
        started = time.monotonic()
        if sys.stdout.isatty():
            show_download_progress(5, "Detectando fotos y videos")
        else:
            print("Detectando fotos y videos antes de descargar...")
            print("Puede tardar hasta 2 minutos en perfiles grandes.")
        while process.poll() is None:
            elapsed = time.monotonic() - started
            if elapsed >= timeout:
                process.terminate()
                try:
                    stdout, stderr = process.communicate(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    stdout, stderr = process.communicate()
                code = 124
                stderr = (stderr or "") + f"\nLa prueba supero {timeout} segundos.\n"
                break
            if sys.stdout.isatty():
                progress = min(95, 5 + int((elapsed / max(timeout, 1)) * 90))
                show_download_progress(progress, "Detectando fotos y videos")
            time.sleep(0.5)
        else:
            stdout, stderr = process.communicate()
            code = process.returncode
        if sys.stdout.isatty():
            label = "Deteccion finalizada" if code == 0 else "Deteccion detenida"
            show_download_progress(100 if code == 0 else 95, label, failed=code != 0)
            print()
    except OSError as exc:
        code, stdout, stderr = 1, "", str(exc)
    log_content = (
        f"OF Downloader {APP_VERSION}\n"
        f"Prueba de perfil: {username}\n"
        f"Codigo: {code}\n\n"
        "SALIDA\n"
        f"{stdout}\n"
        "ERRORES\n"
        f"{stderr}\n"
    )
    visible_log = write_visible_log(destination, PROFILE_TEST_LOG_NAME, log_content)
    return code, stdout, stderr, visible_log


def parse_profile_detection(stdout: str) -> ProfileDetection | None:
    line = next(
        (raw for raw in stdout.splitlines() if raw.startswith("OFDOWNLOADER_PROFILE_OK")),
        "",
    )
    if not line:
        return None
    values = dict(re.findall(r"(\w+)=([^\s]*)", line))
    username = values.get("username", "").strip()
    if not username:
        return None
    return ProfileDetection(
        username=username,
        profile_id=values.get("id", ""),
        posts=optional_int(values.get("posts")),
        photos=optional_int(values.get("photos")),
        videos=optional_int(values.get("videos")),
        archived=optional_int(values.get("archived")),
        counted=optional_int(values.get("counted")),
        partial=values.get("partial") == "1",
    )


def detect_profile_counts(username: str, timeout: int = 120) -> ProfileDetection | None:
    require_credentials()
    write_ofscraper_config()
    ofscraper_binary()
    destination = Path(get_state()["download_dir"]).expanduser()
    code, stdout, stderr, visible_log = run_profile_lookup_process(
        username, destination, timeout
    )
    detection = parse_profile_detection(stdout)
    if code == 0 and detection is not None:
        if detection.counted is not None:
            total = f"{detection.counted} medios"
        else:
            total = "conteo no informado"
        print(f"Deteccion lista: {total}.")
        return detection
    print("No se pudo detectar el contenido antes de descargar.")
    if code == 124:
        print("La deteccion tardo demasiado.")
    elif "Auth Failed" in stdout or "Auth Failed" in stderr:
        print("OnlyFans rechazo los datos de acceso.")
    else:
        print("Puede ser sesion invalida, perfil sin acceso o bloqueo de la API.")
    if visible_log:
        print(f"Log visible: {visible_log}")
    return None


def list_subscription_profiles(timeout: int = 90) -> list[SubscriptionProfile]:
    require_credentials()
    write_ofscraper_config()
    ofscraper_binary()
    destination = Path(get_state()["download_dir"]).expanduser()
    print("\nBuscando perfiles de tus suscripciones activas...")
    print("Incluye perfiles gratis si OnlyFans los muestra como activos.")
    try:
        process = subprocess.run(
            [sys.executable, "-c", SUBSCRIPTIONS_LIST_SCRIPT],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
            env=ofscraper_environment(),
        )
        code, stdout, stderr = process.returncode, process.stdout, process.stderr
    except subprocess.TimeoutExpired:
        code, stdout, stderr = 124, "", f"La busqueda supero {timeout} segundos.\n"
    log_content = (
        f"OF Downloader {APP_VERSION}\n"
        "Perfiles suscritos\n"
        f"Codigo: {code}\n\n"
        "SALIDA\n"
        f"{stdout}\n"
        "ERRORES\n"
        f"{stderr}\n"
    )
    visible_log = write_visible_log(destination, SUBSCRIPTIONS_LOG_NAME, log_content)
    profiles = parse_subscriptions_stdout(stdout)
    if code == 0 and profiles:
        print(f"Perfiles encontrados: {len(profiles)}")
        return profiles
    print("No se pudieron cargar perfiles suscritos.")
    if code == 124:
        print("La busqueda tardo demasiado.")
    elif "Auth Failed" in stdout or "Auth Failed" in stderr:
        print("OnlyFans rechazo los datos de acceso. Renueva la cookie en la opcion 3.")
    else:
        print("La sesion no devolvio perfiles o el motor no informo datos utiles.")
    if visible_log:
        print(f"Log visible: {visible_log}")
    return []


def compact_count(value: int | None) -> str:
    return str(value) if value is not None else "-"


def profile_list_line(index: int, profile: SubscriptionProfile) -> str:
    display = f" ({profile.display_name})" if profile.display_name and profile.display_name != profile.username else ""
    counts = (
        f"posts {compact_count(profile.posts)} | "
        f"fotos {compact_count(profile.photos)} | "
        f"videos {compact_count(profile.videos)}"
    )
    return f"{index:>3}. @{profile.username}{display} - {profile.status} - {counts}"


def choose_subscription_profile(
    profiles: list[SubscriptionProfile],
) -> SubscriptionProfile | None:
    visible = profiles
    while True:
        print("\nPERFILES")
        for index, profile in enumerate(visible[:40], start=1):
            print(profile_list_line(index, profile))
        if len(visible) > 40:
            print(f"... y {len(visible) - 40} mas. Escribe texto para filtrar.")
        choice = input("\nEscoge numero, @usuario, texto para filtrar o Enter para cancelar: ").strip()
        if not choice:
            return None
        if choice.isdigit():
            index = int(choice)
            if 1 <= index <= min(len(visible), 40):
                return visible[index - 1]
            print("Numero fuera de la lista visible.")
            continue
        wanted = choice.lstrip("@").lower()
        exact = [profile for profile in profiles if profile.username.lower() == wanted]
        if len(exact) == 1:
            return exact[0]
        matches = [
            profile
            for profile in profiles
            if wanted in profile.username.lower()
            or wanted in profile.display_name.lower()
        ]
        if len(matches) == 1:
            return matches[0]
        if matches:
            visible = matches
            print(f"Filtro aplicado: {len(matches)} perfiles.")
            continue
        print("No encontre perfiles con ese texto.")


def print_detection_summary(profile: SubscriptionProfile, detection: ProfileDetection | None) -> None:
    print("\nDETECCION")
    print(f"Perfil: @{profile.username}")
    if detection is None:
        print("Detectados: no informado")
        return
    print(f"Posts:      {compact_count(detection.posts)}")
    print(f"Fotos:      {compact_count(detection.photos)}")
    print(f"Videos:     {compact_count(detection.videos)}")
    print(f"Archivados: {compact_count(detection.archived)}")
    if detection.counted:
        status = "parcial" if detection.partial else "completo"
        print(f"Conteo real de medios: {detection.counted} ({status})")


def choose_profile_and_download() -> int:
    profiles = list_subscription_profiles()
    if not profiles:
        return 1
    selected = choose_subscription_profile(profiles)
    if selected is None:
        print("Cancelado. No se descargo nada.")
        return 0
    detection = detect_profile_counts(selected.username)
    print_detection_summary(selected, detection)
    answer = input("\nDescargar este perfil completo? [s/N]: ").strip().lower()
    if answer not in {"s", "si", "sí", "y", "yes"}:
        print("Cancelado. No se descargo nada.")
        return 0
    return download_user(selected.username, source="selector")


def show_download_progress(percent: int, label: str, *, failed: bool = False) -> None:
    percent = min(100, max(0, percent))
    width = 24
    filled = percent * width // 100
    bar = "#" * filled + "-" * (width - filled)
    message = f"[{bar}] {percent:3d}%  {label}"
    if colors_enabled():
        color = PALETTE["red" if failed else "cyan"]
        print(f"\r\033[2K\033[1;{color}m{message}\033[0m", end="", flush=True)
    else:
        print(message)


def run_ofscraper(
    arguments: list[str], *, mode: str = "publicacion", target: str | None = None
) -> int:
    require_credentials()
    write_ofscraper_config()
    executable = ofscraper_binary()
    command = build_ofscraper_command(executable, arguments)
    destination = Path(get_state()["download_dir"]).expanduser()
    before_download = media_snapshot(destination)
    print("\nOF Downloader está preparando la descarga…")
    if mode == "perfil":
        print(f"Modo: perfil completo @{target or 'desconocido'}")
    else:
        print("Modo: publicación por enlace")
    print(f"Motor: {format_command_for_log(command)}")
    traceback_seen = False
    auth_failed = False
    stats = DownloadStats()
    progress = 3
    last_stage = "Iniciando"
    last_label = stats.label(last_stage)
    last_scan = 0.0
    show_download_progress(progress, last_label)
    APP_DIR.mkdir(parents=True, exist_ok=True)
    try:
        with DOWNLOAD_LOG_PATH.open("w", encoding="utf-8") as log_file:
            _chmod(DOWNLOAD_LOG_PATH, 0o600)
            log_file.write(f"OF Downloader {APP_VERSION}\n")
            log_file.write(f"Modo: {mode}\n")
            if target:
                log_file.write(f"Objetivo: {target}\n")
            log_file.write(f"Comando: {format_command_for_log(command)}\n\n")
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                env=ofscraper_environment(),
            )
            if process.stdout is None:  # pragma: no cover - garantía de subprocess
                raise UserError("No se pudo leer la salida de OF-Scraper.")
            for line in process.stdout:
                log_file.write(line)
                log_file.flush()
                lowered = line.lower()
                if "traceback (most recent call last):" in lowered:
                    traceback_seen = True
                if "auth failed" in lowered:
                    auth_failed = True
                if traceback_seen or auth_failed:
                    process.terminate()
                    break

                stats_changed = update_download_stats_from_line(stats, line)
                now = time.monotonic()
                if now - last_scan >= 1:
                    stats.downloaded = count_changed_media(
                        before_download, media_snapshot(destination)
                    )
                    last_scan = now
                    stats_changed = True

                reported = extract_download_percent(line)
                if reported is not None:
                    new_progress = max(progress, min(95, 35 + reported * 3 // 5))
                    stage = "Descargando archivos"
                elif "key mode:" in lowered:
                    new_progress, stage = max(progress, 10), "Preparando video"
                elif "checking auth status" in lowered:
                    new_progress, stage = max(progress, 20), "Verificando acceso"
                elif any(word in lowered for word in ("scrap", "timeline", "post")):
                    search_label = (
                        "Buscando el perfil" if mode == "perfil" else "Buscando la publicación"
                    )
                    new_progress, stage = max(progress, 35), search_label
                elif "download" in lowered:
                    new_progress, stage = max(progress, 45), "Descargando archivos"
                else:
                    new_progress, stage = progress, last_stage

                label = stats.label(stage)
                if (
                    new_progress != progress
                    or stage != last_stage
                    or label != last_label
                    or stats_changed
                ):
                    progress, last_stage = new_progress, stage
                    last_label = label
                    show_download_progress(progress, last_label)
            returncode = process.wait()
    except OSError as exc:
        raise UserError(f"No se pudo iniciar OF-Scraper: {exc}") from exc

    after_download = media_snapshot(destination)
    stats.downloaded = count_changed_media(before_download, after_download)
    new_files = changed_media_files(before_download, after_download)
    if returncode or traceback_seen or auth_failed:
        shown_code = returncode or 1
        show_download_progress(progress, stats.label("ERROR: descarga detenida"), failed=True)
        print("\n✗ La descarga no se completó.")
        if auth_failed:
            print("OnlyFans rechazó los datos de acceso.")
            print("Abre la opción 3 y pega x-bc y User-Agent de la misma sesión.")
        elif traceback_seen and not returncode:
            print("OF-Scraper informó un error interno aunque devolvió código 0.")
        else:
            print(f"OF-Scraper terminó con código {returncode}.")
        print_download_summary(stats, destination, completed=False)
        mirrored = mirror_download_log(destination)
        if mirrored is not None:
            print(f"Registro para revisar el error: {mirrored}")
        else:
            print(f"Registro para revisar el error: {DOWNLOAD_LOG_PATH}")
        return shown_code
    else:
        show_download_progress(100, stats.label("Descarga completada"))
        print(f"\n✓ Descarga terminada. Archivos en: {get_state()['download_dir']}")
        print_download_summary(stats, destination, completed=True)
        maybe_upload_to_drive(new_files, destination)
        return 0


def normalize_url(value: str) -> str:
    value = value.strip()
    if re.fullmatch(r"\d+", value):
        return value
    extracted = extract_onlyfans_url(value)
    if extracted is None:
        raise UserError("Introduce un enlace https://onlyfans.com/... o un ID numérico.")
    return extracted


def extract_onlyfans_url(value: str) -> str | None:
    """Extrae el primer enlace de OnlyFans aunque venga embebido en Markdown o texto extra."""
    value = value.strip()
    match = re.search(r"https://(?:www\.)?onlyfans\.com/[^\s\])>]+", value, re.IGNORECASE)
    if match:
        return match.group(0).rstrip(".,;")
    if value.startswith("<") and value.endswith(">"):
        inner = value[1:-1].strip()
        if inner.lower().startswith("https://onlyfans.com/") or inner.lower().startswith(
            "https://www.onlyfans.com/"
        ):
            return inner
    return None


def profile_username(value: str) -> str | None:
    """Devuelve el usuario cuando el valor representa un perfil de OnlyFans."""
    value = value.strip()
    extracted_url = extract_onlyfans_url(value)
    if extracted_url is not None:
        value = extracted_url
    plain = value.lstrip("@")
    if re.fullmatch(r"[A-Za-z0-9_.-]+", plain):
        return plain
    try:
        parsed = urlparse(value)
    except ValueError:
        return None
    if parsed.scheme.lower() != "https" or parsed.hostname not in {
        "onlyfans.com",
        "www.onlyfans.com",
    }:
        return None
    parts = [part for part in parsed.path.split("/") if part]
    if not parts or parts[0].isdigit():
        return None
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", parts[0]):
        return None
    if len(parts) == 1 or parts[1].lower() in {"media", "posts", "photos", "videos"}:
        return parts[0]
    return None


def download_link(url: str | None = None) -> int:
    url = url or input("Pega el enlace de la publicación: ")
    username = profile_username(url)
    if username:
        return download_user(username, source="enlace")
    return run_ofscraper(
        ["manual", "--url", normalize_url(url), "--output", "normal"],
        mode="publicacion",
        target=normalize_url(url),
    )


def download_user(username: str | None = None, *, source: str = "menu") -> int:
    state = get_state()
    username = (
        username
        or input("Usuario o enlace del perfil: ")
        or state.get("username", "")
    )
    username = profile_username(username) or ""
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", username):
        raise UserError("El nombre de usuario no es válido.")
    state["username"] = username
    save_state(state)
    if source == "enlace":
        print(f"✓ Enlace de perfil detectado: @{username}")
    else:
        print(f"✓ Perfil detectado: @{username}")
    print("Se lanzará la búsqueda del perfil completo permitido por tu cuenta.")
    print("Reescaneo completo activado para evitar caché vacía o antigua.")
    return run_ofscraper(
        [
            "--username",
            username,
            "--action",
            "download",
            "--no-cache",
            "--no-api-cache",
            "--update-profile",
            "--posts",
            "all",
            "--download-area",
            "Timeline,Archived,Pinned,Stories,Streams,Profile,Purchased",
            "--mediatype",
            "images,videos",
            "--force-all",
            "--no-live",
            "--output",
            "normal",
        ],
        mode="perfil",
        target=username,
    )


def test_profile_lookup(username: str | None = None, timeout: int = 120) -> int:
    require_credentials()
    write_ofscraper_config()
    ofscraper_binary()
    state = get_state()
    destination = Path(state["download_dir"]).expanduser()
    username = profile_username(
        username or input("Usuario o enlace del perfil a probar: ")
    ) or ""
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", username):
        raise UserError("El nombre de usuario no es válido.")

    print(f"\nProbando búsqueda de perfil: @{username}")
    print("No se descargará contenido; solo se consulta si OnlyFans devuelve el perfil.")
    try:
        process = subprocess.run(
            [sys.executable, "-c", PROFILE_TEST_SCRIPT, username],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
            env=ofscraper_environment(),
        )
    except subprocess.TimeoutExpired as exc:
        log_content = (
            f"OF Downloader {APP_VERSION}\n"
            f"Prueba de perfil: {username}\n"
            "Codigo: timeout\n\n"
            f"La prueba superó {timeout} segundos.\n"
        )
        visible_log = write_visible_log(destination, PROFILE_TEST_LOG_NAME, log_content)
        print("✗ La prueba de perfil tardó demasiado y fue detenida.")
        if visible_log:
            print(f"Log visible: {visible_log}")
        return 124
    log_content = (
        f"OF Downloader {APP_VERSION}\n"
        f"Prueba de perfil: {username}\n"
        f"Codigo: {process.returncode}\n\n"
        "SALIDA\n"
        f"{process.stdout}\n"
        "ERRORES\n"
        f"{process.stderr}\n"
    )
    visible_log = write_visible_log(destination, PROFILE_TEST_LOG_NAME, log_content)
    if "OFDOWNLOADER_PROFILE_OK" in process.stdout:
        print("✓ OnlyFans devolvió el perfil.")
        for part in process.stdout.strip().split():
            if part.startswith(("posts=", "photos=", "videos=", "archived=")):
                print(f"  {part}")
        if visible_log:
            print(f"Log visible: {visible_log}")
        return 0
    print("✗ OnlyFans no devolvió datos útiles para ese perfil.")
    if process.returncode == 3:
        print("La respuesta vino vacía.")
    elif process.returncode == 4:
        print("El perfil aparece como eliminado o no disponible.")
    else:
        print("Puede ser sesión inválida, perfil sin acceso o bloqueo de la API.")
    if visible_log:
        print(f"Log visible: {visible_log}")
    return process.returncode or 1


def change_destination() -> None:
    state = get_state()
    current = state["download_dir"]
    value = input(f"Carpeta de descargas [{current}]: ").strip()
    destination = Path(value or current).expanduser()
    destination.mkdir(parents=True, exist_ok=True)
    state["download_dir"] = str(destination)
    save_state(state)
    write_ofscraper_config(state)
    print(f"✓ Destino actualizado: {destination}")


def diagnostics() -> None:
    state = get_state()
    executable = find_ofscraper_binary()
    print("\nDIAGNÓSTICO")
    print(f"OF Downloader:   {APP_VERSION}")
    print(f"Python:          {sys.version.split()[0]}")
    print(f"OF-Scraper:      {executable or 'NO ENCONTRADO'}")
    print(f"FFmpeg:          {find_ffmpeg_binary() or 'NO ENCONTRADO'}")
    print(f"Google Drive:    {drive_status_text(state)}")
    print(f"Credenciales:    {'configuradas' if credentials_ready() else 'pendientes'}")
    print(f"Descargas:       {state['download_dir']}")
    print(f"Config privada:  {APP_DIR}")

    version = sys.version_info
    if not ((3, 11) <= version[:2] < (3, 14)):
        print("AVISO: OF-Scraper requiere Python >=3.11 y <3.14.")


def update_engine() -> int:
    print("Actualizando pip, OF-Scraper y Pillow…")
    commands = [
        [sys.executable, "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"],
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--upgrade",
            f"ofscraper=={OFSCRAPER_VERSION}",
            "Pillow>=12.2,<13",
        ],
    ]
    for command in commands:
        completed = subprocess.run(command, check=False)
        if completed.returncode:
            print("✗ La actualización no pudo completarse.")
            return completed.returncode
    print("✓ Motor actualizado correctamente.")
    return 0


def pause() -> None:
    try:
        input(styled("\nPulsa Enter para volver al menú…", "muted"))
    except EOFError:
        pass


def menu() -> int:
    while True:
        state = get_state()
        connected = credentials_ready()
        if ansi_supported():
            print("\033[2J\033[H", end="")
        print()
        brand_labels = (
            "OF DOWNLOADER",
            f"{os.getenv('OFDOWNLOADER_PLATFORM', 'TERMUX')} · v{APP_VERSION}",
            "Descargas simples",
            "",
        )
        for label, logo_line in zip(brand_labels, MENU_LOGO_LINES):
            menu_brand_line(label, logo_line)
        print(styled("  " + "─" * 42, "navy"))

        print(styled("\n  DESCARGAS", "blue", bold=True))
        menu_option("1", "Elegir perfil de mis suscripciones")
        menu_option("2", "Descargar perfil por usuario o enlace")
        menu_option("3", "Descargar publicacion por enlace")

        print(styled("\n  MI CUENTA", "blue", bold=True))
        menu_option("4", "Conectar o renovar acceso")
        menu_option("5", "Probar acceso")

        print(styled("\n  HERRAMIENTAS", "blue", bold=True))
        menu_option("6", "Cambiar carpeta de descargas")
        menu_option("7", "Ver diagnostico")
        update_status = os.getenv("OFDOWNLOADER_UPDATE_STATUS", "unknown")
        update_label = "Actualizar OF Downloader y reiniciar"
        if update_status == "available":
            update_label += "  ← NUEVA"
        menu_option("8", update_label)
        menu_option("9", "Actualizar motor de descarga")
        menu_option("10", "Google Drive")
        menu_option("0", "Salir")

        status = styled("● CONECTADA", "green", bold=True) if connected else styled(
            "● SIN CONECTAR", "yellow", bold=True
        )
        print(styled("\n  " + "─" * 42, "navy"))
        print(f"  {styled('Cuenta:', 'muted')} {status}")
        print(
            f"  {styled('Aplicación:', 'muted')} "
            f"{repository_update_badge(update_status)}"
        )
        print(f"  {styled('Destino:', 'muted')} {styled(state['download_dir'], 'white')}")
        choice = input(styled("\n  Elige una opción › ", "cyan", bold=True)).strip()
        try:
            if choice == "1":
                choose_profile_and_download()
            elif choice == "2":
                download_user()
            elif choice == "3":
                download_link()
            elif choice == "4":
                result = configure_credentials()
                if result == IMPORT_REQUEST_EXIT:
                    return IMPORT_REQUEST_EXIT
            elif choice == "5":
                result = test_credentials()
                if result == IMPORT_REQUEST_EXIT:
                    return IMPORT_REQUEST_EXIT
            elif choice == "6":
                change_destination()
            elif choice == "7":
                diagnostics()
            elif choice == "8":
                return APP_UPDATE_REQUEST_EXIT
            elif choice == "9":
                update_engine()
            elif choice == "10":
                drive_menu()
            elif choice == "0":
                print(styled("\nHasta luego.", "cyan", bold=True))
                return 0
            else:
                print(_status_text("Opción no válida.", "yellow"))
        except UserError as exc:
            print(_status_text(f"\n✗ {exc}", "red"))
        except KeyboardInterrupt:
            print("\nOperación cancelada.")
        pause()


def print_help() -> None:
    print(
        """Uso:
  of                               Abrir menú interactivo
  of ENLACE                        Descargar una publicación
  of usuario NOMBRE                Descargar todo un usuario
  of perfiles                      Elegir perfil de tus suscripciones
  of configurar                    Guardar o renovar credenciales
  of importar                      Importar OFBackup-auth.json
  of importar RUTA                 Importar el archivo directamente
  of recibir-cookie                Recibir acceso desde la extension en red local
  of cookie ayuda                  Ver como exportar y mover OFBackup-auth.json
  of probar                        Comprobar la cookie sin descargar contenido
  of probar-perfil USUARIO          Comprobar si OnlyFans devuelve un perfil
  of diagnostico                   Comprobar la instalación
  of actualizar                    Actualizar el motor de descarga
  of actualizar-app                Actualizar la aplicación y reiniciarla
  of drive estado                  Ver estado de Google Drive
  of drive configurar              Configurar Google Drive con rclone
  of drive activar                 Activar subida automatica
  of drive desactivar              Desactivar subida automatica
  of drive subir                   Subir pendientes ahora
  of drive pendientes              Ver cola pendiente de Google Drive
  of drive limpiar                 Quitar pendientes sin archivo local
  of drive limpiar todo            Borrar toda la cola pendiente

Las credenciales se solicitan de forma oculta para que no queden en el
historial del terminal. Usa únicamente contenido al que tu cuenta tenga acceso.

El comando anterior `ofbackup` continúa disponible como alias.
"""
    )


def print_cookie_help() -> None:
    print(
        """FLUJO RECOMENDADO PARA LA COOKIE

No pegues cookies manualmente. Usa siempre el archivo OFBackup-auth.json de la
extension OF Downloader Exporter.

En el navegador donde ya abriste OnlyFans:
1. Abre OnlyFans e inicia sesion.
2. Pulsa la extension OF Downloader Exporter.
3. Puedes exportar OFBackup-auth.json o enviarlo directo con of recibir-cookie.

Envio local directo:
1. En este equipo ejecuta:
  of recibir-cookie
2. La app mostrara una URL local y un codigo temporal.
3. En la extension usa Enviar a OF Downloader.
4. Pega la URL y el codigo.

Ese modo funciona solo en la misma Wi-Fi o hotspot, dura 5 minutos y es de un
solo uso. No imprime secretos.

Para pasarlo a otro equipo:
- PC a movil: cable USB, Google Drive, Nearby Share, Telegram guardado como
  archivo, o copiarlo a Descargas del telefono.
- Movil a PC: Google Drive, cable USB, Nearby Share, correo propio como archivo
  adjunto, o descargarlo en la carpeta Downloads.

Luego importa y prueba:
  of importar
  of probar

Si el selector no abre, usa ruta directa:
  of importar RUTA/OFBackup-auth.json

Despues de importar, borra OFBackup-auth.json de Descargas. La app guarda solo
sess, auth_id, x-bc y User-Agent en su carpeta privada.
"""
    )


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        if not argv or argv[0] == "menu":
            return menu()
        command = argv[0].lower()
        if command in {"-h", "--help", "ayuda"}:
            print_help()
            return 0
        if command in {"cookie", "cookies", "acceso"}:
            subcommand = argv[1].lower() if len(argv) > 1 else "ayuda"
            if subcommand in {"ayuda", "help", "flujo"}:
                print_cookie_help()
                return 0
            raise UserError("Uso: of cookie ayuda")
        if command in {"ayuda-cookie", "cookie-ayuda"}:
            print_cookie_help()
            return 0
        if command in {"configurar", "config"}:
            return configure_credentials()
        if command == "importar":
            if len(argv) >= 2:
                import_credentials_file(Path(argv[1]))
                return 0
            platform_name = os.getenv("OFDOWNLOADER_PLATFORM", "TERMUX").upper()
            if platform_name in {"LINUX", "WINDOWS"}:
                import_default_auth_export()
                return 0
            return IMPORT_REQUEST_EXIT
        if command == "importar-archivo":
            if len(argv) != 2:
                raise UserError("Falta la ruta temporal del archivo seleccionado.")
            import_credentials_file(Path(argv[1]))
            return 0
        if command in {"recibir-cookie", "recibir", "receive-cookie"}:
            port = int(argv[1]) if len(argv) > 1 and argv[1].isdigit() else 8765
            return receive_credentials_locally(port=port)
        if command in {"diagnostico", "diagnóstico", "status"}:
            diagnostics()
            return 0
        if command in {"probar", "test", "comprobar"}:
            return test_credentials()
        if command in {"probar-perfil", "test-perfil", "perfil-test"}:
            return test_profile_lookup(argv[1] if len(argv) > 1 else None)
        if command in {"perfiles", "suscripciones", "subs"}:
            return choose_profile_and_download()
        if command in {"actualizar", "update"}:
            return update_engine()
        if command in {"actualizar-app", "update-app"}:
            return APP_UPDATE_REQUEST_EXIT
        if command in {"drive", "gdrive"}:
            return drive_command(argv[1:])
        if command == "usuario":
            return download_user(argv[1] if len(argv) > 1 else None)
        return download_link(argv[0])
    except UserError as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\nOperación cancelada.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
