<p align="center">
  <img src="docs/banner.svg" alt="OF Downloader" width="100%">
</p>

<p align="center">
  <strong>OF Downloader · menú de terminal para Termux, Linux y Windows.</strong>
</p>

<p align="center">
  <a href="#instalación-rápida">Instalación</a>
  ·
  <a href="#extensión-del-navegador">Extensión</a>
  ·
  <a href="#conectar-la-cuenta">Conectar cuenta</a>
  ·
  <a href="#google-drive">Google Drive</a>
  ·
  <a href="#actualizar">Actualizar</a>
</p>

> [!IMPORTANT]
> OF Downloader no evita suscripciones, pagos ni restricciones. Solo organiza
> descargas de contenido disponible para tu propia cuenta. Úsalo respetando los
> derechos de los creadores, las condiciones del servicio y la ley aplicable.

## Qué hace

- Abre un menú simple con el comando `of`.
- Funciona en Termux, Linux y Windows.
- Conecta la cuenta usando la extensión `OF Downloader Exporter`.
- Puede recibir la cookie desde la extensión por red local.
- Lista perfiles suscritos activos cuando OnlyFans los devuelve.
- Descarga perfiles por usuario/enlace y publicaciones por enlace.
- Muestra progreso, resumen y logs visibles.
- Puede subir archivos nuevos a Google Drive usando `rclone`.
- Permite actualizar la app desde el menú.

Versión actual: `2.15.0`

## Links rápidos

- App principal: https://github.com/tacosandtypescript-debug/of-downloader
- Extensiones: https://github.com/tacosandtypescript-debug/of-downloader-browser-extensions
- Descargar ZIP del repo: https://github.com/tacosandtypescript-debug/of-downloader/archive/refs/heads/main.zip

## Instalación rápida

### Termux / Android

Instala Termux desde F-Droid o GitHub. No uses la versión antigua de Google Play.

```bash
pkg update -y
pkg install -y git
git clone https://github.com/tacosandtypescript-debug/of-downloader.git
cd of-downloader
bash instalar-termux.sh
of
```

### Linux

```bash
sudo apt update
sudo apt install -y git
git clone https://github.com/tacosandtypescript-debug/of-downloader.git
cd of-downloader
bash instalar-linux.sh
of
```

### Windows

Abre PowerShell:

```powershell
winget install -e --id Git.Git
git clone https://github.com/tacosandtypescript-debug/of-downloader.git "$env:USERPROFILE\of-downloader"
cd "$env:USERPROFILE\of-downloader"
powershell -NoProfile -ExecutionPolicy Bypass -File .\instalar-windows.ps1
```

Abre una terminal nueva y ejecuta:

```powershell
of
```

El instalador de Windows intenta preparar Python 3.12, FFmpeg y rclone con
`winget`. No uses Python 3.13 para esta app en Windows.

## Extensión del navegador

La extensión se usa para conectar tu cuenta sin pegar cookies manualmente.

Descargas:

- Chrome / Chromium:
  https://github.com/tacosandtypescript-debug/of-downloader-browser-extensions/raw/main/artifacts/of_downloader_exporter-chrome-1.0.6.zip
- Firefox:
  https://github.com/tacosandtypescript-debug/of-downloader-browser-extensions/raw/main/artifacts/of_downloader_exporter-firefox-1.0.7.zip

### Instalar en Chrome / Chromium

1. Descarga el ZIP de Chrome.
2. Descomprime el ZIP.
3. Abre `chrome://extensions`.
4. Activa **Modo de desarrollador**.
5. Pulsa **Cargar descomprimida**.
6. Selecciona la carpeta que contiene `manifest.json`.

Si Chrome dice que falta el manifiesto, seleccionaste la carpeta equivocada.
Entra una carpeta más adentro hasta ver `manifest.json`.

### Instalar en Firefox

Usa el ZIP de Firefox o el complemento firmado desde Mozilla Add-ons si ya está
aprobado en tu cuenta.

## Conectar la cuenta

Flujo recomendado:

1. Abre OF Downloader:

```bash
of
```

2. Elige:

```text
[11] Recibir cookie desde extension
```

3. Abre OnlyFans en el navegador donde instalaste la extensión.
4. Abre la extensión `OF Downloader Exporter`.
5. Pulsa **Buscar OF Downloader en mi red**.
6. Si encuentra el celular/PC, pulsa **Enviar a OF Downloader**.
7. Comprueba:

```bash
of probar
```

Respaldo manual si la búsqueda no funciona:

```bash
of recibir-cookie
of recibir-cookie --qr
```

