"""Cliente HTTPS secuencial de la API para a-Shell, sin dependencias externas."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen

from .config import RULES_PATH, _secure_write, load_auth


APP_TOKEN = "33d57ade8c02dbc5a333db99ff9ae26a"
API_ROOT = "https://onlyfans.com/api2/v2"
RULE_SOURCES = (
    "https://raw.githubusercontent.com/datawhores/onlyfans-dynamic-rules/main/dynamicRules.json",
    "https://raw.githubusercontent.com/xagler/dynamic-rules/main/onlyfans.json",
)
RULES_MAX_AGE = 6 * 60 * 60


class ApiError(RuntimeError):
    """Fallo de red/API redactado para no filtrar credenciales."""


@dataclass(frozen=True)
class SigningRules:
    static_param: str
    format: str
    checksum_indexes: tuple[int, ...]
    checksum_constant: int


def _read_json_url(url: str, headers: dict[str, str], timeout: int = 30) -> Any:
    request = Request(url, headers=headers, method="GET")
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _parse_rules(data: Any) -> SigningRules:
    if not isinstance(data, dict):
        raise ApiError("Las reglas de firma no tienen el formato esperado.")
    try:
        fmt = str(data["format"])
        if data.get("suffix"):
            fmt = f"{data['prefix']}:{{}}:{{:x}}:{data['suffix']}"
        indexes = tuple(int(value) for value in data["checksum_indexes"])
        rules = SigningRules(
            static_param=str(data["static_param"]),
            format=fmt,
            checksum_indexes=indexes,
            checksum_constant=int(data["checksum_constant"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ApiError("Las reglas de firma están incompletas.") from exc
    if not rules.static_param or not rules.format or not rules.checksum_indexes:
        raise ApiError("Las reglas de firma están vacías.")
    return rules


def load_signing_rules(force: bool = False) -> SigningRules:
    if not force and RULES_PATH.is_file():
        age = time.time() - RULES_PATH.stat().st_mtime
        if age < RULES_MAX_AGE:
            try:
                return _parse_rules(json.loads(RULES_PATH.read_text(encoding="utf-8")))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError, ApiError):
                pass

    last_error: Exception | None = None
    for source in RULE_SOURCES:
        try:
            data = _read_json_url(source, {"User-Agent": "OF-Downloader-iOS/0.1"})
            rules = _parse_rules(data)
            _secure_write(RULES_PATH, data)
            return rules
        except (HTTPError, URLError, TimeoutError, ValueError, ApiError) as exc:
            last_error = exc
    raise ApiError("No se pudieron actualizar las reglas de firma.") from last_error


def signed_headers(
    url: str,
    auth: dict[str, str],
    rules: SigningRules,
    now_ms: int | None = None,
) -> dict[str, str]:
    timestamp = str(now_ms if now_ms is not None else round(time.time() * 1000))
    parsed = urlsplit(url)
    path = parsed.path + (f"?{parsed.query}" if parsed.query else "")
    message = "\n".join((rules.static_param, timestamp, path, auth["auth_id"]))
    digest = hashlib.sha1(message.encode("utf-8"), usedforsecurity=False).hexdigest()
    digest_bytes = digest.encode("ascii")
    try:
        checksum = (
            sum(digest_bytes[index] for index in rules.checksum_indexes)
            + rules.checksum_constant
        )
    except IndexError as exc:
        raise ApiError("Las reglas de firma contienen índices inválidos.") from exc
    signature = rules.format.format(digest, abs(checksum))
    return {
        "accept": "application/json, text/plain, */*",
        "app-token": APP_TOKEN,
        "user-id": auth["auth_id"],
        "x-bc": auth["x-bc"],
        "referer": "https://onlyfans.com/",
        "user-agent": auth["user_agent"],
        "cookie": f"auth_id={auth['auth_id']}; sess={auth['sess']}",
        "sign": signature,
        "time": timestamp,
    }


class OnlyFansApi:
    def __init__(self) -> None:
        self.auth = load_auth()
        self.rules = load_signing_rules()

    def get_json(self, url: str, retries: int = 2) -> Any:
        last_error: Exception | None = None
        for attempt in range(retries + 1):
            try:
                return _read_json_url(url, signed_headers(url, self.auth, self.rules))
            except HTTPError as exc:
                if exc.code in {401, 403} and attempt == 0:
                    self.rules = load_signing_rules(force=True)
                    last_error = exc
                    continue
                if exc.code == 429 and attempt < retries:
                    time.sleep(2 + attempt * 2)
                    last_error = exc
                    continue
                raise ApiError(f"La API respondió HTTP {exc.code}.") from exc
            except (URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
                last_error = exc
                if attempt < retries:
                    time.sleep(1 + attempt)
                    continue
        raise ApiError("No se pudo completar la consulta HTTPS.") from last_error

    def me(self) -> dict[str, Any]:
        data = self.get_json(f"{API_ROOT}/users/me")
        if not isinstance(data, dict) or not data.get("id"):
            raise ApiError("La sesión no devolvió una cuenta válida.")
        return data

    def subscriptions(self) -> list[dict[str, Any]]:
        offset = 0
        profiles: list[dict[str, Any]] = []
        seen: set[int | str] = set()
        while True:
            url = (
                f"{API_ROOT}/subscriptions/subscribes?offset={offset}"
                "&limit=10&type=active&format=infinite"
            )
            data = self.get_json(url)
            batch = data.get("list", []) if isinstance(data, dict) else []
            if not isinstance(batch, list) or not batch:
                break
            for profile in batch:
                if isinstance(profile, dict) and profile.get("id") not in seen:
                    seen.add(profile.get("id"))
                    profiles.append(profile)
            if data.get("hasMore") is not True:
                break
            offset += len(batch)
        return profiles

    def profile(self, username: str) -> dict[str, Any]:
        raw = username.strip()
        parsed = urlsplit(raw if "://" in raw else f"https://onlyfans.com/{raw}")
        if parsed.netloc and parsed.netloc.lower() not in {"onlyfans.com", "www.onlyfans.com"}:
            raise ApiError("Solo se admiten perfiles de onlyfans.com.")
        clean = parsed.path.strip("/").split("/")[-1]
        if not clean or not all(ch.isalnum() or ch in "._-" for ch in clean):
            raise ApiError("El usuario o enlace no tiene un formato válido.")
        data = self.get_json(f"{API_ROOT}/users/{quote(clean)}")
        if not isinstance(data, dict) or not data.get("id"):
            raise ApiError("OnlyFans no devolvió ese perfil.")
        return data

    def iter_posts(self, model_id: int | str) -> Iterator[tuple[str, dict[str, Any]]]:
        categories = {
            "timeline": f"{API_ROOT}/users/{model_id}/posts",
            "archivados": f"{API_ROOT}/users/{model_id}/posts/archived",
            "streams": f"{API_ROOT}/users/{model_id}/posts/streams",
        }
        seen: set[int | str] = set()
        for category, base in categories.items():
            after: float | None = None
            while True:
                query = (
                    "limit=100&order=publish_date_asc&skip_users=all"
                    "&skip_users_dups=1&format=infinite"
                )
                if category == "timeline":
                    query += "&pinned=0"
                if after is not None:
                    query += f"&afterPublishTime={after}"
                data = self.get_json(f"{base}?{query}")
                batch = data.get("list", []) if isinstance(data, dict) else []
                if not isinstance(batch, list) or not batch:
                    break
                max_time = after or 0.0
                for post in batch:
                    if not isinstance(post, dict):
                        continue
                    post_id = post.get("id")
                    if post_id not in seen:
                        seen.add(post_id)
                        yield category, post
                    try:
                        max_time = max(max_time, float(post.get("postedAtPrecise", 0)))
                    except (TypeError, ValueError):
                        pass
                if data.get("hasMore") is not True or max_time == after:
                    break
                after = max_time
