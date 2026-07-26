"""Utilidades de clasificación y conteo de medios."""

from __future__ import annotations


def media_kind(path):
    import ofbackup_cli
    return ofbackup_cli.media_kind(path)


def count_changed_media(before, after):
    import ofbackup_cli
    return ofbackup_cli.count_changed_media(before, after)

