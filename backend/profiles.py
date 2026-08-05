"""Servicio de perfiles y suscripciones para OF Downloader.

Centraliza la detección de perfiles, listado de suscripciones,
y selección interactiva de perfiles para descargar.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time

from backend.models import (
    DownloadStats, MediaCounts, ProfileDetection,
    SubscriptionProfile, UserError,
)


class ProfileService:
    """Gestiona la detección y selección de perfiles de OnlyFans."""

    SUBSCRIPTIONS_LOG_NAME = "perfiles-suscritos.log"
    SUBSCRIPTIONS_SENTINEL = "OFDOWNLOADER_SUBSCRIPTIONS_JSON:"

    PROFILE_TEST_SCRIPT = r"""
import sys, traceback, logging
username = sys.argv[1]; sys.argv = [sys.argv[0]]
if not hasattr(logging.Logger, "trace"):
    logging.Logger.trace = logging.Logger.debug
if not hasattr(logging.Logger, "traceback_"):
    logging.Logger.traceback_ = logging.Logger.debug
try:
    from ofscraper.main.open import load
    import ofscraper.managers.manager as manager
    from ofscraper.data.api import (archive, highlights, paid, pinned, profile, streams, timeline)
    load.systemSet(); load.settings_loader(); load.setdate()
    load.readConfig(); load.make_folder()
    manager.Manager = manager.mainManager()
    data = profile.scrape_profile(username)
    if not isinstance(data, dict) or not data.get("id"):
        print("OFDOWNLOADER_PROFILE_EMPTY"); raise SystemExit(3)
    if data.get("username") == "deleted":
        print("OFDOWNLOADER_PROFILE_DELETED"); raise SystemExit(4)
    seen = set(); counts = {"photos":0,"videos":0,"accessible":0,"blocked":0}
    counted_posts = set(); partial_errors = []
    def walk_media(value):
        if isinstance(value, dict):
            media = value.get("media")
            if isinstance(media, (dict, list)): yield from walk_media(media)
            for key in ("attachments","mediaFiles","files"):
                nested = value.get(key)
                if isinstance(nested, (dict, list)): yield from walk_media(nested)
            media_type = str(value.get("type") or value.get("media_type") or "").lower()
            if media_type in {"photo","image","images","video","videos"}: yield value
            for key in ("preview","linkedPost","post"):
                nested = value.get(key)
                if isinstance(nested, (dict, list)): yield from walk_media(nested)
        elif isinstance(value, list):
            for item in value: yield from walk_media(item)
    def count_posts(area, posts):
        if not isinstance(posts, list): return
        for post in posts:
            if isinstance(post, dict) and post.get("id") is not None:
                counted_posts.add(str(post.get("id")))
            for media in walk_media(post):
                if not isinstance(media, dict): continue
                mid = media.get("id") or media.get("media_id") or ""
                mtype = str(media.get("type") or "").lower()
                key = str(mid or f"{area}:{mtype}:{len(seen)}")
                if key in seen: continue
                seen.add(key)
                blocked = (media.get("canView") is False or media.get("isLocked") is True
                           or media.get("unlocked") in {0, False})
                counts["blocked" if blocked else "accessible"] += 1
                if mtype in {"photo","image","images"}: counts["photos"] += 1
                elif mtype in {"video","videos"}: counts["videos"] += 1
    def try_area(area, func, *args, **kwargs):
        try: count_posts(area, func(*args, **kwargs))
        except Exception as exc: partial_errors.append(f"{area}:{type(exc).__name__}")
    mid = data.get("id"); muser = data.get("username") or username
    with manager.Manager.session.get_ofsession() as c:
        try_area("timeline", timeline.get_timeline_posts, mid, muser, c=c)
        try_area("archived", archive.get_archived_posts, mid, muser, c=c)
        try_area("pinned", pinned.get_pinned_posts, mid, c=c)
        try_area("stories", highlights.get_stories_post, mid, c=c)
        try_area("streams", streams.get_streams_posts, mid, muser, c=c)
        try_area("purchased", paid.get_paid_posts, muser, mid, c=c)
    pphotos = data.get("photosCount"); pvideos = data.get("videosCount")
    photos = pphotos if pphotos is not None else counts["photos"]
    videos = pvideos if pvideos is not None else counts["videos"]
    posts = len(counted_posts) if counted_posts else data.get("postsCount", 0)
    print(f"OFDOWNLOADER_PROFILE_OK username={data.get('username','')} id={data.get('id','')} "
          f"posts={posts} photos={photos} videos={videos} archived={data.get('archivedPostsCount',0)} "
          f"counted={len(seen)} declared={(int(pphotos or 0)+int(pvideos or 0))} "
          f"accessible={counts['accessible']} blocked={counts['blocked']} "
          f"area_errors={','.join(partial_errors) or 'none'} partial={1 if partial_errors else 0}")
    raise SystemExit(0)
