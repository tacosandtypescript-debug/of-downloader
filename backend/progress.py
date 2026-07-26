"""Interpretación de eventos de progreso emitidos por OF-Scraper."""

from __future__ import annotations

import re

from .models import DownloadStats


def extract_download_percent(line: str) -> int | None:
    matches = re.findall(r"(?<!\d)(\d{1,3})(?:\.\d+)?%", line)
    if not matches:
        return None
    return min(100, max(0, int(matches[-1])))


def extract_media_totals(line: str) -> tuple[int | None, int | None]:
    image_patterns = (
        r"\b(?:images?|photos?|fotos?)\b\s*[:=]\s*(\d+)",
        r"\b(\d+)\s*(?:images?|photos?|fotos?)\b",
    )
    video_patterns = (
        r"\b(?:videos?|v[ií]deos?)\b\s*[:=]\s*(\d+)",
        r"\b(\d+)\s*(?:videos?|v[ií]deos?)\b",
    )

    def first_match(patterns: tuple[str, ...]) -> int | None:
        for pattern in patterns:
            match = re.search(pattern, line, flags=re.IGNORECASE)
            if match:
                return int(match.group(1))
        return None

    return first_match(image_patterns), first_match(video_patterns)


def update_download_stats_from_line(stats: DownloadStats, line: str) -> bool:
    changed = False
    images, videos = extract_media_totals(line)
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
        phrase in lowered
        for phrase in (
            "failed to download",
            "download failed",
            "error downloading",
            "download error",
            "could not download",
        )
    ):
        stats.failed += 1
        changed = True
    elif any(phrase in lowered for phrase in ("already downloaded", "skipped", "skip media")):
        stats.skipped += 1
        changed = True
    return changed

