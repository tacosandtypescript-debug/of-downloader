"""Modelos de dominio compartidos por los frontends."""

from __future__ import annotations

from dataclasses import dataclass, field
import time


class UserError(RuntimeError):
    """Error que se puede mostrar directamente al usuario."""


@dataclass
class MediaCounts:
    images: int = 0
    videos: int = 0
    other: int = 0

    @property
    def total(self) -> int:
        return self.images + self.videos + self.other


@dataclass
class DownloadStats:
    detected_images: int | None = None
    detected_videos: int | None = None
    downloaded: MediaCounts = field(default_factory=MediaCounts)
    failed: int = 0
    skipped: int = 0
    partial_files: int = 0
    processed_images: int | None = None
    processed_videos: int | None = None
    started_at: float | None = None
    seen_events: set[str] = field(default_factory=set, repr=False)

    def label(self, stage: str) -> str:
        parts: list[str] = []
        current_images = self.processed_images if self.processed_images is not None else self.downloaded.images
        current_videos = self.processed_videos if self.processed_videos is not None else self.downloaded.videos
        if self.detected_images is not None or current_images:
            if self.detected_images is None:
                parts.append(f"Fotos {current_images}")
            else:
                parts.append(f"Fotos {current_images}/{self.detected_images}")
        if self.detected_videos is not None or current_videos:
            if self.detected_videos is None:
                parts.append(f"Videos {current_videos}")
            else:
                parts.append(f"Videos {current_videos}/{self.detected_videos}")
        if self.failed:
            parts.append(f"Fallos {self.failed}")
        if self.skipped:
            parts.append(f"Omitidos {self.skipped}")
        if self.partial_files:
            parts.append(f"Temporales {self.partial_files}")
        if self.detected_total:
            remaining = max(0, self.detected_total - self.accounted_total)
            parts.append(
                f"Total {self.accounted_total}/{self.detected_total} | Restan {remaining}"
            )
        elif self.downloaded.total:
            parts.append(f"Total descargado {self.downloaded.total}")
        if self.started_at and self.accounted_total:
            elapsed = max(0.1, time.monotonic() - self.started_at)
            rate = self.accounted_total / elapsed
            parts.append(f"Velocidad {rate:.1f}/s")
            if self.detected_total and rate > 0:
                remaining = max(0, self.detected_total - self.accounted_total)
                eta = int(remaining / rate)
                minutes, seconds = divmod(eta, 60)
                parts.append(f"ETA {minutes:02d}:{seconds:02d}")
        parts.append(stage)
        return " · ".join(parts)

    @property
    def detected_total(self) -> int:
        return (self.detected_images or 0) + (self.detected_videos or 0)

    @property
    def accounted_total(self) -> int:
        accounted = self.downloaded.total + self.skipped
        processed = (self.processed_images or 0) + (self.processed_videos or 0)
        accounted = max(accounted, processed)
        if self.detected_total:
            return min(accounted, self.detected_total)
        return accounted

    @property
    def has_unaccounted_detected_media(self) -> bool:
        return bool(
            self.partial_files
            or (self.detected_total and self.accounted_total < self.detected_total)
        )


@dataclass
class ProfileDetection:
    username: str
    profile_id: str = ""
    posts: int | None = None
    photos: int | None = None
    videos: int | None = None
    archived: int | None = None
    counted: int | None = None
    declared: int | None = None
    accessible: int | None = None
    blocked: int | None = None
    partial: bool = False


@dataclass
class SubscriptionProfile:
    username: str
    display_name: str = ""
    profile_id: str = ""
    avatar_url: str = ""
    status: str = "activo"
    posts: int | None = None
    photos: int | None = None
    videos: int | None = None
    archived: int | None = None
