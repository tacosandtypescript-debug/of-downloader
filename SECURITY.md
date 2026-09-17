# Política de seguridad

## Qué considerar sensible

OF Downloader maneja credenciales de sesión de OnlyFans (`sess`, `auth_id`,
`x-bc`, `User-Agent`). Cualquier fallo que permita leerlas, escribirlas o
enviarlas a terceros es un problema de seguridad prioritario.

Superficies que conviene revisar antes de reportar:

- `ofbackup_cli.py` — receptor HTTP local que recibe la cookie desde la extensión.
- `backend/web_dashboard.py` — dashboard local (solo `127.0.0.1`, con token).
- `backend/auth.py` — fachada de credenciales.
- `android/` — app companion con WebView y puente JavaScript.

## Cómo reportar

**No abras un issue público con cookies, capturas de terminal con secretos ni
archivos `OFBackup-auth.json`.**

Usa la pestaña **Security → Report a vulnerability** del repositorio (GitHub
Security Advisories) para que el informe llegue de forma privada.

Incluye:

1. Versión de la app (`of` o el archivo `backend/constants.py`).
2. Plataforma (Termux, Linux, Windows, a-Shell/iOS).
3. Pasos para reproducirlo, sin credenciales reales.
4. Impacto que crees que tiene.

## Modelo de confianza del receptor local

El receptor escucha en la red local porque la extensión del navegador necesita
enviarle la cookie. Sus defensas son:

- Solo acepta peticiones de extensiones de navegador o de OnlyFans; cualquier
  web de terceros recibe `403` y no puede leer la respuesta de `/pair`.
- Compara el código y el token en tiempo constante.
- El token de emparejamiento solo vale desde la IP que lo pidió.
- Se apaga al primer uso correcto o al agotarse el tiempo.

Aun así, úsalo en una Wi-Fi de confianza o en tu propio hotspot y no lo dejes
abierto más de lo necesario.

## Buenas prácticas para usuarios

- No publiques `OFBackup-auth.json`, `auth.json`, `settings.json` ni logs.
- Si una cookie se filtró, cierra esa sesión en el navegador y genera otra.
- Usa solo contenido al que tu cuenta tenga acceso legítimo.
