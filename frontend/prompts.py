"""Entrada de usuario del CLI."""

from __future__ import annotations


def hidden_prompt(label: str) -> str:
    from ofbackup_cli import hidden_prompt as prompt
    return prompt(label)


def json_cookie_prompt(*, allow_object: bool = False) -> str:
    from ofbackup_cli import json_cookie_prompt as prompt
    return prompt(allow_object=allow_object)

