"""Eventos ligeros para notificar cambios de trabajos en la cola."""

from __future__ import annotations

from dataclasses import dataclass
from queue import Empty, Queue
from threading import Lock
from typing import Any


@dataclass(frozen=True)
class QueueEvent:
    kind: str
    job_id: str | None
    payload: dict[str, Any]


class QueueEventBus:
    """Bus en memoria; permite añadir SSE/websocket sin acoplarlo al worker."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._subscribers: list[Queue[QueueEvent]] = []

    def subscribe(self) -> Queue[QueueEvent]:
        channel: Queue[QueueEvent] = Queue()
        with self._lock:
            self._subscribers.append(channel)
        return channel

    def unsubscribe(self, channel: Queue[QueueEvent]) -> None:
        with self._lock:
            if channel in self._subscribers:
                self._subscribers.remove(channel)

    def publish(self, event: QueueEvent) -> None:
        with self._lock:
            subscribers = tuple(self._subscribers)
        for channel in subscribers:
            channel.put_nowait(event)

    @staticmethod
    def next(channel: Queue[QueueEvent], timeout: float = 0.0) -> QueueEvent | None:
        try:
            return channel.get(timeout=timeout)
        except Empty:
            return None
