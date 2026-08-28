"""Preparación local del motor nativo para a-Shell/iOS.

a-Shell ejecuta Python y no necesita compilar OF-Scraper ni extensiones C para
esta variante. Este módulo ofrece una comprobación explícita que compila los
módulos Python a bytecode, verifica que las carpetas permitidas sean
escribibles y deja un resultado claro antes de usar el menú.
"""

from __future__ import annotations

import compileall
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class BuildReport:
    """Resultado seguro de la preparación local del motor."""

    source_root: Path
    compiled: bool
    writable: bool
    app_home: Path
    download_dir: Path
    app_home_error: str | None = None
    download_dir_error: str | None = None

    @property
    def ok(self) -> bool:
        return self.compiled and self.writable


def _probe_writable(path: Path) -> tuple[bool, str | None]:
    """Comprueba escritura y elimina solo un archivo temporal propio."""
    probe = path / f".of-ios-write-test-{os.getpid()}"
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe.write_text("ok\n", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return True, None
    except (OSError, TypeError, ValueError) as exc:
        try:
            probe.unlink(missing_ok=True)
        except (OSError, TypeError, ValueError):
            pass
        detail = str(exc).strip() or type(exc).__name__
        return False, f"{type(exc).__name__}: {detail}"


def prepare_engine(
    source_root: Path,
    app_home: Path,
    download_dir: Path,
) -> BuildReport:
    """Compila el árbol Python y comprueba el almacenamiento de la app."""
    compiled = compileall.compile_dir(
        str(source_root), quiet=1, force=True, legacy=False
    )
    app_home_ok, app_home_error = _probe_writable(app_home)
    download_dir_ok, download_dir_error = _probe_writable(download_dir)
    return BuildReport(
        source_root=source_root,
        compiled=compiled,
        writable=app_home_ok and download_dir_ok,
        app_home=app_home,
        download_dir=download_dir,
        app_home_error=app_home_error,
        download_dir_error=download_dir_error,
    )


def engine_source_root() -> Path:
    """Devuelve el directorio ``ios`` instalado o clonado."""
    return Path(__file__).resolve().parents[1]
