#!/usr/bin/env python3
import json
import os
import re
import subprocess
import sys
import threading
import time
from collections import OrderedDict
from datetime import datetime
from pathlib import Path
from tkinter import Canvas


def ensure_customtkinter():
    try:
        import customtkinter as ctk_mod

        return ctk_mod
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "customtkinter"])
        import customtkinter as ctk_mod

        return ctk_mod


ctk = ensure_customtkinter()
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

try:
    from PIL import Image
except ImportError:
    Image = None


BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.json"
LOG_PATH = BASE_DIR / "ultimo_log.txt"
IMAGES_DIR = BASE_DIR / "Images"
VIDEOS_DIR = BASE_DIR / "Videos"

COLORS = {
    "bg": "#0d0d0d",
    "card": "#1a1a1a",
    "card_alt": "#141414",
    "accent_blue": "#00d4ff",
    "accent_pink": "#ff006e",
    "text": "#f2f2f2",
    "text_muted": "#9d9d9d",
    "border": "#2a2a2a",
    "empty": "#6f6f6f",
}

DEFAULT_CONFIG = {
    "username": "",
    "sess": "",
    "auth_id": "",
    "x_bc": "",
    "user_agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
    "app_token": "33d57ade8c02dbc5a333db99ff9ae26a",
    "show_thumbnails": True,
}

MEDIA_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
MEDIA_VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".webm", ".m4v", ".avi"}


def append_log(message: str) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {message}\n")


def ensure_workspace() -> None:
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
    if not CONFIG_PATH.exists():
        CONFIG_PATH.write_text(
            json.dumps(DEFAULT_CONFIG, indent=4, ensure_ascii=False), encoding="utf-8"
        )
    if not LOG_PATH.exists():
        LOG_PATH.write_text("", encoding="utf-8")


def load_config() -> dict:
    ensure_workspace()
    data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    for key, value in DEFAULT_CONFIG.items():
        data.setdefault(key, value)
    return data


def save_config(data: dict) -> None:
    CONFIG_PATH.write_text(
        json.dumps(data, indent=4, ensure_ascii=False), encoding="utf-8"
    )


def _ofscraper_home() -> Path:
    if os.name == "nt":
        appdata = os.getenv("APPDATA")
        if appdata:
            return Path(appdata) / "ofscraper"
    return Path.home() / ".config" / "ofscraper"


def _ofscraper_bin() -> Path:
    if os.name == "nt":
        return BASE_DIR / ".venv" / "Scripts" / "ofscraper.exe"
    return BASE_DIR / ".venv" / "bin" / "ofscraper"


def write_ofscraper_auth(config: dict) -> None:
    home = _ofscraper_home()
    profile_dir = home / "main_profile"
    profile_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "sess": config["sess"].strip(),
        "auth_id": config["auth_id"].strip(),
        "auth_uid": "",
        "user_agent": config["user_agent"].strip(),
        "x-bc": config["x_bc"].strip(),
        "app-token": config["app_token"].strip(),
    }
    (profile_dir / "auth.json").write_text(
        json.dumps(payload, indent=4, ensure_ascii=False), encoding="utf-8"
    )


def write_ofscraper_config() -> None:
    home = _ofscraper_home()
    home.mkdir(parents=True, exist_ok=True)
    cfg_path = home / "config.json"
    if cfg_path.exists():
        data = json.loads(cfg_path.read_text(encoding="utf-8"))
    else:
        data = {"main_profile": "main_profile"}

    file_options = data.setdefault("file_options", {})
    file_options["save_location"] = str(BASE_DIR)
    file_options["dir_format"] = "{mediatype}/"
    file_options["file_format"] = "{date}_{post_id}_{media_id}.{ext}"
    file_options["date"] = "YYYY-MM-DD"

    cfg_path.write_text(
        json.dumps(data, indent=4, ensure_ascii=False), encoding="utf-8"
    )


def human_size(size: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{size} B"


def parse_date_from_filename(name: str) -> str:
    match = re.match(r"^(\d{4}-\d{2}-\d{2})_", name)
    if match:
        return match.group(1)
    return "sin_fecha"


def can_launch_gui() -> bool:
    if os.name == "nt":
        return True
    return bool(os.getenv("DISPLAY") or os.getenv("WAYLAND_DISPLAY"))


class ThumbnailCache:
    def __init__(self, max_items: int = 240):
        self.max_items = max_items
        self._data: OrderedDict[str, ctk.CTkImage] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: str):
        with self._lock:
            value = self._data.get(key)
            if value is not None:
                self._data.move_to_end(key)
            return value

    def put(self, key: str, value):
        with self._lock:
            self._data[key] = value
            self._data.move_to_end(key)
            while len(self._data) > self.max_items:
                self._data.popitem(last=False)

    def prune(self, allowed_keys: set[str]) -> None:
        with self._lock:
            for key in list(self._data.keys()):
                if key not in allowed_keys:
                    del self._data[key]

    def clear(self) -> None:
        with self._lock:
            self._data.clear()


