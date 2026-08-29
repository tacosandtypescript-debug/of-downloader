"""Servicio de autenticación para OF Downloader.

Centraliza toda la lógica de cookies, credenciales y verificación de sesión.
Tanto la CLI como el dashboard web consumen este servicio.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import shutil
import socket
import subprocess
import sys
import time
from datetime import datetime
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from backend.models import UserError


class AuthService:
    """Gestiona credenciales de OnlyFans: importación, validación y persistencia."""

    # ── Constantes ────────────────────────────────────────────────────────
    APP_VERSION = "2.17.10"
    DEFAULT_APP_TOKEN = "33d57ade8c02dbc5a333db99ff9ae26a"
    AUTH_EXPORT_FORMAT = "ofbackup-auth"
    AUTH_EXPORT_VERSION = 1
    AUTH_EXPORT_FILENAME = "OFBackup-auth.json"
    MAX_AUTH_EXPORT_SIZE = 64 * 1024

    AUTH_TEST_SCRIPT = r"""
import sys
try:
    from ofscraper.main.open import load
    import ofscraper.managers.manager as manager
    from ofscraper.data.api import me
    load.systemSet(); load.settings_loader(); load.setdate()
    load.readConfig(); load.make_folder()
    manager.Manager = manager.mainManager()
    account = me.scrape_user()
    if isinstance(account, dict) and account.get("isAuth") is True:
        print("OFBACKUP_AUTH_OK"); raise SystemExit(0)
    print("OFBACKUP_AUTH_REJECTED"); raise SystemExit(3)
except SystemExit:
    raise
except Exception as exc:
    http_status = getattr(getattr(exc, "response", None), "status_code", None)
    if http_status in (400, 401):
        print("OFBACKUP_AUTH_REJECTED", file=sys.stderr)
    elif http_status == 403:
        print("OFBACKUP_AUTH_BLOCKED", file=sys.stderr)
    else:
        print(f"OFBACKUP_AUTH_ERROR:{type(exc).__name__}", file=sys.stderr)
    if http_status:
        print(f"HTTP {http_status}: {exc}", file=sys.stderr)
    else:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
    raise SystemExit(4)
