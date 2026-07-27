"""Servidor web local del dashboard de OF Downloader para Linux y Windows."""

from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from dataclasses import asdict, dataclass, field
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
from urllib.parse import urlparse
import webbrowser

from backend.process import PausableProcess


MAX_REQUEST_SIZE = 96 * 1024
ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
PERCENT_RE = re.compile(r"(?<!\d)(\d{1,3})%")


def _cli():
    import ofbackup_cli

    return ofbackup_cli


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


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
    status: str = "queued"
    progress: int | None = None
    message: str = "En cola"
    created_at: str = field(default_factory=_utc_now)
    started_at: str | None = None
    finished_at: str | None = None
    returncode: int | None = None
    process: subprocess.Popen[str] | None = field(default=None, repr=False)
    controller: PausableProcess | None = field(default=None, repr=False)
    cancel_requested: bool = field(default=False, repr=False)


class JobManager:
    """Cola secuencial para no ejecutar varias descargas a la vez."""

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self._jobs: list[DashboardJob] = []
        self._lock = Lock()
        self._queue: Queue[str] = Queue()
        Thread(target=self._worker, daemon=True, name="ofd-dashboard-jobs").start()

    def add(self, target: str) -> dict[str, Any]:
        cli = _cli()
        target = target.strip()
        if not target:
            raise cli.UserError("Escribe un usuario, enlace o ID.")
        username = cli.profile_username(target)
        if username:
            normalized, kind = username, "profile"
        else:
            normalized, kind = cli.normalize_url(target), "post"
        job = DashboardJob(id=secrets.token_hex(6), target=normalized, kind=kind)
        with self._lock:
            self._jobs.append(job)
            self._jobs = self._jobs[-50:]
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
        return _public_job(job)

    def cancel(self, job_id: str) -> dict[str, Any]:
        job = self._find(job_id)
        with self._lock:
            if job.status == "queued":
                job.cancel_requested = True
                job.status = "cancelled"
                job.message = "Cancelado antes de iniciar"
                job.finished_at = _utc_now()
                return _public_job(job)
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
        command = [sys.executable, str(cli_path), "descargar-web", job.target]
        env = os.environ.copy()
        env["OFDOWNLOADER_EXTERNAL_PAUSE"] = "1"
        env["PYTHONUNBUFFERED"] = "1"
        with self._lock:
            job.status = "running"
            job.message = "Preparando descarga"
            job.started_at = _utc_now()
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
            return
        with self._lock:
            job.process = process
            job.controller = PausableProcess(process.pid)
        if process.stdout is not None:
            for raw_line in process.stdout:
                line = ANSI_RE.sub("", raw_line).strip()
                if not line:
                    continue
                match = PERCENT_RE.search(line)
                with self._lock:
                    if match:
                        job.progress = max(0, min(100, int(match.group(1))))
                    job.message = line[-220:]
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
                if not job.message:
                    job.message = f"El proceso terminó con código {returncode}"


class DashboardApplication:
    def __init__(self, project_root: Path, token: str):
        self.project_root = project_root
        self.index_path = project_root / "web" / "index.html"
        self.token = token
        self.jobs = JobManager(project_root)
        self.server: ThreadingHTTPServer | None = None

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
        return {
            "version": cli.APP_VERSION,
            "platform": os.getenv("OFDOWNLOADER_PLATFORM", "WINDOWS" if os.name == "nt" else "LINUX"),
            "connected": cli.credentials_ready(),
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

    def profiles(self) -> dict[str, Any]:
        cli = _cli()
        output = io.StringIO()
        with redirect_stdout(output), redirect_stderr(output):
            profiles = cli.list_subscription_profiles(timeout=90)
        return {
            "profiles": [
                {
                    "username": item.username,
                    "display_name": item.display_name,
                    "status": item.status,
                    "posts": item.posts,
                    "photos": item.photos,
                    "videos": item.videos,
                    "archived": item.archived,
                }
                for item in profiles
            ],
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
            "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
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
                html = self.app.index_path.read_text(encoding="utf-8")
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
                self._json(self.app.profiles())
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
            if path == "/api/jobs":
                payload = self._read_json()
                self._json({"job": self.app.jobs.add(str(payload.get("target", "")))}, 201)
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
