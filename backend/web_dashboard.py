"""Servidor web local del dashboard de OF Downloader para Linux y Windows."""

from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import os
from pathlib import Path
from queue import Queue
import re
import secrets
import shutil
import subprocess
import sys
from threading import Lock, Thread
import time
from typing import Any
from urllib.parse import parse_qs, urlparse
import webbrowser

from backend.process import PausableProcess


MAX_REQUEST_SIZE = 96 * 1024
ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
PERCENT_RE = re.compile(r"(?<!\d)(\d{1,3})%")
PROFILE_CACHE_TTL = 15 * 60
FILE_RE = re.compile(
    r"(?P<file>[A-Za-z]:[\\/][^\r\n]*\.(?:jpg|jpeg|png|webp|gif|bmp|avif|mp4|m4v|mov|webm|mkv|avi|ts|part|partial|tmp)|(?<![\w/])[\w.-]+\.(?:jpg|jpeg|png|webp|gif|bmp|avif|mp4|m4v|mov|webm|mkv|avi|ts|part|partial|tmp))\b",
    re.IGNORECASE,
)


def _cli():
    import ofbackup_cli

    return ofbackup_cli


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def repair_dashboard_encoding(text: str) -> str:
    """Corrige textos antiguos guardados con una doble conversión UTF-8."""
    replacements = {
        "ÃƒÂ¡": "á", "ÃƒÂ©": "é", "ÃƒÂ­": "í", "ÃƒÂ³": "ó", "ÃƒÂº": "ú",
        "ÃƒÂ±": "ñ", "ÃƒÂ‰": "É", "Ãƒâ€œ": "Ó", "ÃƒÅ¡": "Ú", "Ãƒâ€˜": "Ñ",
        "Ã¡": "á", "Ã©": "é", "Ã­": "í", "Ã³": "ó", "Ãº": "ú", "Ã±": "ñ",
        "Ã‰": "É", "Ã“": "Ó", "Ãš": "Ú", "Ã‘": "Ñ", "Â·": "·",
        "â€¦": "…", "â€”": "—", "â†�": "←", "âœ“": "✓", "â”€": "─",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    return text


def _public_job(job: "DashboardJob") -> dict[str, Any]:
    data = asdict(job)
    data.pop("process", None)
    data.pop("controller", None)
    data.pop("cancel_requested", None)
    return data


@dataclass
class DashboardJob:
    id: str
    target: str
    kind: str
    options: dict[str, Any] = field(default_factory=dict)
    status: str = "queued"
    progress: int | None = None
    current_file: str = ""
    detected_images: int | None = None
    processed_images: int = 0
    detected_videos: int | None = None
    processed_videos: int = 0
    skipped: int = 0
    failed: int = 0
    partial_files: int = 0
    speed: str = ""
    eta: str = ""
    log_path: str = ""
    message: str = "En cola"
    created_at: str = field(default_factory=_utc_now)
    started_at: str | None = None
    finished_at: str | None = None
    returncode: int | None = None
    process: subprocess.Popen[str] | None = field(default=None, repr=False)
    controller: PausableProcess | None = field(default=None, repr=False)
    cancel_requested: bool = field(default=False, repr=False)


def update_dashboard_job_from_line(job: DashboardJob, line: str) -> None:
    """Actualiza el estado visible con una línea real del motor."""
    image = re.search(r"\b(?:Fotos|Images?)\s+(\d+)\s*/\s*(\d+)", line, re.I)
    video = re.search(r"\b(?:Videos?|Vídeos?)\s+(\d+)\s*/\s*(\d+)", line, re.I)
    if image:
        job.processed_images, job.detected_images = map(int, image.groups())
    if video:
        job.processed_videos, job.detected_videos = map(int, video.groups())
    for pattern, attribute in (
        (r"\b(?:Omitidos?|Skipped)\s*[:=]?\s*(\d+)", "skipped"),
        (r"\b(?:Fallos?|Failed)\s*[:=]?\s*(\d+)", "failed"),
        (r"\b(?:Temporales?|Partials?)\s*[:=]?\s*(\d+)", "partial_files"),
    ):
        found = re.search(pattern, line, re.I)
        if found:
            setattr(job, attribute, int(found.group(1)))
    speed = re.search(r"\b(?:Velocidad|Speed)\s*[:=]?\s*([\d.,]+\s*(?:KB|MB|GB)?/?s)", line, re.I)
    eta = re.search(r"\bETA\s*[:=]?\s*([\d:]+)", line, re.I)
    if speed:
        job.speed = speed.group(1)
    if eta:
        job.eta = eta.group(1)
    found_file = FILE_RE.search(line)
    if found_file:
        job.current_file = found_file.group("file").strip(" \t-·")


class JobManager:
    """Cola secuencial para no ejecutar varias descargas a la vez."""

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self._jobs: list[DashboardJob] = []
        self._lock = Lock()
        self._queue: Queue[str] = Queue()
        self._load_persisted_jobs()
        Thread(target=self._worker, daemon=True, name="ofd-dashboard-jobs").start()

    @property
    def _jobs_path(self) -> Path:
        return Path(_cli().APP_DIR) / "dashboard-jobs.json"

    def _persist(self) -> None:
        try:
            _cli().secure_write_json(self._jobs_path, {"jobs": self.snapshot()[-50:]})
        except (OSError, _cli().UserError):
            pass

    def _load_persisted_jobs(self) -> None:
        try:
            payload = _cli().read_json(self._jobs_path)
            rows = payload.get("jobs", [])
            if not isinstance(rows, list):
                return
            allowed = {item.name for item in fields(DashboardJob) if item.init}
            loaded: list[DashboardJob] = []
            for row in rows[-50:]:
                if not isinstance(row, dict):
                    continue
                values = {key: value for key, value in row.items() if key in allowed}
                if not values.get("id") or not values.get("target"):
                    continue
                if values.get("status") in {"running", "paused", "queued"}:
                    values["status"] = "error"
                    values["message"] = "Trabajo interrumpido al cerrar el dashboard"
                    values["finished_at"] = _utc_now()
                loaded.append(DashboardJob(**values))
            self._jobs = loaded
        except (OSError, TypeError, ValueError, _cli().UserError):
            self._jobs = []

    def add(self, target: str, options: dict[str, Any] | None = None) -> dict[str, Any]:
        cli = _cli()
        target = target.strip()
        if not target:
            raise cli.UserError("Escribe un usuario, enlace o ID.")
        username = cli.profile_username(target)
        requested_kind = str(options.get("kind", "auto")) if isinstance(options, dict) else "auto"
        if requested_kind == "profile" and not username:
            raise cli.UserError("El tipo Perfil completo necesita un usuario o enlace de perfil.")
        if requested_kind == "post" and username:
            raise cli.UserError("El tipo Publicación necesita un enlace o ID de publicación.")
        if username:
            normalized, kind = username, "profile"
        else:
            normalized, kind = cli.normalize_url(target), "post"
        options = options or {}
        media_type = str(options.get("media_type", "images,videos"))
        if media_type not in {"images", "videos", "images,videos"}:
            raise cli.UserError("Tipo de contenido no válido.")
        job = DashboardJob(
            id=secrets.token_hex(6),
            target=normalized,
            kind=kind,
            options={
                "media_type": media_type,
                "rescan": bool(options.get("rescan", True)),
                "force_all": bool(options.get("force_all", True)),
            },
        )
        with self._lock:
            self._jobs.append(job)
            self._jobs = self._jobs[-50:]
        self._persist()
        self._queue.put(job.id)
        return _public_job(job)

    def snapshot(self) -> list[dict[str, Any]]:
        with self._lock:
            return [_public_job(job) for job in self._jobs]

    def has_pending_work(self) -> bool:
        with self._lock:
            return any(job.status in {"queued", "running", "paused"} for job in self._jobs)

    def cancel_all(self) -> None:
        with self._lock:
            job_ids = [job.id for job in self._jobs if job.status in {"queued", "running", "paused"}]
        for job_id in job_ids:
            try:
                self.cancel(job_id)
            except (KeyError, RuntimeError):
                continue

    def _find(self, job_id: str) -> DashboardJob:
        with self._lock:
            job = next((item for item in self._jobs if item.id == job_id), None)
        if job is None:
            raise KeyError(job_id)
        return job

    def pause(self, job_id: str) -> dict[str, Any]:
        job = self._find(job_id)
        if job.status != "running" or not job.controller:
            raise RuntimeError("Ese trabajo no está ejecutándose.")
        if not job.controller.pause():
            raise RuntimeError("No se pudo pausar el proceso.")
        with self._lock:
            job.status = "paused"
            job.message = "Descarga pausada"
        self._persist()
        return _public_job(job)

    def resume(self, job_id: str) -> dict[str, Any]:
        job = self._find(job_id)
        if job.status != "paused" or not job.controller:
            raise RuntimeError("Ese trabajo no está pausado.")
        if not job.controller.resume():
            raise RuntimeError("No se pudo reanudar el proceso.")
        with self._lock:
            job.status = "running"
            job.message = "Descarga reanudada"
        self._persist()
        return _public_job(job)

    def cancel(self, job_id: str) -> dict[str, Any]:
        job = self._find(job_id)
        with self._lock:
            if job.status == "queued":
                job.cancel_requested = True
                job.status = "cancelled"
                job.message = "Cancelado antes de iniciar"
                job.finished_at = _utc_now()
                result = _public_job(job)
                persist_cancel = True
            else:
                persist_cancel = False
                result = None
        if persist_cancel:
            self._persist()
            return result
        with self._lock:
            process = job.process
            job.cancel_requested = True
        if process and process.poll() is None:
            try:
                if job.controller and job.controller.terminate():
                    return _public_job(job)
                process.terminate()
            except OSError:
                pass
        return _public_job(job)

    def _worker(self) -> None:
        while True:
            job_id = self._queue.get()
            try:
                job = self._find(job_id)
                if job.cancel_requested or job.status == "cancelled":
                    continue
                self._run(job)
            finally:
                self._queue.task_done()

    def _run(self, job: DashboardJob) -> None:
        cli_path = self.project_root / "ofbackup_cli.py"
        command = [
            sys.executable,
            str(cli_path),
            "descargar-web",
            job.target,
            f"--media={job.options.get('media_type', 'images,videos')}",
            f"--rescan={'1' if job.options.get('rescan', True) else '0'}",
            f"--force-all={'1' if job.options.get('force_all', True) else '0'}",
        ]
        env = os.environ.copy()
        env["OFDOWNLOADER_EXTERNAL_PAUSE"] = "1"
        env["PYTHONUNBUFFERED"] = "1"
        with self._lock:
            job.status = "running"
            job.message = "Preparando descarga"
            job.started_at = _utc_now()
            try:
                job.log_path = str(
                    Path(_cli().get_state()["download_dir"]).expanduser()
                    / _cli().PUBLIC_DOWNLOAD_LOG_NAME
                )
            except (KeyError, OSError, _cli().UserError):
                job.log_path = ""
        self._persist()
        try:
            process = subprocess.Popen(
                command,
                cwd=str(self.project_root),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                env=env,
            )
        except OSError as exc:
            with self._lock:
                job.status = "error"
                job.message = f"No se pudo iniciar: {exc}"
                job.finished_at = _utc_now()
                job.returncode = 1
                if job.log_path:
                    job.message = f"{job.message} · Log: {job.log_path}"
            self._persist()
            return
        with self._lock:
            job.process = process
            job.controller = PausableProcess(process.pid)
        last_persist = time.monotonic()
        if process.stdout is not None:
            for raw_line in process.stdout:
                line = ANSI_RE.sub("", raw_line).strip()
                if not line:
                    continue
                match = PERCENT_RE.search(line)
                with self._lock:
                    if match:
                        job.progress = max(0, min(100, int(match.group(1))))
                    update_dashboard_job_from_line(job, line)
                    job.message = line[-220:]
                if time.monotonic() - last_persist >= 1:
                    self._persist()
                    last_persist = time.monotonic()
        returncode = process.wait()
        with self._lock:
            job.returncode = returncode
            job.finished_at = _utc_now()
            job.process = None
            job.controller = None
            if job.cancel_requested:
                job.status = "cancelled"
                job.message = "Descarga cancelada"
            elif returncode == 0:
                job.status = "completed"
                job.progress = 100
                job.message = "Descarga completada"
            else:
                job.status = "error"
                if job.log_path:
                    job.message = f"{job.message} · Log: {job.log_path}"
                if not job.message:
                    job.message = f"El proceso terminó con código {returncode}"

        self._persist()


class DashboardApplication:
    def __init__(self, project_root: Path, token: str):
        self.project_root = project_root
        self.index_path = project_root / "web" / "index.html"
        self.token = token
        self.jobs = JobManager(project_root)
        self.server: ThreadingHTTPServer | None = None

    def _profiles_cache_path(self) -> Path:
        return Path(_cli().APP_DIR) / "dashboard-profiles.json"

    @staticmethod
    def _profile_payload(item: Any) -> dict[str, Any]:
        return {
            "username": item.username,
            "display_name": item.display_name,
            "profile_id": getattr(item, "profile_id", ""),
            "avatar_url": getattr(item, "avatar_url", ""),
            "status": item.status,
            "posts": item.posts,
            "photos": item.photos,
            "videos": item.videos,
            "archived": item.archived,
        }

    def _read_profiles_cache(self) -> tuple[list[dict[str, Any]], str] | None:
        try:
            cache = _cli().read_json(self._profiles_cache_path())
            timestamp = float(cache.get("updated_at", 0))
            profiles = cache.get("profiles")
            if not isinstance(profiles, list) or not isinstance(timestamp, (int, float)):
                return None
            return profiles, datetime.fromtimestamp(timestamp, timezone.utc).isoformat().replace("+00:00", "Z")
        except (OSError, TypeError, ValueError, AttributeError, _cli().UserError):
            return None

    def _write_profiles_cache(self, profiles: list[dict[str, Any]]) -> None:
        path = self._profiles_cache_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        _cli().secure_write_json(path, {"updated_at": time.time(), "profiles": profiles})

    def status(self) -> dict[str, Any]:
        cli = _cli()
        state = cli.get_state()
        download_dir = Path(state["download_dir"]).expanduser()
        try:
            usage = shutil.disk_usage(download_dir if download_dir.exists() else download_dir.parent)
            disk = {
                "total": usage.total,
                "used": usage.used,
                "free": usage.free,
                "percent": round(usage.used * 100 / usage.total) if usage.total else 0,
            }
        except OSError:
            disk = {"total": 0, "used": 0, "free": 0, "percent": 0}
        try:
            pending = cli.read_json(cli.DRIVE_QUEUE_PATH)
            drive_pending = len(pending) if isinstance(pending, list) else 0
        except cli.UserError:
            drive_pending = 0
        jobs = self.jobs.snapshot()
        try:
            engine_path = str(cli.ofscraper_binary())
            engine_available = bool(engine_path)
        except Exception:
            engine_path = ""
            engine_available = False
        return {
            "version": cli.APP_VERSION,
            "platform": os.getenv("OFDOWNLOADER_PLATFORM", "WINDOWS" if os.name == "nt" else "LINUX"),
            "connected": cli.credentials_ready(),
            "engine_available": engine_available,
            "engine_path": engine_path,
            "username": state.get("username", ""),
            "download_dir": str(download_dir),
            "drive_enabled": bool(state.get("drive_enabled")),
            "drive_upload_after_download": bool(state.get("drive_upload_after_download", True)),
            "drive_remote": state.get("drive_remote", "gdrive"),
            "drive_folder": state.get("drive_folder", "OFDownloader"),
            "drive_pending": drive_pending,
            "disk": disk,
            "jobs": jobs,
            "active_jobs": sum(item["status"] in {"running", "paused"} for item in jobs),
            "queued_jobs": sum(item["status"] == "queued" for item in jobs),
        }

    def import_auth(self, payload: dict[str, Any]) -> dict[str, Any]:
        cli = _cli()
        filename = str(payload.get("filename", "OFBackup-auth.json"))[:200]
        content = payload.get("content")
        if not isinstance(content, str):
            raise cli.UserError("No se recibió el contenido del archivo.")
        raw = content.encode("utf-8")
        if not raw or len(raw) > cli.MAX_AUTH_EXPORT_SIZE:
            raise cli.UserError("El archivo está vacío o supera 64 KB.")
        try:
            data = json.loads(content)
        except json.JSONDecodeError as exc:
            raise cli.UserError("Usa el archivo JSON generado por OF Downloader Exporter.") from exc
        values = cli.parse_auth_export(data)
        cli.save_credentials(values)
        # La cuenta puede haber cambiado: no reutilizar perfiles de la sesión anterior.
        try:
            self._profiles_cache_path().unlink(missing_ok=True)
        except OSError:
            pass
        return {
            "ok": True,
            "connected": True,
            "filename": filename,
            "fields": ["sess", "auth_id", "x-bc", "User-Agent"],
            "message": "Archivo válido. Los cuatro datos necesarios se guardaron localmente.",
        }

    def test_auth(self) -> dict[str, Any]:
        cli = _cli()
        output = io.StringIO()
        with redirect_stdout(output), redirect_stderr(output):
            code = cli.test_credentials(timeout=60)
        text = ANSI_RE.sub("", output.getvalue())
        if code == 0:
            message = "OnlyFans aceptó la sesión."
        elif code == cli.IMPORT_REQUEST_EXIT:
            message = "Primero carga OFBackup-auth.json."
        elif "RECHAZADA" in text or "VENCIDA" in text:
            message = "La cookie fue rechazada o venció."
        else:
            message = "No se pudo comprobar la cookie. Revisa el diagnóstico del programa."
        return {"ok": code == 0, "code": code, "message": message}

    def profiles(self, *, force_refresh: bool = False) -> dict[str, Any]:
        cli = _cli()
        log_path = str(Path(cli.get_state()["download_dir"]).expanduser() / cli.SUBSCRIPTIONS_LOG_NAME)
        cached = self._read_profiles_cache()
        if cached and not force_refresh:
            profiles, updated_at = cached
            try:
                age = time.time() - datetime.fromisoformat(updated_at.replace("Z", "+00:00")).timestamp()
            except ValueError:
                age = PROFILE_CACHE_TTL + 1
            if age <= PROFILE_CACHE_TTL:
                return {
                    "profiles": profiles,
                    "cached": True,
                    "stale": False,
                    "updated_at": updated_at,
                    "log_path": log_path,
                    "message": f"{len(profiles)} perfiles en caché",
                }
        output = io.StringIO()
        with redirect_stdout(output), redirect_stderr(output):
            try:
                profiles = cli.list_subscription_profiles(timeout=90)
            except Exception:
                if cached:
                    old_profiles, updated_at = cached
                    return {
                        "profiles": old_profiles,
                        "cached": True,
                        "stale": True,
                        "updated_at": updated_at,
                        "log_path": log_path,
                        "message": "No se pudo actualizar; mostrando la última lista guardada.",
                    }
                raise
        payload = [self._profile_payload(item) for item in profiles]
        self._write_profiles_cache(payload)
        return {
            "profiles": payload,
            "cached": False,
            "stale": False,
            "updated_at": _utc_now(),
            "log_path": log_path,
            "message": f"{len(profiles)} perfiles encontrados" if profiles else "No se encontraron perfiles.",
        }

    def open_download_folder(self) -> dict[str, Any]:
        cli = _cli()
        folder = Path(cli.get_state()["download_dir"]).expanduser()
        folder.mkdir(parents=True, exist_ok=True)
        try:
            if os.name == "nt":
                os.startfile(str(folder))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(folder)])
            else:
                subprocess.Popen(["xdg-open", str(folder)])
        except OSError as exc:
            raise RuntimeError(f"No se pudo abrir la carpeta: {exc}") from exc
        return {"ok": True, "path": str(folder)}

    def set_destination(self, payload: dict[str, Any]) -> dict[str, Any]:
        cli = _cli()
        value = str(payload.get("path", "")).strip()
        if not value:
            raise cli.UserError("Escribe una carpeta de destino.")
        folder = Path(value).expanduser().resolve()
        folder.mkdir(parents=True, exist_ok=True)
        state = cli.get_state()
        state["download_dir"] = str(folder)
        cli.save_state(state)
        return {"ok": True, "path": str(folder)}


