"""Autoprueba local del motor nativo para ejecutarse dentro de a-Shell."""

from __future__ import annotations

import importlib
import platform
from dataclasses import dataclass
from pathlib import Path

from .build import prepare_engine
from .config import AUTH_PATH, ConfigError, load_auth


@dataclass(frozen=True)
class SelfTestReport:
    """Resultado no sensible de la instalación local."""

    python_ok: bool
    stdlib_ok: bool
    source_ok: bool
    compiled_ok: bool
    storage_ok: bool
    auth_ok: bool | None
    python_version: str
    system: str
    source_root: Path
    app_home: Path
    download_dir: Path

    @property
    def ok(self) -> bool:
        """La ausencia de una sesión todavía no invalida la instalación."""
        return (
            self.python_ok
            and self.stdlib_ok
            and self.source_ok
            and self.compiled_ok
            and self.storage_ok
            and self.auth_ok is not False
        )


def _check_stdlib() -> bool:
    """Confirma los módulos que usa el motor sin instalar paquetes."""
    try:
        for module in (
            "argparse",
            "compileall",
            "hashlib",
            "http.cookies",
            "json",
            "urllib.request",
        ):
            importlib.import_module(module)
    except (ImportError, ModuleNotFoundError):
        return False
    return True


def _check_auth() -> bool | None:
    """Comprueba solo la forma de la sesión; jamás devuelve sus valores."""
    if not AUTH_PATH.is_file():
        return None
    try:
        load_auth()
    except ConfigError:
        return False
    return True


def run_selftest(
    source_root: Path,
    app_home: Path,
    download_dir: Path,
) -> SelfTestReport:
    """Compila y comprueba el entorno local sin llamar a OnlyFans."""
    try:
        report = prepare_engine(source_root, app_home, download_dir)
    except (OSError, RuntimeError, ValueError):
        report = None

    source_ok = source_root.is_dir() and all(
        (source_root / path).is_file()
        for path in (
            "of-ios.py",
            "of_ios/__init__.py",
            "of_ios/config.py",
            "of_ios/api.py",
            "of_ios/media.py",
            "of_ios/cli.py",
            "of_ios/selftest.py",
        )
    )
    return SelfTestReport(
        python_ok=platform.python_version_tuple()[0] == "3",
        stdlib_ok=_check_stdlib(),
        source_ok=source_ok,
        compiled_ok=bool(report and report.compiled),
        storage_ok=bool(report and report.writable),
        auth_ok=_check_auth(),
        python_version=platform.python_version(),
        system=f"{platform.system()} {platform.release()}".strip(),
        source_root=source_root,
        app_home=app_home,
        download_dir=download_dir,
    )
