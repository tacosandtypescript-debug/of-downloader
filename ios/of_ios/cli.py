"""CLI nativa de OF Downloader para a-Shell en iOS, creada desde cero."""

from __future__ import annotations

import argparse
import platform
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from . import __version__
from .api import ApiError, OnlyFansApi
from .config import (
    APP_HOME,
    AUTH_PATH,
    ConfigError,
    DOWNLOAD_DIR,
    RULES_PATH,
    import_auth,
)
from .media import DownloadStats, download_posts


def _prompt(label: str) -> str:
    try:
        return input(label).strip()
    except (EOFError, OSError, KeyboardInterrupt):
        return ""


def cmd_import(path: str | None = None) -> int:
    imported = import_auth(Path(path) if path else None)
    print("✓ Archivo válido. Los cuatro campos de acceso se guardaron localmente.")
    print(f"Configuración privada: {imported}")
    print("No se mostraron cookies ni tokens.")
    print("Por seguridad, elimina el JSON original desde la app Archivos.")
    return 0


def cmd_test() -> int:
    print("Consultando la sesión sin descargar contenido…")
    OnlyFansApi().me()
    print("✓ COOKIE VÁLIDA: OnlyFans aceptó la sesión.")
    return 0


def fetch_profiles(api: OnlyFansApi) -> list[dict[str, Any]]:
    profiles = api.subscriptions()
    if not profiles:
        raise ApiError("No se encontraron suscripciones activas.")
    return profiles


def print_profiles(profiles: list[dict[str, Any]]) -> None:
    print(f"Suscripciones activas: {len(profiles)}")
    for index, profile in enumerate(profiles, start=1):
        print(f"[{index}] @{profile.get('username', 'sin_usuario')}")


def cmd_profiles() -> int:
    profiles = fetch_profiles(OnlyFansApi())
    print_profiles(profiles)
    return 0


def print_summary(stats: DownloadStats) -> None:
    print("\nResumen")
    print(f"  Publicaciones revisadas: {stats.posts}")
    print(f"  Descargados: {stats.downloaded}")
    print(f"  Ya existentes: {stats.existing}")
    print(f"  Bloqueados: {stats.locked}")
    print(f"  DRM omitidos: {stats.drm}")
    print(f"  Formatos no soportados: {stats.unsupported}")
    print(f"  Fallidos: {stats.failed}")


def download_profile(api: OnlyFansApi, profile: dict[str, Any]) -> int:
    username = str(profile.get("username") or "perfil").strip()
    print(f"Perfil: @{username}")
    print(f"Destino: {DOWNLOAD_DIR / username}")
    print("Descargando medios directos accesibles; DRM y bloqueados se omiten.")
    stats = download_posts(
        api.iter_posts(profile["id"]), DOWNLOAD_DIR, username, api.auth
    )
    print_summary(stats)
    return 0 if stats.failed == 0 else 2


def cmd_user(value: str) -> int:
    api = OnlyFansApi()
    return download_profile(api, api.profile(value))


def cmd_publication(value: str) -> int:
    api = OnlyFansApi()
    post = api.post(api.extract_post_id(value))
    author = post.get("user") or post.get("author") or {}
    if isinstance(author, dict):
        username = str(author.get("username") or "publicacion")
    else:
        username = "publicacion"
    print(f"Publicación: {post.get('id')}")
    print(f"Destino: {DOWNLOAD_DIR / username / 'publicaciones'}")
    print("Descargando los medios directos accesibles de la publicación.")
    stats = download_posts(
        [("publicaciones", post)], DOWNLOAD_DIR, username, api.auth
    )
    print_summary(stats)
    return 0 if stats.failed == 0 else 2


def cmd_target(value: str) -> int:
    """Mantiene el atajo del CLI original: `of URL` descarga el objetivo."""
    raw = value.strip()
    if not raw:
        raise ApiError("Falta el usuario, enlace o ID de publicación.")
    if raw.isdigit():
        return cmd_publication(raw)
    parsed = urlsplit(raw)
    if parsed.scheme and parsed.netloc:
        host = parsed.netloc.lower()
        if host not in {"onlyfans.com", "www.onlyfans.com"}:
            raise ApiError("Solo se admiten enlaces de onlyfans.com.")
        parts = [part for part in parsed.path.split("/") if part]
        if parts and parts[-1].isdigit():
            return cmd_publication(raw)
        return cmd_user(raw)
    return cmd_user(raw)


def cmd_profile_test(value: str) -> int:
    """Comprueba un perfil sin recorrer sus publicaciones."""
    api = OnlyFansApi()
    profile = api.profile(value)
    username = str(profile.get("username") or value).strip()
    print(f"✓ Perfil accesible: @{username} (ID {profile.get('id')})")
    return 0


def print_cookie_help() -> None:
    print("FLUJO DE ACCESO NATIVO PARA a-Shell")
    print("1. Exporta OFBackup-auth.json desde el dispositivo donde ya tienes la sesión.")
    print("2. En Archivos, copia el JSON a la carpeta de a-Shell.")
    print("3. Ejecuta: of importar OFBackup-auth.json")
    print("4. Comprueba: of probar")
    print("El JSON original se puede borrar después de importarlo.")