class DashboardHandler(BaseHTTPRequestHandler):
    server_version = "OFDownloaderDashboard/1.0"

    @property
    def app(self) -> DashboardApplication:
        return self.server.app  # type: ignore[attr-defined]

    def log_message(self, _format: str, *_args: Any) -> None:
        return

    def _headers(self, content_type: str, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data: https:; style-src 'self' 'unsafe-inline'; "
            "script-src 'self' 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'",
        )
        self.end_headers()

    def _json(self, data: dict[str, Any], status: int = 200) -> None:
        encoded = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self._headers("application/json; charset=utf-8", status)
        self.wfile.write(encoded)

    def _read_json(self) -> dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise ValueError("Longitud inválida.") from exc
        if length <= 0 or length > MAX_REQUEST_SIZE:
            raise ValueError("La solicitud está vacía o es demasiado grande.")
        try:
            data = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("La solicitud no contiene JSON válido.") from exc
        if not isinstance(data, dict):
            raise ValueError("La solicitud debe ser un objeto JSON.")
        return data

    def _authorized(self) -> bool:
        host = self.headers.get("Host", "").split(":", 1)[0].strip("[]").lower()
        if host not in {"127.0.0.1", "localhost", "::1"}:
            return False
        return secrets.compare_digest(self.headers.get("X-OFD-Token", ""), self.app.token)

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        try:
            if path in {"/", "/index.html"}:
                html = repair_dashboard_encoding(self.app.index_path.read_text(encoding="utf-8"))
                html = html.replace("__OFD_TOKEN__", self.app.token)
                self._headers("text/html; charset=utf-8")
                self.wfile.write(html.encode("utf-8"))
                return
            if path.startswith("/api/") and not self._authorized():
                self._json({"error": "Solicitud no autorizada."}, 403)
                return
            if path == "/api/status":
                self._json(self.app.status())
                return
            if path == "/api/jobs":
                self._json({"jobs": self.app.jobs.snapshot()})
                return
            if path == "/api/profiles":
                query = parse_qs(urlparse(self.path).query)
                self._json(self.app.profiles(force_refresh=query.get("refresh") == ["1"]))
                return
            self._json({"error": "Ruta no encontrada."}, 404)
        except Exception as exc:  # La UI recibe un error breve, nunca secretos.
            self._json({"error": str(exc)}, 500)

    def do_POST(self) -> None:  # noqa: N802
        if not self._authorized():
            self._json({"error": "Solicitud no autorizada."}, 403)
            return
        path = urlparse(self.path).path
        try:
            if path == "/api/auth/import":
                self._json(self.app.import_auth(self._read_json()))
                return
            if path == "/api/auth/test":
                self._json(self.app.test_auth())
                return
            if path == "/api/auth/remove":
                cli = _cli()
                cli.AUTH_PATH.unlink(missing_ok=True)
                self._json({"ok": True, "connected": False, "message": "Credenciales eliminadas localmente."})
                return
            if path == "/api/jobs":
                payload = self._read_json()
                raw_options = payload.get("options")
                options = raw_options if isinstance(raw_options, dict) else {}
                self._json({"job": self.app.jobs.add(str(payload.get("target", "")), options)}, 201)
                return
            match = re.fullmatch(r"/api/jobs/([a-f0-9]+)/(?P<action>pause|resume|cancel)", path)
            if match:
                action = match.group("action")
                method = getattr(self.app.jobs, action)
                self._json({"job": method(match.group(1))})
                return
            if path == "/api/open-folder":
                self._json(self.app.open_download_folder())
                return
            if path == "/api/settings/destination":
                self._json(self.app.set_destination(self._read_json()))
                return
            if path == "/api/shutdown":
                if self.app.jobs.has_pending_work():
                    self._json({"error": "Espera o cancela los trabajos antes de cerrar el dashboard."}, 409)
                    return
                self._json({"ok": True, "message": "Dashboard cerrado."})
                Thread(target=self.server.shutdown, daemon=True).start()
                return
            self._json({"error": "Ruta no encontrada."}, 404)
        except KeyError:
            self._json({"error": "Trabajo no encontrado."}, 404)
        except (ValueError, RuntimeError, _cli().UserError) as exc:
            self._json({"error": str(exc)}, 400)
        except Exception as exc:
            self._json({"error": str(exc)}, 500)