Ese modo muestra enlace rápido, URL local y código temporal. El QR o enlace no
contiene la cookie; solo sirve para vincular la extensión con OF Downloader. La
cookie se envía aparte por red local y el servidor se cierra después de recibir.

## Menú principal

```text
DESCARGAS
[1] Elegir perfil de mis suscripciones
[2] Descargar perfil por usuario o enlace
[3] Descargar publicación por enlace

MI CUENTA
[4] Conectar o renovar acceso
[5] Probar acceso
[11] Recibir cookie desde extension

HERRAMIENTAS
[6] Cambiar carpeta de descargas
[7] Ver diagnóstico
[8] Actualizar OF Downloader y reiniciar
[9] Actualizar motor de descarga
[10] Google Drive
[0] Salir
```

## Comandos útiles

```bash
of
of perfiles
of usuario NOMBRE
of "https://onlyfans.com/..."
of probar
of diagnostico
of actualizar-app
of recibir-cookie
of recibir-cookie --qr
```

## Google Drive

OF Downloader usa `rclone` para subir a Google Drive.

```bash
of drive instalar
of drive configurar
of drive activar
of drive estado
of drive subir
of drive pendientes
of drive limpiar
of drive limpiar todo
```

Por defecto:

- Remote: `gdrive`
- Carpeta en Drive: `OFDownloader`
- No borra archivos locales después de subir.
- Si falla una subida, queda en pendientes.

En Termux, `rclone` debe existir dentro del Debian interno. Si falta:

```bash
proot-distro login --shared-home ofbackup-debian -- apt-get update
proot-distro login --shared-home ofbackup-debian -- apt-get install -y rclone qrencode
```

## Rutas importantes

### Termux

- Repo: `~/of-downloader`
- Descargas: `/root/storage/downloads/OFBackup`
- Config privada: `/root/.config/ofbackup`
- Config OF-Scraper: `/root/.config/ofscraper`
- Logs visibles: `/root/storage/downloads/OFBackup`

### Linux

- Repo: `~/of-downloader`
- Descargas: `~/Downloads/OFDownloader`
- Config privada: `~/.config/ofbackup`
- Config OF-Scraper: `~/.config/ofscraper`

### Windows

- Repo: `%USERPROFILE%\of-downloader`
- Descargas: `%USERPROFILE%\Downloads\OFDownloader`
- Config privada: `%USERPROFILE%\.config\ofbackup`
- Config OF-Scraper: `%USERPROFILE%\.config\ofscraper`
- Comandos: `%LOCALAPPDATA%\Programs\OFDownloader\bin`

## Actualizar

Desde el menú:

```text
[8] Actualizar OF Downloader y reiniciar
```

Manual:

```bash
cd ~/of-downloader
git pull --ff-only origin main
bash instalar-termux.sh
```

En Linux cambia el último comando por:

```bash
bash instalar-linux.sh
```

En Windows:

```powershell
cd "$env:USERPROFILE\of-downloader"
git pull --ff-only origin main
powershell -NoProfile -ExecutionPolicy Bypass -File .\instalar-windows.ps1
```

## Reinstalar limpio

### Termux

```bash
rm -rf ~/of-downloader
git clone https://github.com/tacosandtypescript-debug/of-downloader.git
cd of-downloader
bash instalar-termux.sh
```

Para borrar también configuración/cookies:

```bash
rm -rf /root/.config/ofbackup /root/.config/ofscraper
```

### Windows

```powershell
Remove-Item -Recurse -Force "$env:USERPROFILE\of-downloader"
Remove-Item -Recurse -Force "$env:LOCALAPPDATA\Programs\OFDownloader"
git clone https://github.com/tacosandtypescript-debug/of-downloader.git "$env:USERPROFILE\of-downloader"
cd "$env:USERPROFILE\of-downloader"
powershell -NoProfile -ExecutionPolicy Bypass -File .\instalar-windows.ps1
```

## Seguridad

- No pegues cookies en chats, issues ni capturas.
- No publiques `OFBackup-auth.json`, `auth.json` ni `config.json`.
- El QR/enlace de conexión no contiene la cookie.
- La extensión no guarda la cookie.
- Si una cookie se filtró, cierra esa sesión en el navegador y genera otra.
- Usa solo contenido al que tu cuenta tenga acceso legítimo.

## Desarrollo

```bash
python -m unittest discover -s tests
```

Archivos principales:

```text
ofbackup_cli.py              Menú terminal
instalar-termux.sh           Instalador Termux
instalar-linux.sh            Instalador Linux
instalar-windows.ps1         Instalador Windows
ofbackup                     Launcher Termux
of-downloader-linux          Launcher Linux
of-windows.cmd               Launcher Windows terminal
tests/                       Pruebas automáticas
docs/                        Recursos visuales
```
