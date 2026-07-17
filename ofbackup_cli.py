#!/usr/bin/env python3
"""Interfaz de terminal de OF Backup para Termux y Linux."""

from __future__ import annotations

import getpass
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from http.cookies import SimpleCookie
from pathlib import Path


APP_VERSION = "2.3.3"
OFSCRAPER_VERSION = "3.14.7"
DEFAULT_APP_TOKEN = "33d57ade8c02dbc5a333db99ff9ae26a"
AUTH_EXPORT_FORMAT = "ofbackup-auth"
AUTH_EXPORT_VERSION = 1
AUTH_EXPORT_FILENAME = "OFBackup-auth.json"
MAX_AUTH_EXPORT_SIZE = 64 * 1024
IMPORT_REQUEST_EXIT = 42

HOME = Path.home()
APP_DIR = HOME / ".config" / "ofbackup"
STATE_PATH = APP_DIR / "settings.json"
OFSCRAPER_DIR = HOME / ".config" / "ofscraper"
OFSCRAPER_CONFIG_PATH = OFSCRAPER_DIR / "config.json"
AUTH_PATH = OFSCRAPER_DIR / "main_profile" / "auth.json"
EXPORTED_AUTH_PATH = HOME / "storage" / "downloads" / AUTH_EXPORT_FILENAME

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
    shared = HOME / "storage" / "downloads"
    return (shared if shared.exists() else HOME) / "OFBackup"


def get_state() -> dict:
    state = read_json(STATE_PATH)
    state.setdefault("download_dir", str(default_download_dir()))
    state.setdefault("username", "")
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


def parse_auth_export(data: object) -> dict[str, str]:
    if not isinstance(data, dict):
        raise UserError("El archivo de acceso no contiene un objeto JSON.")
    if data.get("format") != AUTH_EXPORT_FORMAT:
        raise UserError("El archivo no fue creado por OF Backup Exporter.")
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
    print("Elige el tipo de datos que has copiado:")
    print("1. Importar OFBackup-auth.json con el selector Android (recomendado)")
    print("2. Cookie normal en una sola línea")
    print("3. Lista JSON exportada por el navegador o una extensión")
    print("4. JSON completo de OnlyFans-Cookie-Helper")
    cookie_format = input("Opción [1]: ").strip() or "1"
    if cookie_format == "1":
        return IMPORT_REQUEST_EXIT
    if cookie_format == "3":
        raw_cookie = json_cookie_prompt()
    elif cookie_format == "4":
        raw_cookie = json_cookie_prompt(allow_object=True)
    elif cookie_format == "2":
        print("La entrada queda oculta y no se guarda en el historial de Termux.")
        raw_cookie = hidden_prompt("Pega la Cookie completa: ")
    else:
        raise UserError("Elige 1, 2, 3 o 4.")
    cookies = parse_cookie_header(raw_cookie)

    sess = cookies.get("sess") or hidden_prompt("No encontré sess. Pega su valor: ")
    auth_id = cookies.get("auth_id") or hidden_prompt(
        "No encontré auth_id. Pega su valor: "
    )
    x_bc = cookies.get("x-bc") or hidden_prompt(
        "Pega x-bc de la misma sesión del navegador: "
    )
    user_agent = cookies.get("user_agent") or input(
        "Pega el User-Agent exacto de esa misma sesión: "
    ).strip()
    username = input("Usuario predeterminado, sin @ (opcional): ").strip().lstrip("@")

    missing = [
        key
        for key, value in (
            ("sess", sess),
            ("auth_id", auth_id),
            ("x-bc", x_bc),
            ("User-Agent", user_agent),
        )
        if not value
    ]
    if missing:
        raise UserError(f"Faltan credenciales: {', '.join(missing)}")

    values = {
        "sess": sess,
        "auth_id": auth_id,
        "user_agent": user_agent,
        "x-bc": x_bc,
    }
    save_credentials(values, username)
    print("\n✓ Datos de acceso guardados.")
    print("OF-Scraper comprobará la cuenta al iniciar la próxima descarga.")
    print("Solo se guardaron los cuatro campos necesarios; el resto se descartó.")
    print(f"Archivo privado: {AUTH_PATH}")
    return 0


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
    if not sys.stdout.isatty():
        return message
    colors = {"green": "\033[32m", "red": "\033[31m", "yellow": "\033[33m"}
    return f"{colors[color]}{message}\033[0m"


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
        print("OnlyFans aceptó la sesión. OF Backup está listo para descargar.")
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


def build_ofscraper_command(executable: str, arguments: list[str]) -> list[str]:
    if arguments and arguments[0] == "manual":
        return [executable, "manual", "--auth-fail", *arguments[1:]]
    return [executable, "--auth-fail", *arguments]


def ofscraper_environment() -> dict[str, str]:
    """Evita que la comprobación externa de CDM bloquee mucho el inicio."""
    environment = os.environ.copy()
    environment["OFSC_CDM_TEST_TIMEOUT"] = "8"
    environment["OFSC_CDM_TEST_NUM_TRIES"] = "1"
    return environment