def _available_server(app: DashboardApplication, requested_port: int) -> ThreadingHTTPServer:
    last_error: OSError | None = None
    for port in range(requested_port, requested_port + 10):
        try:
            server = ThreadingHTTPServer(("127.0.0.1", port), DashboardHandler)
            server.app = app  # type: ignore[attr-defined]
            app.server = server
            return server
        except OSError as exc:
            last_error = exc
    raise RuntimeError(f"No se encontró un puerto local disponible: {last_error}")


def run_dashboard(*, port: int = 8766, open_browser: bool = True) -> int:
    """Inicia el dashboard ligado exclusivamente a la máquina local."""
    project_root = Path(__file__).resolve().parents[1]
    index_path = project_root / "web" / "index.html"
    if not index_path.is_file():
        raise RuntimeError(f"Falta el dashboard web: {index_path}")
    token = secrets.token_urlsafe(32)
    app = DashboardApplication(project_root, token)
    server = _available_server(app, port)
    address, selected_port = server.server_address[:2]
    url = f"http://{address}:{selected_port}/"
    print(f"\n✓ Dashboard disponible en {url}")
    print("  Solo acepta conexiones desde este PC.")
    print("  Cierra el panel desde el navegador o pulsa Ctrl+C para volver al menú.")
    if open_browser:
        Thread(target=lambda: (time.sleep(0.35), webbrowser.open(url, new=2)), daemon=True).start()
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        print("\nDashboard detenido.")
    finally:
        app.jobs.cancel_all()
        server.server_close()
    return 0
