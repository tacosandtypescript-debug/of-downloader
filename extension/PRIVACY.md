# Política de privacidad de OF Downloader Exporter

OF Downloader Exporter procesa localmente cuatro datos de la sesión activa:
`sess`, `auth_id`, `x-bc` y `User-Agent`.

- No transmite datos a servidores propios ni de terceros.
- No incluye telemetría, publicidad ni analítica.
- No copia credenciales al portapapeles.
- No conserva credenciales en el almacenamiento de la extensión.
- Solo crea `OFBackup-auth.json` en la carpeta de descargas cuando el usuario
  pulsa expresamente el botón de exportación.

El usuario debe importar el archivo en OF Downloader y eliminarlo después. OF
Downloader intenta eliminarlo automáticamente cuando verifica que coincide con el
archivo seleccionado.
