# OF Downloader Exporter

Extensión para Firefox Android y escritorio. Genera localmente
`OFBackup-auth.json`, compatible con `of importar`.

## Desarrollo

1. Instala Node.js y `web-ext`.
2. Desde esta carpeta ejecuta `web-ext lint`.
3. Para escritorio usa `web-ext run`.
4. Para Android usa `web-ext run -t firefox-android` siguiendo la guía oficial
   de Mozilla.

La extensión no usa servidores, telemetría, portapapeles ni almacenamiento
persistente. El archivo exportado contiene credenciales de sesión y no debe
compartirse.

## Distribución inicial

Empaqueta el contenido de esta carpeta, solicita una firma **unlisted** en AMO
y prueba el XPI firmado antes de crear una ficha pública.

## Atribución

La técnica para leer `bcTokenSha` está basada en
M-rcus/OnlyFans-Cookie-Helper, distribuido bajo licencia MIT. Consulta
`NOTICE.md` y `LICENSE.md`.
