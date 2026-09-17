"""Backend compartido de OF Downloader.

Módulos activos: constants, downloads, drive, models, process, profiles,
progress, queue, web_dashboard.

Fachadas de compatibilidad (delegan en el CLI o en models): auth, diagnostics,
errors, media, storage, updates.

La implementación de auth (cookies, receptor local, verificación de sesión)
vive en ofbackup_cli; backend.auth solo delega para evitar dos copias del
mismo código sensible.
"""
