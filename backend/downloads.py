"""Servicio de descargas para OF Downloader.

Centraliza la ejecución de OF-Scraper, progreso de descargas,
post-procesamiento de medios y utilidades de archivos.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

from backend.models import DownloadStats, MediaCounts, ProfileDetection, UserError

# Constantes de extensiones de archivo
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".avif"}
VIDEO_EXTENSIONS = {".mp4", ".m4v", ".mov", ".webm", ".mkv", ".avi", ".ts"}
PARTIAL_EXTENSIONS = {".part", ".partial", ".tmp", ".temp", ".download"}


class DownloadService:
    """Orquesta descargas con OF-Scraper y gestiona el ciclo de vida completo."""

    DOWNLOAD_LOG_NAME = "ultima-descarga.log"
    PROFILE_DOWNLOAD_AREAS = "Timeline,Archived,Pinned,Stories,Streams,Profile,Purchased"

    def __init__(self, config_service=None, auth_service=None):
        self._config = config_service
        self._auth = auth_service

    # ── Binarios ──────────────────────────────────────────────────────────

    @staticmethod
    def find_ofscraper() -> str | None:
        configured = os.getenv("OFSCRAPER_BIN")
        if configured:
            resolved = shutil.which(configured) or configured
            if Path(resolved).is_file():
                return str(Path(resolved))
        on_path = shutil.which("ofscraper")
        if on_path:
            return on_path
        scripts_dir = Path(sys.executable).parent
        for name in ("ofscraper", "ofscraper.exe"):
            candidate = scripts_dir / name
            if candidate.is_file():
                return str(candidate)
        return None

    def ofscraper_binary(self) -> str:
        exe = self.find_ofscraper()
        if not exe:
            raise UserError("No se encontró ofscraper.")
        return exe

    @staticmethod
    def find_ffmpeg() -> str | None:
        configured = os.getenv("FFMPEG_BIN") or os.getenv("IMAGEIO_FFMPEG_EXE")
        if configured:
            resolved = shutil.which(configured) or configured
            if Path(resolved).is_file():
                return str(Path(resolved))
        return shutil.which("ffmpeg")

    # ── Entorno y comandos ───────────────────────────────────────────────

    def build_command(self, executable: str, arguments: list[str]) -> list[str]:
        if arguments and arguments[0] == "manual":
            return [executable, "manual", "--auth-fail", *arguments[1:]]
        return [executable, "--auth-fail", *arguments]

    def environment(self) -> dict[str, str]:
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["OFSC_CDM_TEST_TIMEOUT"] = "8"
        env["OFSC_CDM_TEST_NUM_TRIES"] = "1"
        ffmpeg = self.find_ffmpeg()
        if ffmpeg:
            ffmpeg_dir = str(Path(ffmpeg).parent)
            env["PATH"] = ffmpeg_dir + os.pathsep + env.get("PATH", "")
            env.setdefault("FFMPEG_BIN", ffmpeg)
            env.setdefault("IMAGEIO_FFMPEG_EXE", ffmpeg)
        return env

    def build_profile_command(self, executable: str, username: str) -> list[str]:
        return [
            executable, "--auth-fail",
            username, "--dupe", "--no-auto-resume",
            "--download-area", self.PROFILE_DOWNLOAD_AREAS,
            "--ofscraper-dynamic-mode", "aiohttp",
            "--no-browser", "--no-cache", "--no-config-check",
        ]

    # ── Progreso ──────────────────────────────────────────────────────────

    @staticmethod
    def extract_percent(line: str) -> int | None:
        matches = re.findall(r"(?<!\d)(\d{1,3})(?:\.\d+)?%", line)
        if not matches:
            return None
        return min(100, max(0, int(matches[-1])))

    @staticmethod
    def extract_media_totals(line: str) -> tuple[int | None, int | None]:
        image_patterns = (
            r"\b(?:images?|photos?|fotos?)\b\s*[:=]\s*(\d+)",
            r"\b(\d+)\s*(?:images?|photos?|fotos?)\b",
        )
        video_patterns = (
            r"\b(?:videos?|v[ií]deos?)\b\s*[:=]\s*(\d+)",
            r"\b(\d+)\s*(?:videos?|v[ií]deos?)\b",
        )
        def first_match(patterns):
            for p in patterns:
                m = re.search(p, line, re.IGNORECASE)
                if m:
                    return int(m.group(1))
            return None
        return first_match(image_patterns), first_match(video_patterns)

    @staticmethod
    def update_stats(stats: DownloadStats, line: str) -> bool:
        changed = False
        images, videos = DownloadService.extract_media_totals(line)
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
            phrase in lowered for phrase in (
                "failed to download", "download failed", "error downloading",
                "download error", "could not download",
            )
        ):
            stats.failed += 1
            changed = True
        elif any(phrase in lowered for phrase in ("already downloaded", "skipped", "skip media")):
            stats.skipped += 1
            changed = True
        return changed

    # ── Medios en disco ───────────────────────────────────────────────────

    @staticmethod
    def media_kind(path: Path) -> str | None:
        suffix = path.suffix.lower()
        if suffix in PARTIAL_EXTENSIONS:
            return None
        if suffix in IMAGE_EXTENSIONS:
            return "images"
        if suffix in VIDEO_EXTENSIONS:
            return "videos"
        return None

    @staticmethod
    def media_snapshot(root: Path) -> dict[str, tuple[int, int]]:
        root = root.expanduser()
        if not root.exists():
            return {}
        snapshot: dict[str, tuple[int, int]] = {}
        try:
            for path in root.rglob("*"):
                try:
                    if not path.is_file() or DownloadService.media_kind(path) is None:
                        continue
                    stat = path.stat()
                except OSError:
                    continue
                snapshot[str(path)] = (stat.st_size, stat.st_mtime_ns)
        except OSError:
            pass
        return snapshot

    @staticmethod
    def partial_files(root: Path) -> list[Path]:
        root = root.expanduser()
        if not root.exists():
            return []
        files: list[Path] = []
        try:
            for path in root.rglob("*"):
                try:
                    if path.is_file() and path.suffix.lower() in PARTIAL_EXTENSIONS:
                        files.append(path)
                except OSError:
                    continue
        except OSError:
            pass
        return sorted(files, key=lambda p: str(p).lower())

    @staticmethod
    def count_changed(before: dict, after: dict) -> MediaCounts:
        counts = MediaCounts()
        for raw_path, signature in after.items():
            if before.get(raw_path) == signature:
                continue
            kind = DownloadService.media_kind(Path(raw_path))
            if kind == "images":
                counts.images += 1
            elif kind == "videos":
                counts.videos += 1
            else:
                counts.other += 1
        return counts

    @staticmethod
    def changed_files(before: dict, after: dict) -> list[Path]:
        files: list[Path] = []
        for raw_path, signature in after.items():
            if before.get(raw_path) == signature:
                continue
            if DownloadService.media_kind(Path(raw_path)) is not None:
                files.append(Path(raw_path))
        return sorted(files, key=lambda p: str(p).lower())

    # ── URLs y perfiles ───────────────────────────────────────────────────

    @staticmethod
    def normalize_url(value: str) -> str:
        value = value.strip().strip("'").strip('"')
        if not value.startswith(("http://", "https://")):
            value = "https://" + value.lstrip("/")
        return value

    @staticmethod
    def extract_of_url(value: str) -> str | None:
        import re as _re
        match = _re.search(r"(https?://onlyfans\.com/[^\s<>\"']+)", value)
        return match.group(1) if match else None

    @staticmethod
    def username_from_url(value: str) -> str | None:
        import re as _re
        match = _re.search(r"onlyfans\.com/([a-zA-Z0-9_.-]+)", value)
        return match.group(1) if match else None


# ── Singleton ────────────────────────────────────────────────────────────

_download_service: DownloadService | None = None


def get_download_service() -> DownloadService:
    global _download_service
    if _download_service is None:
        _download_service = DownloadService()
    return _download_service
