"""Notificaciones y estados visibles del CLI."""

from __future__ import annotations


def update_notification(status: str | None = None) -> str | None:
    from ofbackup_cli import update_notification as notification
    return notification(status)


def repository_update_badge(status: str | None = None) -> str:
    from ofbackup_cli import repository_update_badge as badge
    return badge(status)