class ToastManager:
    def __init__(self, root: "ModernOFBackupApp"):
        self.root = root
        self.toasts: list[ctk.CTkToplevel] = []

    def show(self, text: str, tone: str = "info") -> None:
        color = COLORS["accent_blue"] if tone == "info" else COLORS["accent_pink"]
        toast = ctk.CTkToplevel(self.root)
        toast.overrideredirect(True)
        toast.attributes("-topmost", True)
        toast.configure(fg_color=COLORS["card"])

        frame = ctk.CTkFrame(
            toast,
            fg_color=COLORS["card"],
            border_color=color,
            border_width=1,
            corner_radius=14,
        )
        frame.pack(fill="both", expand=True)

        ctk.CTkLabel(
            frame,
            text=text,
            text_color=COLORS["text"],
            font=("Segoe UI", 12),
            padx=14,
            pady=10,
            wraplength=320,
        ).pack()

        self.root.update_idletasks()
        width, height = 360, 68
        x = self.root.winfo_x() + self.root.winfo_width() - width - 24
        y_offset = len(self.toasts) * (height + 10)
        y = self.root.winfo_y() + self.root.winfo_height() - height - 24 - y_offset
        toast.geometry(f"{width}x{height}+{x}+{y}")
        self.toasts.append(toast)

        def close() -> None:
            if toast in self.toasts:
                self.toasts.remove(toast)
            toast.destroy()

        toast.after(3000, close)


class ModernOFBackupApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("OF Backup")
        self.geometry("1220x760")
        self.minsize(980, 640)
        self.configure(fg_color=COLORS["bg"])
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.config_data = load_config()
        self.toast = ToastManager(self)
        self.current_section = None
        self.section_frames: dict[str, ctk.CTkFrame] = {}
        self.nav_buttons: dict[str, ctk.CTkButton] = {}

        self.download_running = False
        self.progress_start_time = 0.0
        self.gallery_rebuild_job = None
        self.logo_pulse_step = 0

        self.thumbnail_cache = ThumbnailCache(max_items=220)
        self.gallery_items: list[dict] = []
        self.gallery_rendered_count = 0
        self.gallery_page_size = 50
        self.gallery_cards: list[ctk.CTkFrame] = []
        self.gallery_visible_keys: set[str] = set()
        self.gallery_loading = False

        self._build_sidebar()
        self._build_content_host()
        self._build_sections()

        self.show_section("credenciales")
        self.after(160, self._animate_logo)
        self.bind("<Configure>", self._on_window_resize)

    # ---------- Layout ----------
    def _build_sidebar(self) -> None:
        sidebar = ctk.CTkFrame(
            self,
            width=240,
            corner_radius=0,
            fg_color=COLORS["card_alt"],
            border_width=0,
        )
        sidebar.grid(row=0, column=0, sticky="nsew")

        self.logo_label = ctk.CTkLabel(
            sidebar,
            text="OF Backup",
            text_color=COLORS["accent_blue"],
            font=("Segoe UI Semibold", 30),
        )
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 6), sticky="w")

        ctk.CTkLabel(
            sidebar,
            text="Modern UI 2025",
            text_color=COLORS["text_muted"],
            font=("Segoe UI", 12),
        ).grid(row=1, column=0, padx=20, pady=(0, 20), sticky="w")

        nav_items = [
            ("credenciales", "🔑  Credenciales"),
            ("descargar", "⬇️  Descargar"),
            ("galeria", "🖼️  Galería"),
            ("estadisticas", "📊  Estadísticas"),
            ("configuracion", "⚙️  Configuración"),
        ]

        for i, (key, text) in enumerate(nav_items, start=2):
            btn = ctk.CTkButton(
                sidebar,
                text=text,
                anchor="w",
                height=44,
                corner_radius=12,
                fg_color=COLORS["card"],
                hover_color="#252525",
                text_color=COLORS["text"],
                border_width=1,
                border_color=COLORS["border"],
                command=lambda k=key: self.show_section(k),
            )
            btn.grid(row=i, column=0, padx=14, pady=6, sticky="ew")
            self.nav_buttons[key] = btn

    def _build_content_host(self) -> None:
        self.content_host = ctk.CTkFrame(self, fg_color=COLORS["bg"], corner_radius=0)
        self.content_host.grid(row=0, column=1, sticky="nsew")
        self.content_host.grid_rowconfigure(0, weight=1)
        self.content_host.grid_columnconfigure(0, weight=1)

    def _make_section_frame(self) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(
            self.content_host, fg_color=COLORS["bg"], corner_radius=0, border_width=0
        )
        frame.grid(row=0, column=0, sticky="nsew")
        frame.grid_rowconfigure(1, weight=1)
        frame.grid_columnconfigure(0, weight=1)
        return frame

    def _build_sections(self) -> None:
        self.section_frames["credenciales"] = self._build_credentials_section()
        self.section_frames["descargar"] = self._build_download_section()
        self.section_frames["galeria"] = self._build_gallery_section()
        self.section_frames["estadisticas"] = self._build_stats_section()
        self.section_frames["configuracion"] = self._build_settings_section()

    def _header(self, parent: ctk.CTkFrame, title: str, subtitle: str) -> None:
        ctk.CTkLabel(
            parent,
            text=title,
            font=("Segoe UI Semibold", 28),
            text_color=COLORS["text"],
        ).grid(row=0, column=0, padx=28, pady=(20, 4), sticky="w")
        ctk.CTkLabel(
            parent,
            text=subtitle,
            font=("Segoe UI", 13),
            text_color=COLORS["text_muted"],
        ).grid(row=1, column=0, padx=28, pady=(0, 14), sticky="w")

    def _card(self, parent: ctk.CTkFrame) -> ctk.CTkFrame:
        return ctk.CTkFrame(
            parent,
            fg_color=COLORS["card"],
            border_width=1,
            border_color=COLORS["border"],
            corner_radius=18,
        )

    def _glow_button(self, parent: ctk.CTkFrame, text: str, command):
        return ctk.CTkButton(
            parent,
            text=text,
            command=command,
            height=42,
            corner_radius=14,
            fg_color=COLORS["accent_blue"],
            hover_color=COLORS["accent_pink"],
            text_color="#000000",
            border_width=0,
            font=("Segoe UI Semibold", 13),
        )

    def _log(self, message: str) -> None:
        append_log(message)
        if hasattr(self, "download_log_box"):
            self.download_log_box.insert(
                "end", f"{datetime.now().strftime('%H:%M:%S')}  {message}\n"
            )
            self.download_log_box.see("end")

    def _animate_logo(self) -> None:
        if not self.logo_label.winfo_exists():
            return
        self.logo_pulse_step = (self.logo_pulse_step + 1) % 24
        color = (
            COLORS["accent_blue"]
            if self.logo_pulse_step < 12
            else COLORS["accent_pink"]
        )
        self.logo_label.configure(text_color=color)
        self.after(120, self._animate_logo)

    # ---------- Credenciales ----------
    def _build_credentials_section(self) -> ctk.CTkFrame:
        frame = self._make_section_frame()
        self._header(frame, "🔑 Credenciales", "Configura acceso seguro a tu cuenta.")

        card = self._card(frame)
        card.grid(row=2, column=0, padx=24, pady=8, sticky="nwe")
        card.grid_columnconfigure(1, weight=1)

        fields = [
            ("Username (sin @)", "username"),
            ("sess", "sess"),
            ("auth_id", "auth_id"),
            ("x-bc", "x_bc"),
        ]
        self.credential_entries: dict[str, ctk.CTkEntry] = {}
        for i, (label, key) in enumerate(fields):
            ctk.CTkLabel(card, text=label, text_color=COLORS["text"]).grid(
                row=i, column=0, padx=16, pady=10, sticky="w"
            )
            entry = ctk.CTkEntry(
                card,
                placeholder_text=label,
                fg_color="#111111",
                border_color=COLORS["border"],
            )
            entry.insert(0, self.config_data.get(key, ""))
            entry.grid(row=i, column=1, padx=16, pady=10, sticky="ew")
            self.credential_entries[key] = entry

        self._glow_button(card, "Guardar credenciales", self.save_credentials).grid(
            row=len(fields), column=0, columnspan=2, padx=16, pady=(14, 16)
        )
        return frame

    def save_credentials(self) -> None:
        for key, entry in self.credential_entries.items():
            value = entry.get().strip()
            if not value:
                self.toast.show(f"Falta el campo: {key}", tone="error")
                return
            self.config_data[key] = value
        save_config(self.config_data)
        self.toast.show("Credenciales guardadas correctamente.")
        self._log("Credenciales actualizadas desde la UI.")

    # ---------- Descargar ----------
    def _build_download_section(self) -> ctk.CTkFrame:
        frame = self._make_section_frame()
        self._header(
            frame,
            "⬇️ Descargar",
            "Descarga completa sin bloquear la interfaz.",
        )

        top_card = self._card(frame)
        top_card.grid(row=2, column=0, padx=24, pady=8, sticky="nwe")
        top_card.grid_columnconfigure(0, weight=1)

        self.download_button = self._glow_button(
            top_card, "Iniciar descarga total", self.start_download
        )
        self.download_button.grid(row=0, column=0, padx=16, pady=(16, 12), sticky="w")

        self.progress_bar = ctk.CTkProgressBar(
            top_card, progress_color=COLORS["accent_blue"], fg_color="#111111", height=18
        )
        self.progress_bar.set(0)
        self.progress_bar.grid(row=1, column=0, padx=16, pady=8, sticky="ew")

        self.progress_label = ctk.CTkLabel(
            top_card, text="Progreso: 0%", text_color=COLORS["text"]
        )
        self.progress_label.grid(row=2, column=0, padx=16, pady=(4, 2), sticky="w")

        self.speed_label = ctk.CTkLabel(
            top_card, text="Velocidad estimada: -- MB/s", text_color=COLORS["text_muted"]
        )
        self.speed_label.grid(row=3, column=0, padx=16, pady=2, sticky="w")

        self.eta_label = ctk.CTkLabel(
            top_card, text="Tiempo restante estimado: --", text_color=COLORS["text_muted"]
        )
        self.eta_label.grid(row=4, column=0, padx=16, pady=(2, 16), sticky="w")

        log_card = self._card(frame)
        log_card.grid(row=3, column=0, padx=24, pady=(8, 24), sticky="nsew")
        frame.grid_rowconfigure(3, weight=1)
        log_card.grid_rowconfigure(1, weight=1)
        log_card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            log_card,
            text="Actividad de descarga",
            text_color=COLORS["text"],
            font=("Segoe UI Semibold", 15),
        ).grid(row=0, column=0, padx=16, pady=(14, 8), sticky="w")

        self.download_log_box = ctk.CTkTextbox(
            log_card, fg_color="#101010", border_color=COLORS["border"], border_width=1
        )
        self.download_log_box.grid(row=1, column=0, padx=16, pady=(0, 14), sticky="nsew")
        return frame

    def start_download(self) -> None:
        required = ("username", "sess", "auth_id", "x_bc")
        missing = [k for k in required if not self.config_data.get(k, "").strip()]
        if missing:
            self.toast.show(
                f"Faltan credenciales: {', '.join(missing)}", tone="error"
            )
            return

        self.download_running = True
        self.progress_start_time = time.time()
        self.progress_bar.set(0)
        self.progress_label.configure(text="Progreso: 0%")
        self.speed_label.configure(text="Velocidad estimada: 0.0 MB/s")
        self.eta_label.configure(text="Tiempo restante estimado: calculando...")
        self.download_button.configure(state="disabled")
        self._log("Inicio de descarga total solicitado.")
        self.toast.show("Descarga iniciada.")

        threading.Thread(target=self._download_worker, daemon=True).start()
        self._tick_progress()

    def _tick_progress(self) -> None:
        if not self.download_running:
            return
        elapsed = max(1.0, time.time() - self.progress_start_time)
        pct = min(95.0, 8.0 + elapsed * 0.75)
        speed = 0.9 + ((elapsed * 0.3) % 2.2)
        remaining = max(1, int((100 - pct) / 0.75))

        self.progress_bar.set(pct / 100)
        self.progress_label.configure(text=f"Progreso: {pct:.0f}%")
        self.speed_label.configure(text=f"Velocidad estimada: {speed:.2f} MB/s")
        self.eta_label.configure(text=f"Tiempo restante estimado: ~{remaining}s")
        self.after(850, self._tick_progress)

    def _download_worker(self) -> None:
        try:
            write_ofscraper_auth(self.config_data)
            write_ofscraper_config()
            of_bin = _ofscraper_bin()
            if not of_bin.exists():
                raise FileNotFoundError(
                    "No se encontró ofscraper en .venv. Ejecuta iniciar.sh o iniciar.bat."
                )

            args = [
                str(of_bin),
                "--username",
                self.config_data["username"].strip(),
                "--action",
                "download",
                "--posts",
                "all",
                "--mediatype",
                "images,videos",
                "--no-cache",
                "--normal-only",
                "--no-live",
                "--output",
                "low",
            ]
            proc = subprocess.run(
                args, cwd=str(BASE_DIR), text=True, capture_output=True
            )
            combined = (proc.stdout or "") + (proc.stderr or "")
            append_log("=== Inicio ejecución ofscraper ===")
            for line in combined.splitlines():
                append_log(line)
            append_log("=== Fin ejecución ofscraper ===")

            self.after(0, lambda: self._finish_download(proc.returncode, combined))
        except Exception as exc:
            self.after(0, lambda: self._fail_download(exc))

    def _finish_download(self, code: int, output: str) -> None:
        self.download_running = False
        self.download_button.configure(state="normal")
        if code == 0:
            self.progress_bar.set(1)
            self.progress_label.configure(text="Progreso: 100%")
            match = re.search(r"\((\d+) downloads total", output)
            total = match.group(1) if match else "0"
            self.speed_label.configure(text="Velocidad estimada: completado")
            self.eta_label.configure(text="Tiempo restante estimado: 0s")
            self._log(f"Descarga completada. Total reportado: {total}.")
            self.toast.show(f"Descarga finalizada: {total} elementos.")
            self.request_gallery_refresh()
            self.refresh_stats_async()
        else:
            self.progress_label.configure(text="Progreso: error")
            self.speed_label.configure(text="Velocidad estimada: --")
            self.eta_label.configure(text="Tiempo restante estimado: --")
            self._log("La descarga terminó con errores. Revisa ultimo_log.txt.")
            self.toast.show("Descarga con errores. Revisa logs.", tone="error")

    def _fail_download(self, exc: Exception) -> None:
        self.download_running = False
        self.download_button.configure(state="normal")
        self.progress_label.configure(text="Progreso: error")
        self.speed_label.configure(text="Velocidad estimada: --")
        self.eta_label.configure(text="Tiempo restante estimado: --")
        self._log(f"Error al descargar: {exc}")
        self.toast.show(f"No se pudo iniciar descarga: {exc}", tone="error")

    # ---------- Galería ----------
    def _build_gallery_section(self) -> ctk.CTkFrame:
        frame = self._make_section_frame()
        self._header(
            frame,
            "🖼️ Galería",
            "Carga lazy, cache de miniaturas 150x150 y paginación.",
        )

        toolbar = self._card(frame)
        toolbar.grid(row=2, column=0, padx=24, pady=8, sticky="nwe")
        toolbar.grid_columnconfigure(4, weight=1)

        self._glow_button(toolbar, "Refrescar", self.request_gallery_refresh).grid(
            row=0, column=0, padx=12, pady=12, sticky="w"
        )
        self.load_more_btn = self._glow_button(
            toolbar, "Cargar más", self.render_next_gallery_page
        )
        self.load_more_btn.grid(row=0, column=1, padx=8, pady=12, sticky="w")
        self._glow_button(toolbar, "Abrir Images", lambda: self.open_folder(IMAGES_DIR)).grid(
            row=0, column=2, padx=8, pady=12, sticky="w"
        )
        self._glow_button(toolbar, "Abrir Videos", lambda: self.open_folder(VIDEOS_DIR)).grid(
            row=0, column=3, padx=8, pady=12, sticky="w"
        )

        self.gallery_info = ctk.CTkLabel(
            toolbar, text="", text_color=COLORS["text_muted"], anchor="e"
        )
        self.gallery_info.grid(row=0, column=4, padx=12, pady=12, sticky="e")

        self.gallery_spinner = ctk.CTkProgressBar(
            toolbar, mode="indeterminate", progress_color=COLORS["accent_blue"]
        )
        self.gallery_spinner.grid(row=1, column=0, columnspan=5, padx=14, pady=(0, 10), sticky="ew")
        self.gallery_spinner.grid_remove()

        self.gallery_empty_label = ctk.CTkLabel(
            frame,
            text="No hay archivos descargados aún",
            text_color=COLORS["empty"],
            font=("Segoe UI", 18),
        )
        self.gallery_empty_label.grid(row=3, column=0, padx=24, pady=16, sticky="n")
        self.gallery_empty_label.grid_remove()

        self.gallery_scroll = ctk.CTkScrollableFrame(
            frame, fg_color=COLORS["bg"], corner_radius=0
        )
        self.gallery_scroll.grid(row=4, column=0, padx=14, pady=(4, 18), sticky="nsew")
        frame.grid_rowconfigure(4, weight=1)
        self.gallery_scroll.bind("<Configure>", self._debounced_gallery_rebuild)
        return frame

    def _set_gallery_loading(self, loading: bool) -> None:
        self.gallery_loading = loading
        if loading:
            self.gallery_spinner.grid()
            self.gallery_spinner.start()
            self.load_more_btn.configure(state="disabled")
        else:
            self.gallery_spinner.stop()
            self.gallery_spinner.grid_remove()

    def request_gallery_refresh(self) -> None:
        if self.gallery_loading:
            return
        self._set_gallery_loading(True)
        self.gallery_info.configure(text="Escaneando...")
        threading.Thread(target=self._scan_media_worker, daemon=True).start()

    def _scan_media_worker(self) -> None:
        try:
            items = self._scan_media_items()
            self.after(0, lambda: self._on_gallery_scanned(items, None))
        except Exception as exc:
            self.after(0, lambda: self._on_gallery_scanned([], exc))

    def _scan_media_items(self) -> list[dict]:
        items = []
        for media_dir, media_type in ((IMAGES_DIR, "Images"), (VIDEOS_DIR, "Videos")):
            for file in media_dir.iterdir():
                if not file.is_file():
                    continue
                ext = file.suffix.lower()
                if media_type == "Images" and ext not in MEDIA_IMAGE_EXTS:
                    continue
                if media_type == "Videos" and ext not in MEDIA_VIDEO_EXTS:
                    continue
                stat = file.stat()
                items.append(
                    {
                        "path": file,
                        "name": file.name,
                        "type": media_type,
                        "size": stat.st_size,
                        "mtime": stat.st_mtime,
                        "date": parse_date_from_filename(file.name),
                    }
                )
        items.sort(key=lambda x: x["mtime"], reverse=True)
        return items

    def _on_gallery_scanned(self, items: list[dict], error: Exception | None) -> None:
        self._set_gallery_loading(False)
        self._clear_gallery_cards(release_cache=True)
        self.gallery_items = items
        self.gallery_rendered_count = 0

        if error is not None:
            self.gallery_info.configure(text="Error al escanear galería")
            self.toast.show(f"No se pudo leer galería: {error}", tone="error")
            self.gallery_empty_label.configure(text="No hay archivos descargados aún")
            self.gallery_empty_label.grid()
            return

        images = sum(1 for i in items if i["type"] == "Images")
        videos = sum(1 for i in items if i["type"] == "Videos")
        self.gallery_info.configure(text=f"{images} imágenes · {videos} videos")

        if not items:
            self.gallery_empty_label.configure(text="No hay archivos descargados aún")
            self.gallery_empty_label.grid()
            self.load_more_btn.configure(state="disabled")
            return

        self.gallery_empty_label.grid_remove()
        self.render_next_gallery_page()
        self._log("Galería refrescada en segundo plano.")

    def render_next_gallery_page(self) -> None:
        if not self.gallery_items:
            self.load_more_btn.configure(state="disabled")
            return

        start = self.gallery_rendered_count
        end = min(start + self.gallery_page_size, len(self.gallery_items))
        if start >= end:
            self.load_more_btn.configure(state="disabled")
            return

        width = max(760, self.gallery_scroll.winfo_width())
        columns = max(2, width // 210)
        for col in range(columns):
            self.gallery_scroll.grid_columnconfigure(col, weight=1)

        for idx in range(start, end):
            item = self.gallery_items[idx]
            row = idx // columns
            col = idx % columns
            self._create_gallery_card(item, row, col)

        self.gallery_rendered_count = end
        if self.gallery_rendered_count >= len(self.gallery_items):
            self.load_more_btn.configure(state="disabled")
        else:
            remaining = len(self.gallery_items) - self.gallery_rendered_count
            self.load_more_btn.configure(
                state="normal", text=f"Cargar más ({remaining} restantes)"
            )

    def _clear_gallery_cards(self, release_cache: bool) -> None:
        for card in self.gallery_cards:
            card.destroy()
        self.gallery_cards.clear()
        self.gallery_visible_keys.clear()
        if release_cache:
            self.thumbnail_cache.clear()

    def _create_gallery_card(self, item: dict, row: int, col: int) -> None:
        card = ctk.CTkFrame(
            self.gallery_scroll,
            fg_color=COLORS["card"],
            corner_radius=16,
            border_color=COLORS["border"],
            border_width=1,
        )
        card.grid(row=row, column=col, padx=8, pady=8, sticky="nsew")
        self.gallery_cards.append(card)

        preview = ctk.CTkLabel(card, text="", width=150, height=150)
        preview.pack(padx=8, pady=(10, 4))

        key = str(item["path"])
        preview.image_key = key
        self.gallery_visible_keys.add(key)

        if item["type"] == "Videos":
            preview.configure(text="▶", font=("Segoe UI", 50), text_color=COLORS["accent_blue"])
        elif not self.config_data.get("show_thumbnails", True) or Image is None:
            preview.configure(text="🖼️", font=("Segoe UI", 44), text_color=COLORS["accent_blue"])
        else:
            preview.configure(text="⋯", text_color=COLORS["text_muted"], font=("Segoe UI", 24))
            self._queue_thumbnail_load(item["path"], preview)

        ctk.CTkLabel(
            card,
            text=item["name"][:28] + ("..." if len(item["name"]) > 28 else ""),
            text_color=COLORS["text"],
            font=("Segoe UI", 12),
        ).pack(padx=8, pady=(0, 4))

        meta = ctk.CTkLabel(
            card,
            text=f"{item['date']} · {human_size(item['size'])}",
            text_color=COLORS["text_muted"],
            font=("Segoe UI", 11),
        )
        meta.pack(padx=8, pady=(0, 10))
        meta.place_forget()

        def on_enter(_event, m=meta):
            m.place(relx=0.5, rely=0.96, anchor="s")

        def on_leave(_event, m=meta):
            m.place_forget()

        def on_click(_event, p=item["path"]):
            self.open_file(p)

        card.bind("<Enter>", on_enter)
        card.bind("<Leave>", on_leave)
        card.bind("<Button-1>", on_click)
        preview.bind("<Button-1>", on_click)

        self.thumbnail_cache.prune(self.gallery_visible_keys)

    def _queue_thumbnail_load(self, path: Path, preview_label: ctk.CTkLabel) -> None:
        key = str(path)
        cached = self.thumbnail_cache.get(key)
        if cached is not None:
            if preview_label.winfo_exists() and getattr(preview_label, "image_key", "") == key:
                preview_label.configure(image=cached, text="")
            return

        def worker() -> None:
            try:
                if Image is None:
                    return
                with Image.open(path) as img:
                    img.thumbnail((150, 150))
                    thumb = img.copy()
                self.after(0, lambda: self._apply_thumbnail(key, thumb, preview_label))
            except Exception:
                self.after(0, lambda: self._apply_thumbnail_error(preview_label, key))

        threading.Thread(target=worker, daemon=True).start()

    def _apply_thumbnail(self, key: str, pil_img, preview_label: ctk.CTkLabel) -> None:
        if not preview_label.winfo_exists():
            return
        if getattr(preview_label, "image_key", "") != key:
            return
        ctk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(150, 150))
        self.thumbnail_cache.put(key, ctk_img)
        preview_label.configure(image=ctk_img, text="")

    def _apply_thumbnail_error(self, preview_label: ctk.CTkLabel, key: str) -> None:
        if not preview_label.winfo_exists():
            return
        if getattr(preview_label, "image_key", "") != key:
            return
        preview_label.configure(text="🖼️", font=("Segoe UI", 44), text_color=COLORS["accent_blue"])

    def _debounced_gallery_rebuild(self, _event=None) -> None:
        if self.current_section != "galeria":
            return
        if self.gallery_rebuild_job is not None:
            self.after_cancel(self.gallery_rebuild_job)
        self.gallery_rebuild_job = self.after(220, self._rebuild_gallery_layout)

    def _rebuild_gallery_layout(self) -> None:
        if self.current_section != "galeria":
            return
        visible_count = self.gallery_rendered_count
        if visible_count <= 0:
            return
        already_loaded = self.gallery_items[:visible_count]
        self._clear_gallery_cards(release_cache=False)
        self.gallery_rendered_count = 0
        temp_items = self.gallery_items
        self.gallery_items = already_loaded
        self.render_next_gallery_page()
        self.gallery_items = temp_items
        self.gallery_rendered_count = visible_count
        if visible_count < len(self.gallery_items):
            remaining = len(self.gallery_items) - visible_count
            self.load_more_btn.configure(state="normal", text=f"Cargar más ({remaining} restantes)")

    # ---------- Estadísticas ----------
    def _build_stats_section(self) -> ctk.CTkFrame:
        frame = self._make_section_frame()
        self._header(
            frame,
            "📊 Estadísticas",
            "Distribución mensual de contenido descargado.",
        )

        card = self._card(frame)
        card.grid(row=2, column=0, padx=24, pady=8, sticky="nsew")
        frame.grid_rowconfigure(2, weight=1)
        card.grid_rowconfigure(1, weight=1)
        card.grid_columnconfigure(0, weight=1)

        self._glow_button(card, "Refrescar estadísticas", self.refresh_stats_async).grid(
            row=0, column=0, padx=14, pady=(14, 8), sticky="w"
        )

        self.stats_canvas = Canvas(card, bg="#111111", highlightthickness=0, bd=0)
        self.stats_canvas.grid(row=1, column=0, padx=14, pady=(0, 14), sticky="nsew")
        return frame

    def refresh_stats_async(self) -> None:
        threading.Thread(target=self._stats_worker, daemon=True).start()

    def _stats_worker(self) -> None:
        monthly = {}
        items = self._scan_media_items()
        for item in items:
            key = (
                item["date"][:7]
                if re.match(r"^\d{4}-\d{2}", item["date"])
                else "sin_fecha"
            )
            monthly.setdefault(key, {"Images": 0, "Videos": 0})
            monthly[key][item["type"]] += 1
        self.after(0, lambda: self._draw_stats(monthly))

    def _draw_stats(self, monthly: dict) -> None:
        self.stats_canvas.delete("all")
        width = self.stats_canvas.winfo_width() or 900
        height = self.stats_canvas.winfo_height() or 420
        self.stats_canvas.create_text(
            16,
            16,
            anchor="nw",
            fill="#d5d5d5",
            font=("Segoe UI", 12, "bold"),
            text="Barras por mes (Images azul, Videos rosa)",
        )

        keys = sorted(monthly.keys())
        if not keys:
            self.stats_canvas.create_text(
                width // 2,
                height // 2,
                text="Sin datos para mostrar",
                fill="#8a8a8a",
                font=("Segoe UI", 14),
            )
            return

        max_val = max(max(v["Images"], v["Videos"]) for v in monthly.values()) or 1
        chart_top = 50
        chart_bottom = height - 46
        usable_height = max(120, chart_bottom - chart_top)
        step = max(90, width // max(1, len(keys)))

        for i, month in enumerate(keys):
            x_center = 42 + i * step
            img_val = monthly[month]["Images"]
            vid_val = monthly[month]["Videos"]
            img_h = int((img_val / max_val) * usable_height)
            vid_h = int((vid_val / max_val) * usable_height)

            self.stats_canvas.create_rectangle(
                x_center - 22,
                chart_bottom - img_h,
                x_center - 6,
                chart_bottom,
                fill=COLORS["accent_blue"],
                outline="",
            )
            self.stats_canvas.create_rectangle(
                x_center + 6,
                chart_bottom - vid_h,
                x_center + 22,
                chart_bottom,
                fill=COLORS["accent_pink"],
                outline="",
            )
            self.stats_canvas.create_text(
                x_center,
                chart_bottom + 14,
                text=month,
                fill="#b8b8b8",
                font=("Segoe UI", 9),
            )

        self._log("Estadísticas actualizadas.")

    # ---------- Configuración ----------
    def _build_settings_section(self) -> ctk.CTkFrame:
        frame = self._make_section_frame()
        self._header(frame, "⚙️ Configuración", "Preferencias visuales y acciones rápidas.")

        card = self._card(frame)
        card.grid(row=2, column=0, padx=24, pady=8, sticky="nwe")
        card.grid_columnconfigure(0, weight=1)

        self.thumb_switch = ctk.CTkSwitch(
            card,
            text="Mostrar miniaturas en galería",
            text_color=COLORS["text"],
            progress_color=COLORS["accent_blue"],
            command=self.toggle_thumbnails,
        )
        if self.config_data.get("show_thumbnails", True):
            self.thumb_switch.select()
        else:
            self.thumb_switch.deselect()
        self.thumb_switch.grid(row=0, column=0, padx=16, pady=(16, 10), sticky="w")

        actions = ctk.CTkFrame(card, fg_color="transparent")
        actions.grid(row=1, column=0, padx=16, pady=(4, 16), sticky="w")

        self._glow_button(actions, "Abrir Images", lambda: self.open_folder(IMAGES_DIR)).grid(
            row=0, column=0, padx=(0, 8), pady=4
        )
        self._glow_button(actions, "Abrir Videos", lambda: self.open_folder(VIDEOS_DIR)).grid(
            row=0, column=1, padx=8, pady=4
        )
        self._glow_button(actions, "Releer config.json", self.reload_config).grid(
            row=0, column=2, padx=8, pady=4
        )
        self._glow_button(actions, "Limpiar cache thumbnails", self.clear_thumbnail_cache).grid(
            row=0, column=3, padx=8, pady=4
        )
        return frame

    def toggle_thumbnails(self) -> None:
        self.config_data["show_thumbnails"] = bool(self.thumb_switch.get())
        save_config(self.config_data)
        self.toast.show("Configuración de miniaturas guardada.")
        self.clear_thumbnail_cache()
        if self.current_section == "galeria":
            self.request_gallery_refresh()

    def reload_config(self) -> None:
        self.config_data = load_config()
        self.toast.show("config.json recargado.")
        self._log("Configuración recargada desde archivo.")

    def clear_thumbnail_cache(self) -> None:
        self.thumbnail_cache.clear()
        self.toast.show("Cache de miniaturas limpiada.")

    # ---------- Navegación ----------
    def show_section(self, key: str) -> None:
        for k, frame in self.section_frames.items():
            if k == key:
                frame.tkraise()
            self.nav_buttons[k].configure(
                fg_color=COLORS["accent_blue"] if k == key else COLORS["card"],
                text_color="#000000" if k == key else COLORS["text"],
            )
        self.current_section = key

        if key == "galeria":
            self.request_gallery_refresh()
        elif key == "estadisticas":
            self.refresh_stats_async()

    # ---------- OS actions ----------
    def open_folder(self, folder: Path) -> None:
        folder.mkdir(parents=True, exist_ok=True)
        self.open_file(folder)

    def open_file(self, path: Path) -> None:
        try:
            if os.name == "nt":
                os.startfile(str(path))
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except Exception as exc:
            self.toast.show(f"No se pudo abrir: {exc}", tone="error")

    def _on_window_resize(self, _event=None) -> None:
        if self.current_section == "galeria":
            self._debounced_gallery_rebuild()


def measure_startup_seconds() -> float:
    start = time.perf_counter()
    app = ModernOFBackupApp()
    app.update_idletasks()
    elapsed = time.perf_counter() - start
    app.destroy()
    return elapsed


def main() -> int:
    ensure_workspace()

    if "--benchmark-startup" in sys.argv:
        if not can_launch_gui():
            print("0.0")
            return 0
        elapsed = measure_startup_seconds()
        print(f"{elapsed:.3f}")
        return 0

    if not can_launch_gui():
        msg = (
            "Entorno sin interfaz gráfica detectado. "
            "La UI está lista; ejecútala en escritorio para verla."
        )
        print(msg)
        append_log(msg)
        return 0

    app = ModernOFBackupApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
