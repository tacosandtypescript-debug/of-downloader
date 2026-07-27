# OF Downloader 2.17.0

## Dashboard web integrado

Esta versión incorpora el dashboard directamente al proyecto principal. En
Linux y Windows aparece la opción `[13] Abrir dashboard en el navegador`; en
Termux permanece oculto.

### Funciones conectadas

- Estado real de cuenta, destino, disco, Google Drive y trabajos.
- Importación por drag & drop de `OFBackup-auth.json`.
- Prueba de la sesión desde el navegador.
- Consulta real de perfiles suscritos.
- Cola secuencial para perfiles, enlaces e IDs.
- Pausa, reanudación y cancelación del proceso activo y sus procesos hijos.
- Apertura de la carpeta configurada.
- Botón para cerrar el servidor y volver al menú.

### Seguridad

- El servidor escucha exclusivamente en `127.0.0.1`.
- Cada ejecución genera un token temporal para las llamadas a la API.
- Las respuestas nunca contienen `sess`, `auth_id`, `x-bc` ni `User-Agent`.
- El archivo de acceso se limita a 64 KB y se valida con el mismo parser del CLI.
- El dashboard no se ofrece en Android/Termux y el frontend bloquea móviles y tablets.

### Uso

```bash
of dashboard
```

O abre `of` y selecciona la opción `13`.
