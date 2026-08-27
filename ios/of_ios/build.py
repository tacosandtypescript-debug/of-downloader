"""Preparación local del motor nativo para a-Shell/iOS.

a-Shell ejecuta Python y no necesita compilar OF-Scraper ni extensiones C para
esta variante. Este módulo ofrece una comprobación explícita que compila los
módulos Python a bytecode, verifica que las carpetas permitidas sean
escribibles y deja un resultado claro antes de usar el menú.
"""

from __future__ import annotations

import compileall
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class BuildReport:
    """Resultado seguro de la preparación local del motor."""

    source_root: Path
    compiled: bool
    writable: bool

    @property
    def ok(self) -> bool:
        return self.compiled and self.writable


def _probe_writable(path: Path) -> bool:
    """Comprueba escritura y elimina solo un archivo temporal propio."""
    probe = path / ".of-ios-write-test"
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe.write_text("ok\n", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return True
    except OSError:
        try:
            probe.unlink(missing_ok=True)
        except OSError:
            pass
        return False


def prepare_engine(
    source_root: Path,
    app_home: Path,
    download_dir: Path,
) -> BuildReport:
    """Compila el árbol Python y comprueba el almacenamiento de la app."""
    compiled = compileall.compile_dir(
        str(source_root), quiet=1, force=True, legacy=False
    )
    writable = _probe_writable(app_home) and _probe_writable(download_dir)
    return BuildReport(
        source_root=source_root,
        compiled=compiled,
        writable=writable,
    )


def engine_source_root() -> Path:
    """Devuelve el directorio ``ios`` instalado o clonado."""
    return Path(__file__).resolve().parents[1]