"""

    def __init__(self, config_service=None):
        self._config = config_service

    # ── Paths ─────────────────────────────────────────────────────────────

    @property
    def home(self) -> Path:
        return Path.home()

    @property
    def auth_path(self) -> Path:
        ofscraper_dir = self.home / ".config" / "ofscraper"
        return ofscraper_dir / "main_profile" / "auth.json"

    @property
    def default_export_path(self) -> Path:
        configured = os.getenv("OFDOWNLOADER_AUTH_EXPORT")
        if configured:
            return Path(configured).expanduser()
        if os.name == "nt":
            return self.home / "Downloads" / self.AUTH_EXPORT_FILENAME
        return self.home / "storage" / "downloads" / self.AUTH_EXPORT_FILENAME

    # ── Parsing de cookies ────────────────────────────────────────────────

    def parse_cookie_header(self, raw: str) -> dict[str, str]:
        """Extrae valores de autenticación desde un header cookie o JSON exportado."""
        raw = raw.strip()
        try:
            exported = json.loads(raw)
        except json.JSONDecodeError:
            exported = None

        if isinstance(exported, dict):
            return self._parse_dict_export(exported)
        if isinstance(exported, list):
            return self._parse_list_export(exported)

        return self._parse_raw_cookie(raw)

    def _parse_dict_export(self, exported: dict) -> dict[str, str]:
        source = exported.get("auth", exported)
        if not isinstance(source, dict):
            return {}
        values: dict[str, str] = {}
        cookie = source.get("cookie")
        if isinstance(cookie, str):
            values.update(self.parse_cookie_header(cookie))
        for source_key, target_key in (
            ("sess", "sess"), ("auth_id", "auth_id"),
            ("x-bc", "x-bc"), ("x_bc", "x-bc"),
            ("user_agent", "user_agent"),
        ):
            value = source.get(source_key)
            if isinstance(value, str) and value.strip():
                values[target_key] = value.strip()
        return values

    def _parse_list_export(self, exported: list) -> dict[str, str]:
        allowed = {"sess", "auth_id", "x-bc", "x_bc", "user_agent", "userAgent", "User-Agent"}
        values: dict[str, str] = {}
        for item in exported:
            if not isinstance(item, dict):
                continue
            domain = str(item.get("domain", "")).lower().lstrip(".")
            name = str(item.get("name", ""))
            value = item.get("value")
            # Cookie-Editor y exportadores móviles pueden usar un subdominio
            # de OnlyFans en vez del dominio raíz (por ejemplo, cdn.onlyfans.com).
            # Nunca aceptamos cookies de dominios ajenos.
            is_onlyfans_domain = domain == "onlyfans.com" or domain.endswith(".onlyfans.com")
            if is_onlyfans_domain and name in allowed and isinstance(value, str):
                target_name = "x-bc" if name == "x_bc" else "user_agent" if name in {"userAgent", "User-Agent"} else name
                values[target_name] = value
            for source_key, target_key in (
                ("user_agent", "user_agent"),
                ("userAgent", "user_agent"),
                ("User-Agent", "user_agent"),
            ):
                user_agent = item.get(source_key)
                if isinstance(user_agent, str) and user_agent.strip():
                    values[target_key] = user_agent.strip()
        return values

    @staticmethod
    def _parse_raw_cookie(raw: str) -> dict[str, str]:
        raw = re.sub(r"^cookie\s*:\s*", "", raw, flags=re.IGNORECASE)
        values: dict[str, str] = {}
        jar = SimpleCookie()
        try:
            jar.load(raw)
            values.update({key: morsel.value for key, morsel in jar.items()})
        except Exception:
            pass
        for part in raw.split(";"):
            if "=" not in part:
                continue
            key, value = part.split("=", 1)
            key = key.strip()
            if key:
                values.setdefault(key, value.strip().strip('"'))
        return values

    # ── Validación ────────────────────────────────────────────────────────

    @staticmethod
    def _clean_field(name: str, value: object, max_length: int) -> str:
        if not isinstance(value, str):
            raise UserError(f"El campo {name} no es texto.")
        value = value.strip()
        if not value:
            raise UserError(f"Falta el campo {name}.")
        if len(value) > max_length or any(ord(char) < 32 for char in value):
            raise UserError(f"El campo {name} no tiene un formato válido.")
        return value

    def validate_auth_values(self, values: dict[str, str]) -> dict[str, str]:
        required = ("sess", "auth_id", "x-bc", "user_agent")
        missing = [k for k in required if not values.get(k)]
        if missing:
            readable = ["User-Agent" if k == "user_agent" else k for k in missing]
            raise UserError(
                "El archivo no trae todos los datos necesarios. "
                f"Falta: {', '.join(readable)}. "
                "Exporta de nuevo con OF Downloader Exporter desde la misma sesion."
            )
        cleaned = {
            "sess": self._clean_field("sess", values.get("sess"), 4096),
            "auth_id": self._clean_field("auth_id", values.get("auth_id"), 32),
            "x-bc": self._clean_field("x-bc", values.get("x-bc"), 512),
            "user_agent": self._clean_field("user_agent", values.get("user_agent"), 1024),
        }
        if not cleaned["auth_id"].isdigit():
            raise UserError("auth_id debe contener únicamente números.")
        return cleaned

    # ── Parseo de archivo exportado ───────────────────────────────────────

    def parse_auth_export(self, data: object) -> dict[str, str]:
        if not isinstance(data, dict):
            return self.validate_auth_values(
                self.parse_cookie_header(json.dumps(data, ensure_ascii=False))
            )
        if data.get("format") != self.AUTH_EXPORT_FORMAT:
            cookies = self.parse_cookie_header(json.dumps(data, ensure_ascii=False))
            if cookies:
                return self.validate_auth_values(cookies)
            raise UserError("El archivo no fue creado por OF Downloader Exporter.")
        if data.get("version") != self.AUTH_EXPORT_VERSION:
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
            "sess": self._clean_field("sess", auth.get("sess"), 4096),
            "auth_id": self._clean_field("auth_id", auth.get("auth_id"), 32),
            "x-bc": self._clean_field("x-bc", auth.get("x-bc"), 512),
            "user_agent": self._clean_field("user_agent", auth.get("user_agent"), 1024),
        }
        if not values["auth_id"].isdigit():
            raise UserError("auth_id debe contener únicamente números.")
        return values

    # ── Carga desde archivo ───────────────────────────────────────────────

    def load_auth_export(self, path: Path) -> tuple[dict[str, str], str]:
        path = path.expanduser()
        try:
            if not path.is_file():
                raise UserError("El archivo seleccionado no existe.")
            size = path.stat().st_size
            if size <= 0 or size > self.MAX_AUTH_EXPORT_SIZE:
                raise UserError("El archivo seleccionado está vacío o es demasiado grande.")
            raw = path.read_bytes()
            data = json.loads(raw.decode("utf-8"))
        except UserError:
            raise
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise UserError(f"No se pudo leer el archivo de acceso: {exc}") from exc
        return self.parse_auth_export(data), hashlib.sha256(raw).hexdigest()

    # ── Persistencia ──────────────────────────────────────────────────────

    def credentials_payload(self, values: dict[str, str]) -> dict[str, str]:
        return {
            "sess": values["sess"],
            "auth_id": values["auth_id"],
            "auth_uid": values["auth_id"],
            "user_agent": values["user_agent"],
            "x-bc": values["x-bc"],
            "app-token": self.DEFAULT_APP_TOKEN,
        }

    def save_credentials(self, values: dict[str, str]) -> None:
        from ofbackup_cli import secure_write_json, get_state, save_state, write_ofscraper_config
        secure_write_json(self.auth_path, self.credentials_payload(values))

    def credentials_ready(self) -> bool:
        try:
            data = self._read_json(self.auth_path)
        except UserError:
            return False
        return all(data.get(k) for k in ("sess", "auth_id", "x-bc", "user_agent"))

    # ── Importación ───────────────────────────────────────────────────────

    def import_credentials(self, path: Path) -> None:
        from ofbackup_cli import secure_write_json, get_state, save_state, write_ofscraper_config
        values, selected_hash = self.load_auth_export(path)
        secure_write_json(self.auth_path, self.credentials_payload(values))

        export_path = self.default_export_path
        if self._file_sha256(export_path) == selected_hash:
            try:
                export_path.unlink()
            except OSError:
                pass

        print("\n✓ Archivo válido y datos de acceso guardados.")
        print("Solo se conservaron sess, auth_id, x-bc y User-Agent.")
        print("Comprueba ahora la sesión ejecutando: of probar")

    # ── Verificación de sesión ────────────────────────────────────────────

    def test_credentials(self, timeout: int = 60) -> int:
        if not self.credentials_ready():
            print("Todavía no hay credenciales configuradas.")
            return 42  # IMPORT_REQUEST_EXIT

        try:
            process = subprocess.Popen(
                [sys.executable, "-c", self.AUTH_TEST_SCRIPT],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, encoding="utf-8", errors="replace",
                env=self._auth_test_environment(),
            )
        except OSError as exc:
            raise UserError(f"No se pudo iniciar la prueba de acceso: {exc}") from exc

        deadline = time.monotonic() + timeout
        frames = ("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏")
        frame = 0
        interactive = sys.stdout.isatty()

        while process.poll() is None and time.monotonic() < deadline:
            if interactive:
                remaining = max(0, int(deadline - time.monotonic()))
                print(f"\r{frames[frame % len(frames)]} Consultando… {remaining:02d}s ", end="", flush=True)
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
            print("\n✗ LA PRUEBA TARDÓ DEMASIADO")
            print("La cookie sí está cargada, pero OnlyFans no respondió a tiempo.")
            return 1

        stdout, stderr = process.communicate()
        if interactive:
            print("\r" + " " * 38 + "\r", end="", flush=True)
        output = f"{stdout}\n{stderr}"

        if process.returncode == 0 and "OFBACKUP_AUTH_OK" in output:
            print("\n✓ COOKIE VÁLIDA")
            print("OnlyFans aceptó la sesión. OF Downloader está listo para descargar.")
            return 0
        if "OFBACKUP_AUTH_REJECTED" in output:
            print("\n✗ COOKIE RECHAZADA O VENCIDA")
            return 1
        if "OFBACKUP_AUTH_BLOCKED" in output:
            print("\n✗ SOLICITUD BLOQUEADA (HTTP 403)")
            print("OnlyFans bloqueó la solicitud desde esta red o dispositivo.")
            print("Esto no confirma que la cookie esté vencida.")
            return 1
        print("\n✗ NO SE PUDO COMPROBAR LA COOKIE")
        return 1

    @staticmethod
    def _auth_test_environment() -> dict[str, str]:
        """Usa un solo intento para que la prueba sea rápida y diagnóstica."""
        environment = os.environ.copy()
        environment.update(
            {
                "PYTHONIOENCODING": "utf-8",
                "OFSC_NUM_RETRIES_SESSION_DEFAULT": "1",
                "OFSC_API_INDIVIDUAL_NUM_TRIES": "1",
                "OFSC_API_NUM_TRIES": "1",
                "OFSC_API_CHECK_NUM_TRIES": "1",
                "OFSC_GIT_NUM_TRIES": "1",
                "OFSC_MIN_WAIT_SESSION_DEFAULT": "0",
                "OFSC_MAX_WAIT_SESSION_DEFAULT": "0",
                "OFSC_MIN_WAIT_API": "0",
                "OFSC_MAX_WAIT_API": "0",
            }
        )
        return environment

    # ── Receptor local (extensión del navegador) ──────────────────────────

    def start_local_receiver(self, port: int = 8765, timeout: int = 300, *, show_qr: bool = False) -> int:
        code = f"{secrets.randbelow(1_000_000):06d}"
        pair_token = secrets.token_urlsafe(18)
        received: dict[str, object] = {"done": False, "error": "", "paired": False}

        auth_service = self

        class ReceiverHandler(BaseHTTPRequestHandler):
            server_version = "OFDownloaderCookieReceiver/1.0"

            def log_message(self, *args): pass

            def _send_json(self, status, payload):
                body = json.dumps(payload).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "Content-Type")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_OPTIONS(self):
                self._send_json(200, {"ok": True})

            def do_GET(self):
                if self.path.rstrip("/") == "/discover":
                    self._send_json(200, {"ok": True, "app": "OF Downloader",
                                          "version": auth_service.APP_VERSION, "pairing": True})
                    return
                self._send_json(200, {"ok": True, "app": "OF Downloader",
                                      "version": auth_service.APP_VERSION})

            def do_POST(self):
                if self.path.rstrip("/") == "/pair":
                    length = int(self.headers.get("Content-Length", "0"))
                    if length and length <= auth_service.MAX_AUTH_EXPORT_SIZE:
                        self.rfile.read(length)
                    received["paired"] = True
                    self._send_json(200, {"ok": True, "token": pair_token})
                    print("\n✓ Extension encontrada en la red local.")
                    return
                if self.path.rstrip("/") != "/upload":
                    self._send_json(404, {"ok": False, "error": "ruta invalida"})
                    return
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > auth_service.MAX_AUTH_EXPORT_SIZE:
                    self._send_json(413, {"ok": False, "error": "archivo demasiado grande"})
                    return
                try:
                    payload = json.loads(self.rfile.read(length).decode("utf-8"))
                except Exception:
                    self._send_json(400, {"ok": False, "error": "json invalido"})
                    return
                if str(payload.get("code", "")) != code and str(payload.get("token", "")) != pair_token:
                    self._send_json(403, {"ok": False, "error": "codigo incorrecto"})
                    return
                try:
                    values = auth_service.parse_auth_export(payload.get("auth"))
                    from ofbackup_cli import secure_write_json
                    secure_write_json(auth_service.auth_path, auth_service.credentials_payload(values))
                except UserError as exc:
                    self._send_json(400, {"ok": False, "error": str(exc)})
                    return
                received["done"] = True
                self._send_json(200, {"ok": True, "message": "Datos guardados."})

        host = "0.0.0.0"
        try:
            server = ThreadingHTTPServer((host, port), ReceiverHandler)
        except OSError as exc:
            raise UserError(f"No se pudo abrir el receptor en puerto {port}: {exc}") from exc

        server.timeout = 0.5
        ip = self._local_ip()
        quick_link = f"http://{ip}:{port}/?code={code}"
        expires_at = time.monotonic() + timeout

        print(f"\nRECIBIR COOKIE LOCAL")
        print(f"Enlace rapido: {quick_link}")
        print(f"Codigo: {code}")
        if show_qr:
            self._print_qr(quick_link)

        try:
            while time.monotonic() < expires_at and not received["done"]:
                server.handle_request()
        finally:
            server.server_close()

        if received["done"]:
            print("\n✓ Datos de acceso guardados.")
            return 0
        print("\nNo se recibio ningun archivo antes de que venciera el tiempo.")
        return 1

    # ── Helpers privados ──────────────────────────────────────────────────

    @staticmethod
    def _local_ip() -> str:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.connect(("8.8.8.8", 80))
                return sock.getsockname()[0]
        except OSError:
            return "127.0.0.1"

    @staticmethod
    def _print_qr(value: str) -> bool:
        executable = shutil.which("qrencode")
        if not executable:
            print("QR: no disponible.")
            return False
        subprocess.run([executable, "-t", "ANSIUTF8", value], check=False)
        return True

    @staticmethod
    def _file_sha256(path: Path) -> str | None:
        try:
            if not path.is_file() or path.stat().st_size > AuthService.MAX_AUTH_EXPORT_SIZE:
                return None
            return hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError:
            return None

    @staticmethod
    def _read_json(path: Path) -> dict:
        if not path.exists():
            return {}
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise UserError(f"No se pudo leer {path}: {exc}") from exc
        if not isinstance(value, dict):
            raise UserError(f"El archivo {path} no contiene un objeto JSON válido.")
        return value


# ── Singleton para usar desde ofbackup_cli y mantener compatibilidad ──────

_auth_service: AuthService | None = None


def get_auth_service() -> AuthService:
    global _auth_service
    if _auth_service is None:
        _auth_service = AuthService()
    return _auth_service


# ── Funciones de compatibilidad (delegan en AuthService) ─────────────────
# Permiten que el código existente en ofbackup_cli.py siga funcionando
# mientras se migra gradualmente a AuthService.


def configure_credentials() -> int:
    from ofbackup_cli import runtime_platform_name, IMPORT_REQUEST_EXIT, import_default_auth_export
    print("\nCONECTAR MI CUENTA")
    platform_name = runtime_platform_name()
    if platform_name in {"LINUX", "WINDOWS"}:
        import_default_auth_export()
        return 0
    return 42  # IMPORT_REQUEST_EXIT


def credentials_ready() -> bool:
    return get_auth_service().credentials_ready()


def require_credentials() -> None:
    if credentials_ready():
        return
    print("Todavía no hay credenciales configuradas.")
    if configure_credentials() == 42:
        raise UserError("Vuelve al menú y usa Conectar mi cuenta para abrir el selector.")


def import_credentials_file(path) -> None:
    get_auth_service().import_credentials(Path(path))


def test_credentials(timeout: int = 60) -> int:
    return get_auth_service().test_credentials(timeout=timeout)


def receive_credentials_locally(*, port: int = 8765, show_qr: bool = False) -> int:
    return get_auth_service().start_local_receiver(port=port, show_qr=show_qr)