def run_ofscraper(arguments: list[str]) -> int:
    require_credentials()
    write_ofscraper_config()
    executable = ofscraper_binary()
    print("\nIniciando OF-Scraper…\n")
    print("La comprobación inicial de video puede tardar hasta unos 12 segundos.\n")
    traceback_seen = False
    auth_failed = False
    try:
        process = subprocess.Popen(
            build_ofscraper_command(executable, arguments),
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
            print(line, end="", flush=True)
            if "Traceback (most recent call last):" in line:
                traceback_seen = True
            if "Auth Failed" in line or "auth failed quitting on error" in line:
                auth_failed = True
        returncode = process.wait()
    except OSError as exc:
        raise UserError(f"No se pudo iniciar OF-Scraper: {exc}") from exc

    if returncode or traceback_seen or auth_failed:
        shown_code = returncode or 1
        print("\n✗ La descarga no se completó.")
        if auth_failed:
            print("OnlyFans rechazó los datos de acceso.")
            print("Abre la opción 3 y pega x-bc y User-Agent de la misma sesión.")
        elif traceback_seen and not returncode:
            print("OF-Scraper informó un error interno aunque devolvió código 0.")
        else:
            print(f"OF-Scraper terminó con código {returncode}.")
        print("No se mostrará un éxito falso. Revisa el error que aparece arriba.")
        return shown_code
    else:
        print(f"\n✓ Descarga terminada. Archivos en: {get_state()['download_dir']}")
        return 0


def normalize_url(value: str) -> str:
    value = value.strip()
    if re.fullmatch(r"\d+", value):
        return value
    if not re.match(r"^https://(?:www\.)?onlyfans\.com/", value, re.IGNORECASE):
        raise UserError("Introduce un enlace https://onlyfans.com/... o un ID numérico.")
    return value


def download_link(url: str | None = None) -> int:
    url = url or input("Pega el enlace de la publicación: ")
    return run_ofscraper(["manual", "--url", normalize_url(url), "--output", "normal"])


def download_user(username: str | None = None) -> int:
    state = get_state()
    username = (username or input("Usuario, sin @: ") or state.get("username", ""))
    username = username.strip().lstrip("@")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", username):
        raise UserError("El nombre de usuario no es válido.")
    state["username"] = username
    save_state(state)
    return run_ofscraper(
        [
            "--username",
            username,
            "--action",
            "download",
            "--posts",
            "all",
            "--mediatype",
            "images,videos",
            "--normal-only",
            "--no-live",
            "--output",
            "normal",
        ]
    )


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
    print(f"OF Backup:       {APP_VERSION}")
    print(f"Python:          {sys.version.split()[0]}")
    print(f"OF-Scraper:      {executable or 'NO ENCONTRADO'}")
    print(f"FFmpeg:          {shutil.which('ffmpeg') or 'NO ENCONTRADO'}")
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
        input("\nPulsa Enter para volver al menú…")
    except EOFError:
        pass


def menu() -> int:
    while True:
        state = get_state()
        print("\n" + "═" * 46)
        print("  OF BACKUP · TERMUX")
        print("═" * 46)
        print("1. Descargar una publicación con un enlace")
        print("2. Descargar todo un usuario")
        print("3. Conectar mi cuenta o renovar el acceso")
        print("4. Cambiar carpeta de descargas")
        print("5. Ver diagnóstico")
        print("6. Actualizar motor de descarga")
        print("7. Probar si la cookie funciona")
        print("0. Salir")
        print(f"\nDestino: {state['download_dir']}")
        choice = input("\nElige una opción: ").strip()
        try:
            if choice == "1":
                download_link()
            elif choice == "2":
                download_user()
            elif choice == "3":
                result = configure_credentials()
                if result == IMPORT_REQUEST_EXIT:
                    return IMPORT_REQUEST_EXIT
            elif choice == "4":
                change_destination()
            elif choice == "5":
                diagnostics()
            elif choice == "6":
                update_engine()
            elif choice == "7":
                result = test_credentials()
                if result == IMPORT_REQUEST_EXIT:
                    return IMPORT_REQUEST_EXIT
            elif choice == "0":
                print("Hasta luego.")
                return 0
            else:
                print("Opción no válida.")
        except UserError as exc:
            print(f"\n✗ {exc}")
        except KeyboardInterrupt:
            print("\nOperación cancelada.")
        pause()


def print_help() -> None:
    print(
        """Uso:
  of                               Abrir menú interactivo
  of ENLACE                        Descargar una publicación
  of usuario NOMBRE                Descargar todo un usuario
  of configurar                    Guardar o renovar credenciales
  of importar                      Elegir OFBackup-auth.json en Android
  of importar RUTA                 Importar el archivo directamente
  of probar                        Comprobar la cookie sin descargar contenido
  of diagnostico                   Comprobar la instalación
  of actualizar                    Actualizar el motor de descarga

Las credenciales se solicitan de forma oculta para que no queden en el
historial del terminal. Usa únicamente contenido al que tu cuenta tenga acceso.

El comando anterior `ofbackup` continúa disponible como alias.
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
        if command in {"configurar", "config"}:
            return configure_credentials()
        if command == "importar":
            return IMPORT_REQUEST_EXIT
        if command == "importar-archivo":
            if len(argv) != 2:
                raise UserError("Falta la ruta temporal del archivo seleccionado.")
            import_credentials_file(Path(argv[1]))
            return 0
        if command in {"diagnostico", "diagnóstico", "status"}:
            diagnostics()
            return 0
        if command in {"probar", "test", "comprobar"}:
            return test_credentials()
        if command in {"actualizar", "update"}:
            return update_engine()
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
