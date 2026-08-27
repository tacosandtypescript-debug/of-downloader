"""Extracción y descarga secuencial de medios accesibles en iOS."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from .api import ApiError


@dataclass
class DownloadStats:
    posts: int = 0
    downloaded: int = 0
    existing: int = 0
    locked: int = 0
    drm: int = 0
    unsupported: int = 0
    failed: int = 0


def safe_name(value: object, fallback: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value or "")).strip("._")
    return cleaned[:120] or fallback


def _direct_url(media: dict[str, Any]) -> str | None:
    def candidate(value: Any, depth: int = 0) -> str | None:
        if depth > 3:
            return None
        if isinstance(value, str):
            parsed = urlsplit(value)
            if parsed.scheme == "https" and parsed.netloc:
                return value
            return None
        if isinstance(value, dict):
            for key in ("url", "src", "download", "source", "original", "full", "preview", "thumb"):
                found = candidate(value.get(key), depth + 1)
                if found:
                    return found
        if isinstance(value, list):
            for item in value:
                found = candidate(item, depth + 1)
                if found:
                    return found
        return None

    files = media.get("files")
    if isinstance(files, dict):
        for quality in ("full", "preview", "thumb"):
            found = candidate(files.get(quality))
            if found:
                return found
    for value in (media.get("url"), media.get("src"), media.get("source"), media.get("download")):
        found = candidate(value)
        if found:
            return found
    return None


def iter_direct_media(post: dict[str, Any]) -> Iterable[tuple[dict[str, Any], str | None, str]]:
    media_list = post.get("media")
    if not isinstance(media_list, list):
        return
    for media in media_list:
        if not isinstance(media, dict):
            continue
        if (
            media.get("canView") is False
            or media.get("isBlocked") is True
            or media.get("isLocked") is True
            or media.get("locked") is True
        ):
            yield media, None, "locked"
            continue
        url = _direct_url(media)
        files = media.get("files")
        drm_flag = (
            media.get("isDrm") is True
            or media.get("drm") is True
            or (isinstance(files, dict) and bool(files.get("drm")))
        )
        if not url and drm_flag:
            yield media, None, "drm"
            continue
        if url and urlsplit(url).path.lower().endswith((".m3u8", ".mpd")):
            yield media, None, "unsupported"
            continue
        yield media, url, "direct" if url else "missing"


def _extension(url: str, media: dict[str, Any]) -> str:
    suffix = Path(urlsplit(url).path).suffix.lower()
    if suffix and len(suffix) <= 8:
        return suffix
    media_type = str(media.get("type", "")).lower()
    if "video" in media_type:
        return ".mp4"
    if "audio" in media_type:
        return ".mp3"
    return ".jpg"


def download_url(url: str, target: Path, user_agent: str, cookie: str) -> bool:
    if target.is_file() and target.stat().st_size > 0:
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_suffix(target.suffix + ".part")
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ApiError("La URL del medio no es válida.")
    request = Request(
        url,
        headers={"User-Agent": user_agent, "Cookie": cookie, "Referer": "https://onlyfans.com/"},
        method="GET",
    )
    try:
        with urlopen(request, timeout=60) as response, partial.open("wb") as output:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                output.write(chunk)
        if partial.stat().st_size <= 0:
            raise ApiError("El servidor devolvió un archivo vacío.")
        os.replace(partial, target)
        return True
    except ApiError:
        try:
            partial.unlink(missing_ok=True)
        except OSError:
            pass
        raise
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        try:
            partial.unlink(missing_ok=True)
        except OSError:
            pass
        raise ApiError("Falló una descarga de medio.") from exc


def download_posts(
    posts: Iterable[tuple[str, dict[str, Any]]],
    destination: Path,
    username: str,
    auth: dict[str, str],
) -> DownloadStats:
    stats = DownloadStats()
    cookie = f"auth_id={auth['auth_id']}; sess={auth['sess']}"
    for category, post in posts:
        stats.posts += 1
        post_id = safe_name(post.get("id"), f"post_{stats.posts}")
        for index, (media, url, status) in enumerate(iter_direct_media(post), start=1):
            if status == "locked":
                stats.locked += 1
                continue
            if status == "drm":
                stats.drm += 1
                continue
            if status == "unsupported":
                stats.unsupported += 1
                continue
            if not url:
                stats.failed += 1
                continue
            media_id = safe_name(media.get("id"), str(index))
            filename = f"{post_id}_{media_id}{_extension(url, media)}"
            target = destination / safe_name(username, "perfil") / category / filename
            try:
                if download_url(url, target, auth["user_agent"], cookie):
                    stats.downloaded += 1
                    print(f"  ✓ {category}/{filename}")
                else:
                    stats.existing += 1
            except ApiError:
                stats.failed += 1
                print(f"  ✗ No se pudo descargar {category}/{filename}")
    return stats
