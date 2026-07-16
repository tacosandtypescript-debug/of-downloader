#!/usr/bin/env python3
"""Interfaz de terminal de OF Backup para Termux y Linux."""

from __future__ import annotations

import getpass
import json
import os
import re
import shutil
import subprocess
import sys
from http.cookies import SimpleCookie
from pathlib import Path


APP_VERSION = "2.0.0"
OFSCRAPER_VERSION = "3.14.7"
DEFAULT_APP_TOKEN = "33d57ade8c02dbc5a333db99ff9ae26a"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/146.0.0.0 Mobile Safari/537.36"
)

HOME = Path.home()
APP_DIR = HOME / ".config" / "ofbackup"
STATE_PATH = APP_DIR / "settings.json"
OFSCRAPER_DIR = HOME / ".config" / "ofscraper"
OFSCRAPER_CONFIG_PATH = OFSCRAPER_DIR / "config.json"
AUTH_PATH = OFSCRAPER_DIR / "main_profile" / "auth.json"


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


def hidden_prompt(label: str) -> str:
    try:
        return getpass.getpass(label).strip()
    except (EOFError, KeyboardInterrupt):
        raise
    except Exception:
        return input(label).strip()


def configure_credentials() -> None:
    print("\nCONFIGURAR CREDENCIALES")
    print("La entrada queda oculta y no se guarda en el historial de Termux.")
    raw_cookie = hidden_prompt("Pega la cabecera Cookie completa: ")
    cookies = parse_cookie_header(raw_cookie)

    sess = cookies.get("sess") or hidden_prompt("No encontré sess. Pega su valor: ")
    auth_id = cookies.get("auth_id") or hidden_prompt(
        "No encontré auth_id. Pega su valor: "
    )
    x_bc = hidden_prompt("Pega la cabecera x-bc: ")
    user_agent = input(
        "User-Agent (Enter para usar el valor Android recomendado): "
    ).strip() or DEFAULT_USER_AGENT
    username = input("Usuario predeterminado, sin @ (opcional): ").strip().lstrip("@")

    missing = [
        key
        for key, value in (("sess", sess), ("auth_id", auth_id), ("x-bc", x_bc))
        if not value
    ]
    if missing:
        raise UserError(f"Faltan credenciales: {', '.join(missing)}")

    payload = {
        "sess": sess,
        "auth_id": auth_id,
        "auth_uid": "",
        "user_agent": user_agent,
        "x-bc": x_bc,
        "app-token": DEFAULT_APP_TOKEN,
    }
    secure_write_json(AUTH_PATH, payload)

    state = get_state()
    if username:
        state["username"] = username
    save_state(state)
    write_ofscraper_config(state)
    print(f"\n✓ Credenciales guardadas con permisos privados en {AUTH_PATH}")


def write_ofscraper_config(state: dict | None = None) -> None:
    state = state or get_state()
    destination = Path(state["download_dir"]).expanduser()
    destination.mkdir(parents=True, exist_ok=True)

    data = read_json(OFSCRAPER_CONFIG_PATH, {"main_profile": "main_profile"})
    data["main_profile"] = "main_profile"
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
    configure_credentials()


def ofscraper_binary() -> str:
    configured = os.getenv("OFSCRAPER_BIN")
    executable = configured or shutil.which("ofscraper")
    if not executable:
        raise UserError(
            "No se encontró ofscraper. Ejecuta instalar-termux.sh o elige "
            "'Actualizar motor' en el menú."
        )
    return executable


def run_ofscraper(arguments: list[str]) -> int:
    require_credentials()
    write_ofscraper_config()
    executable = ofscraper_binary()
    print("\nIniciando OF-Scraper…\n")
    try:
        completed = subprocess.run([executable, *arguments], check=False)
    except OSError as exc:
        raise UserError(f"No se pudo iniciar OF-Scraper: {exc}") from exc
    if completed.returncode:
        print(f"\n✗ OF-Scraper terminó con código {completed.returncode}.")
    else:
        print(f"\n✓ Descarga terminada. Archivos en: {get_state()['download_dir']}")
    return completed.returncode


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
    executable = shutil.which("ofscraper")
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
        print("3. Configurar o renovar Cookie")
        print("4. Cambiar carpeta de descargas")
        print("5. Ver diagnóstico")
        print("6. Actualizar motor de descarga")
        print("0. Salir")
        print(f"\nDestino: {state['download_dir']}")
        choice = input("\nElige una opción: ").strip()
        try:
            if choice == "1":
                download_link()
            elif choice == "2":
                download_user()
            elif choice == "3":
                configure_credentials()
            elif choice == "4":
                change_destination()
            elif choice == "5":
                diagnostics()
            elif choice == "6":
                update_engine()
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
  ofbackup                         Abrir menú interactivo
  ofbackup ENLACE                 Descargar una publicación
  ofbackup usuario NOMBRE         Descargar todo un usuario
  ofbackup configurar             Guardar o renovar credenciales
  ofbackup diagnostico            Comprobar la instalación
  ofbackup actualizar             Actualizar el motor de descarga

Las credenciales se solicitan de forma oculta para que no queden en el
historial del terminal. Usa únicamente contenido al que tu cuenta tenga acceso.
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
            configure_credentials()
            return 0
        if command in {"diagnostico", "diagnóstico", "status"}:
            diagnostics()
            return 0
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
