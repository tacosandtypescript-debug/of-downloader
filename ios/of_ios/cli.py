"""Interfaz de terminal nativa para a-Shell en iOS."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .api import ApiError, OnlyFansApi
from .config import ConfigError, DOWNLOAD_DIR, import_auth
from .media import download_posts


def cmd_import(path: str) -> int:
    import_auth(Path(path))
    print("✓ Archivo válido. Los cuatro campos de acceso se guardaron localmente.")
    print("No se mostraron cookies ni tokens.")
    print("Por seguridad, elimina el JSON original desde la app Archivos.")
    return 0


def cmd_test() -> int:
    print("Consultando la sesión sin descargar contenido…")
    OnlyFansApi().me()
    print("✓ COOKIE VÁLIDA: OnlyFans aceptó la sesión.")
    return 0


def cmd_profiles() -> int:
    profiles = OnlyFansApi().subscriptions()
    if not profiles:
        print("No se encontraron suscripciones activas.")
        return 1
    print(f"Suscripciones activas: {len(profiles)}")
    for index, profile in enumerate(profiles, start=1):
        print(f"[{index}] @{profile.get('username', 'sin_usuario')}")
    return 0


def cmd_user(value: str) -> int:
    api = OnlyFansApi()
    profile = api.profile(value)
    username = str(profile.get("username") or value).strip()
    print(f"Perfil: @{username}")
    print(f"Destino: {DOWNLOAD_DIR / username}")
    print("Descargando medios directos accesibles; DRM y bloqueados se omiten.")
    stats = download_posts(
        api.iter_posts(profile["id"]), DOWNLOAD_DIR, username, api.auth
    )
    print("\nResumen")
    print(f"  Publicaciones revisadas: {stats.posts}")
    print(f"  Descargados: {stats.downloaded}")
    print(f"  Ya existentes: {stats.existing}")
    print(f"  Bloqueados: {stats.locked}")
    print(f"  DRM omitidos: {stats.drm}")
    print(f"  Fallidos: {stats.failed}")
    return 0 if stats.failed == 0 else 2


def interactive() -> int:
    print(f"OF Downloader iOS nativo · {__version__}")
    print("[1] Probar acceso")
    print("[2] Ver suscripciones")
    print("[3] Descargar perfil")
    print("[4] Importar JSON")
    print("[0] Salir")
    choice = input("Opción: ").strip()
    if choice == "1":
        return cmd_test()
    if choice == "2":
        return cmd_profiles()
    if choice == "3":
        return cmd_user(input("Usuario o enlace: ").strip())
    if choice == "4":
        return cmd_import(input("Ruta del JSON: ").strip())
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="of-ios")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command")
    importer = sub.add_parser("importar", help="Importar OFBackup-auth.json")
    importer.add_argument("path")
    sub.add_parser("probar", help="Probar la sesión sin descargar")
    sub.add_parser("perfiles", help="Listar suscripciones activas")
    user = sub.add_parser("usuario", help="Descargar un perfil")
    user.add_argument("value")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "importar":
            return cmd_import(args.path)
        if args.command == "probar":
            return cmd_test()
        if args.command == "perfiles":
            return cmd_profiles()
        if args.command == "usuario":
            return cmd_user(args.value)
        return interactive()
    except (ConfigError, ApiError) as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nOperación cancelada.")
        return 130