except SystemExit: raise
except Exception as exc:
    print(f"OFDOWNLOADER_PROFILE_ERROR:{type(exc).__name__}", file=sys.stderr)
    raise SystemExit(5)
"""

    SUBSCRIPTIONS_LIST_SCRIPT = r"""
import json, sys
try:
    from ofscraper.main.open import load
    import ofscraper.managers.manager as manager
    from ofscraper.data.api.subscriptions import subscriptions
    load.systemSet(); load.settings_loader(); load.setdate()
    load.readConfig(); load.make_folder()
    manager.Manager = manager.mainManager()
    data = subscriptions.get_all_subscriptions(0, account="active")
    if not isinstance(data, list): data = []
    payload = "OFDOWNLOADER_SUBSCRIPTIONS_JSON:" + json.dumps(data, ensure_ascii=False) + "\n"
    sys.stdout.buffer.write(payload.encode("utf-8", errors="replace"))
    sys.stdout.flush()
    raise SystemExit(0)
except SystemExit: raise
except Exception as exc:
    print(f"OFDOWNLOADER_SUBSCRIPTIONS_ERROR:{type(exc).__name__}", file=sys.stderr)
    raise SystemExit(5)
"""

    def __init__(self, config_service=None, auth_service=None, download_service=None):
        self._config = config_service
        self._auth = auth_service
        self._download = download_service

    # ── Detección de perfil ───────────────────────────────────────────────

    def detect_profile(self, username: str, timeout: int = 120) -> ProfileDetection | None:
        if not self._check_ofscraper():
            return None
        try:
            process = subprocess.Popen(
                [sys.executable, "-c", self.PROFILE_TEST_SCRIPT, username],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, encoding="utf-8", errors="replace",
            )
        except OSError:
            return None

        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate()
            return None

        return self._parse_detection(f"{stdout}\n{stderr}")

    def test_profile(self, username: str, timeout: int = 120) -> int:
        from ofbackup_cli import (
            write_ofscraper_config, DOWNLOAD_LOG_PATH, PROFILE_TEST_LOG_NAME,
            styled, write_visible_log, default_download_dir,
        )
        detection = self.detect_profile(username, timeout)
        if detection is None:
            print(styled("\n✗ NO SE PUDO DETECTAR EL PERFIL", "red"))
            return 1

        print(styled(f"\n✓ PERFIL DETECTADO: {detection.username}", "green"))
        print(f"  ID: {detection.profile_id}")
        print(f"  Posts: {detection.posts}")
        print(f"  Fotos: {detection.photos}")
        print(f"  Videos: {detection.videos}")
        print(f"  Archivados: {detection.archived}")
        if detection.partial:
            print(styled("  ⚠ Datos parciales — algunas áreas no respondieron.", "yellow"))

        dest = default_download_dir()
        log_content = (
            f"OF Downloader — prueba de perfil\n"
            f"Usuario: {detection.username} (ID {detection.profile_id})\n"
            f"Posts: {detection.posts}, Fotos: {detection.photos}, Videos: {detection.videos}\n"
        )
        write_visible_log(dest, PROFILE_TEST_LOG_NAME, log_content)
        return 0

    # ── Suscripciones ─────────────────────────────────────────────────────

    def list_subscriptions(self, timeout: int = 90) -> list[SubscriptionProfile]:
        if not self._check_ofscraper():
            return []
        try:
            process = subprocess.Popen(
                [sys.executable, "-c", self.SUBSCRIPTIONS_LIST_SCRIPT],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, encoding="utf-8", errors="replace",
            )
        except OSError:
            return []

        try:
            stdout, _ = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate()
            return []

        return self._parse_subscriptions(stdout)

    # ── Parsing ───────────────────────────────────────────────────────────

    @staticmethod
    def _parse_detection(output: str) -> ProfileDetection | None:
        marker = "OFDOWNLOADER_PROFILE_OK "
        if marker not in output:
            return None
        line = [l for l in output.splitlines() if marker in l][0]
        fields = {}
        for part in line.split():
            if "=" in part:
                k, v = part.split("=", 1)
                fields[k] = v

        def opt_int(key):
            try:
                return int(fields.get(key, ""))
            except (ValueError, TypeError):
                return None

        return ProfileDetection(
            username=fields.get("username", ""),
            profile_id=fields.get("id", ""),
            posts=opt_int("posts"),
            photos=opt_int("photos"),
            videos=opt_int("videos"),
            archived=opt_int("archived"),
            counted=opt_int("counted"),
            declared=opt_int("declared"),
            accessible=opt_int("accessible"),
            blocked=opt_int("blocked"),
            partial=fields.get("partial") == "1",
        )

    @staticmethod
    def _parse_subscriptions(stdout: str) -> list[SubscriptionProfile]:
        marker = "OFDOWNLOADER_SUBSCRIPTIONS_JSON:"
        profiles: list[SubscriptionProfile] = []
        for line in stdout.splitlines():
            if marker not in line:
                continue
            try:
                data = json.loads(line.split(marker, 1)[1].strip())
            except json.JSONDecodeError:
                continue
            if not isinstance(data, list):
                continue
            for item in data:
                if not isinstance(item, dict):
                    continue
                status = "activo" if item.get("subscribedBy", True) else "expirado"
                profiles.append(SubscriptionProfile(
                    username=str(item.get("username", "")),
                    display_name=str(item.get("displayName", item.get("name", ""))),
                    profile_id=str(item.get("id", "")),
                    avatar_url=str(item.get("avatarUrl", item.get("avatar", ""))),
                    status=status,
                    posts=ProfileService._opt_int(item.get("postsCount")),
                    photos=ProfileService._opt_int(item.get("photosCount")),
                    videos=ProfileService._opt_int(item.get("videosCount")),
                    archived=ProfileService._opt_int(item.get("archivedPostsCount")),
                ))
        return profiles

    @staticmethod
    def _opt_int(value):
        try:
            return int(value)
        except (ValueError, TypeError):
            return None

    # ── Helpers ───────────────────────────────────────────────────────────

    def _check_ofscraper(self) -> bool:
        if self._download:
            return self._download.find_ofscraper() is not None
        from ofbackup_cli import find_ofscraper_binary
        return find_ofscraper_binary() is not None

    @staticmethod
    def compact_count(value: int | None) -> str:
        if value is None:
            return "?"
        if value >= 1_000_000:
            return f"{value / 1_000_000:.1f}M"
        if value >= 1_000:
            return f"{value / 1_000:.0f}k"
        return str(value)


# ── Singleton ────────────────────────────────────────────────────────────

_profile_service: ProfileService | None = None


def get_profile_service() -> ProfileService:
    global _profile_service
    if _profile_service is None:
        _profile_service = ProfileService()
    return _profile_service
