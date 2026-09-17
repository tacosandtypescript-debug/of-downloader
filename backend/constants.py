"""Constantes compartidas por los puntos de entrada de OF Downloader.

Fuente única de verdad para la versión de la aplicación y el app-token público
de OnlyFans. Este módulo no debe importar ningún otro módulo del proyecto para
evitar ciclos de importación.
"""

from __future__ import annotations

# Versión del CLI multiplataforma (Termux, Linux y Windows).
APP_VERSION = "2.17.11"

# Versión de OF-Scraper fijada en requirements/*.txt.
OFSCRAPER_VERSION = "3.14.7"

# Token público de la aplicación web de OnlyFans. No es un secreto de usuario:
# viaja en las peticiones de la web oficial y está publicado en Internet.
DEFAULT_APP_TOKEN = "33d57ade8c02dbc5a333db99ff9ae26a"

# Formato del archivo de acceso exportado por la extensión del navegador.
AUTH_EXPORT_FORMAT = "ofbackup-auth"
AUTH_EXPORT_VERSION = 1
AUTH_EXPORT_FILENAME = "OFBackup-auth.json"
MAX_AUTH_EXPORT_SIZE = 64 * 1024

__all__ = [
    "APP_VERSION",
    "AUTH_EXPORT_FILENAME",
    "AUTH_EXPORT_FORMAT",
    "AUTH_EXPORT_VERSION",
    "DEFAULT_APP_TOKEN",
    "MAX_AUTH_EXPORT_SIZE",
    "OFSCRAPER_VERSION",
]
