"""Modelos de dominio compartidos por los frontends."""

from __future__ import annotations

from dataclasses import dataclass, field


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
    seen_events: set[str] = field(default_factory=set, repr=False)

    def label(self, stage: str) -> str:
        parts: list[str] = []
        if self.detected_images is not None or self.downloaded.images:
            if self.detected_images is None:
                parts.append(f"Fotos {self.downloaded.images}")
            else:
                parts.append(f"Fotos {self.downloaded.images}/{self.detected_images}")
        if self.detected_videos is not None or self.downloaded.videos:
            if self.detected_videos is None:
                parts.append(f"Videos {self.downloaded.videos}")
            else:
                parts.append(f"Videos {self.downloaded.videos}/{self.detected_videos}")
        if self.failed:
            parts.append(f"Fallos {self.failed}")
        if self.skipped:
            parts.append(f"Omitidos {self.skipped}")
        if self.detected_total:
            remaining = max(0, self.detected_total - self.accounted_total)
            parts.append(
                f"Total {self.accounted_total}/{self.detected_total} | Restan {remaining}"
            )
        elif self.downloaded.total:
            parts.append(f"Total descargado {self.downloaded.total}")
        parts.append(stage)
        return " · ".join(parts)

    @property
    def detected_total(self) -> int:
        return (self.detected_images or 0) + (self.detected_videos or 0)

    @property
    def accounted_total(self) -> int:
        accounted = self.downloaded.total + self.skipped
        if self.detected_total:
            return min(accounted, self.detected_total)
        return accounted

    @property
    def has_unaccounted_detected_media(self) -> bool:
        return bool(self.detected_total and self.accounted_total < self.detected_total)