def cmd_choose_profile() -> int:
    api = OnlyFansApi()
    profiles = fetch_profiles(api)
    print_profiles(profiles)
    selected = _prompt("Número de perfil (Enter cancela): ")
    if not selected:
        print("Operación cancelada.")
        return 130
    try:
        index = int(selected)
    except ValueError as exc:
        raise ApiError("El número de perfil no es válido.") from exc
    if index < 1 or index > len(profiles):
        raise ApiError("El número de perfil está fuera de rango.")
    return download_profile(api, profiles[index - 1])


def cmd_diagnostic() -> int:
    print(f"OF Downloader iOS nativo · {__version__}")
    print(f"Python: {platform.python_version()}")
    print(f"Sistema: {platform.system()} {platform.release()}")
    print("Motor: biblioteca estándar de Python; sin OF-Scraper ni procesos hijos")
    print(f"Carpeta de aplicación: {APP_HOME}")
    print(f"Carpeta de descargas: {DOWNLOAD_DIR}")
    print(f"Acceso importado: {'sí' if AUTH_PATH.is_file() else 'no'}")
    print(f"Reglas dinámicas en caché: {'sí' if RULES_PATH.is_file() else 'no'}")
    return 0


def interactive() -> int:
    print(f"OF DOWNLOADER · iOS NATIVO · v{__version__}")
    print("\nDESCARGAS")
    print("[1] Elegir perfil de mis suscripciones")
    print("[2] Descargar perfil por usuario o enlace")
    print("[3] Descargar publicación por enlace")
    print("\nMI CUENTA")
    print("[4] Importar OFBackup-auth.json")
    print("[5] Probar acceso")
    print("\nHERRAMIENTAS")
    print("[6] Ver diagnóstico")
    print("[0] Salir")
    choice = _prompt("Opción: ")
    if choice == "1":
        return cmd_choose_profile()
    if choice == "2":
        value = _prompt("Usuario o enlace: ")
        return cmd_user(value) if value else 130
    if choice == "3":
        value = _prompt("Enlace o ID de publicación: ")
        return cmd_publication(value) if value else 130
    if choice == "4":
        path = _prompt("Ruta del JSON (Enter busca automáticamente): ")
        return cmd_import(path or None)
    if choice == "5":
        return cmd_test()
    if choice == "6":
        return cmd_diagnostic()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="of")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command")

    for name in ("importar", "importar-archivo"):
        importer = sub.add_parser(name, help="Importar OFBackup-auth.json")
        importer.add_argument("path", nargs="?", help="Ruta del JSON; opcional")
    for name in ("probar", "test", "comprobar"):
        sub.add_parser(name, help="Probar la sesión sin descargar")
    for name in ("perfiles", "suscripciones", "subs"):
        sub.add_parser(name, help="Listar suscripciones activas")
    for name in ("usuario", "perfil", "descargar-perfil"):
        user = sub.add_parser(name, help="Descargar un perfil")
        user.add_argument("value")
    for name in ("publicacion", "post", "descargar-publicacion"):
        publication = sub.add_parser(name, help="Descargar una publicación")
        publication.add_argument("value")
    for name in ("probar-perfil", "test-perfil", "perfil-test"):
        profile_test = sub.add_parser(name, help="Comprobar un perfil sin descargar")
        profile_test.add_argument("value")
    for name in ("diagnostico", "diagnóstico", "status"):
        sub.add_parser(name, help="Mostrar diagnóstico local")
    sub.add_parser("menu", help="Abrir el menú interactivo")
    return parser


def main(argv: list[str] | None = None) -> int:
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()
    if raw_argv and len(raw_argv) == 1 and not raw_argv[0].startswith("-"):
        direct = raw_argv[0]
        known = {
            "importar",
            "importar-archivo",
            "probar",
            "test",
            "comprobar",
            "perfiles",
            "suscripciones",
            "subs",
            "usuario",
            "perfil",
            "descargar-perfil",
            "publicacion",
            "post",
            "descargar-publicacion",
            "probar-perfil",
            "test-perfil",
            "perfil-test",
            "diagnostico",
            "diagnóstico",
            "status",
            "menu",
            "ayuda",
            "help",
            "cookie",
            "cookies",
            "acceso",
        }
        if direct.lower() not in known:
            try:
                return cmd_target(direct)
            except (ConfigError, ApiError) as exc:
                print(f"✗ {exc}", file=sys.stderr)
                return 1
    if raw_argv and raw_argv[0].lower() in {"ayuda", "help", "-h", "--help"}:
        parser.print_help()
        return 0
    if raw_argv and raw_argv[0].lower() in {"cookie", "cookies", "acceso"}:
        print_cookie_help()
        return 0
    args = parser.parse_args(raw_argv)
    try:
        if args.command in {"importar", "importar-archivo"}:
            return cmd_import(args.path)
        if args.command in {"probar", "test", "comprobar"}:
            return cmd_test()
        if args.command in {"perfiles", "suscripciones", "subs"}:
            return cmd_profiles()
        if args.command in {"usuario", "perfil", "descargar-perfil"}:
            return cmd_user(args.value)
        if args.command in {"publicacion", "post", "descargar-publicacion"}:
            return cmd_publication(args.value)
        if args.command in {"probar-perfil", "test-perfil", "perfil-test"}:
            return cmd_profile_test(args.value)
        if args.command in {"diagnostico", "diagnóstico", "status"}:
            return cmd_diagnostic()
        return interactive()
    except (ConfigError, ApiError) as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nOperación cancelada.")
        return 130
