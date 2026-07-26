"""Servicios de perfiles y suscripciones."""

from __future__ import annotations


def _cli():
    import ofbackup_cli
    return ofbackup_cli


def list_subscription_profiles(timeout: int = 90):
    return _cli().list_subscription_profiles(timeout=timeout)


def detect_profile_counts(username: str, timeout: int = 120):
    return _cli().detect_profile_counts(username, timeout=timeout)


def choose_profile_and_download() -> int:
    return _cli().choose_profile_and_download()


def parse_subscriptions_stdout(stdout: str):
    return _cli().parse_subscriptions_stdout(stdout)

