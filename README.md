<p align="center">
  <img src="docs/banner.svg" alt="OF Downloader" width="100%">
</p>

<p align="center">
  <strong>OF Downloader · menu de terminal para Termux, Linux y Windows.</strong>
</p>

<p align="center">
  <a href="https://github.com/tacosandtypescript-debug/of-downloader/archive/refs/heads/main.zip"><strong>Descargar ZIP</strong></a>
  ·
  <a href="#instalacion-rapida">Instalacion rapida</a>
  ·
  <a href="#extension-del-navegador">Extension</a>
  ·
  <a href="#google-drive">Google Drive</a>
  ·
  <a href="#menu-actual">Menu</a>
  ·
  <a href="#reinstalar-limpio">Reinstalar limpio</a>
</p>

> [!IMPORTANT]
> Este repositorio es privado. Para clonar o descargar el ZIP debes iniciar
> sesion en GitHub con una cuenta autorizada.

OF Downloader no evita suscripciones, pagos ni restricciones. Solo organiza la
descarga de contenido disponible para tu propia cuenta. Usa la herramienta
respetando los derechos de los creadores, las condiciones del servicio y la ley
aplicable.

## Que hace

- Abre un menu simple en terminal con el comando `of`.
- Importa el archivo `OFBackup-auth.json` creado por la extension del navegador.
- Lista perfiles suscritos activos, incluidos perfiles gratis cuando OnlyFans los devuelve.
- Permite escoger un perfil y detecta posts/fotos/videos antes de descargar.
- Pregunta antes de descargar un perfil.
- Descarga perfiles por usuario/enlace y publicaciones por enlace.
- Muestra barra de progreso, resumen y logs visibles.
- Puede subir automaticamente archivos nuevos a Google Drive usando rclone.
- Permite actualizar la app desde el menu.

Version actual de la app: `2.10.1`.

## Links rapidos

- Repo privado:
  https://github.com/tacosandtypescript-debug/of-downloader
- Descargar todo el repo en ZIP:
  https://github.com/tacosandtypescript-debug/of-downloader/archive/refs/heads/main.zip
- Instalador Windows:
  https://github.com/tacosandtypescript-debug/of-downloader/blob/main/instalar-windows.ps1
- Instalador Termux:
  https://github.com/tacosandtypescript-debug/of-downloader/blob/main/instalar-termux.sh
- Instalador Linux:
  https://github.com/tacosandtypescript-debug/of-downloader/blob/main/instalar-linux.sh
- Repo de extensiones Chrome/Firefox:
  https://github.com/tacosandtypescript-debug/of-downloader-browser-extensions
- rclone:
  https://rclone.org/

## Instalacion rapida

### Termux / Android

Instala Termux desde F-Droid o GitHub, no desde Google Play. Instala tambien
Termux:API desde la misma fuente para abrir el selector de archivos Android.

```bash
pkg update -y && pkg install -y git gh
gh auth login
gh repo clone tacosandtypescript-debug/of-downloader
cd of-downloader
bash instalar-termux.sh
```

Abrir:

```bash
of
```

### Linux

```bash
sudo apt update && sudo apt install -y git gh
gh auth login
gh repo clone tacosandtypescript-debug/of-downloader
cd of-downloader
bash instalar-linux.sh
```

Abrir:

```bash
of
```

### Windows

Desde PowerShell:

```powershell
gh auth login
gh repo clone tacosandtypescript-debug/of-downloader "$env:USERPROFILE\of-downloader"
cd "$env:USERPROFILE\of-downloader"
powershell -NoProfile -ExecutionPolicy Bypass -File .\instalar-windows.ps1
```

Abrir una terminal nueva y ejecutar:

```powershell
of
```

El instalador intenta preparar Python 3.12 y FFmpeg con `winget` si no estan
instalados. No uses Python 3.13 para esta app en Windows.

## Extension del navegador

La extension exporta el archivo `OFBackup-auth.json`. Ese archivo es lo que
debes cargar en OF Downloader.

Descargas:

- Chrome / Chromium:
  https://github.com/tacosandtypescript-debug/of-downloader-browser-extensions/releases/latest/download/of_downloader_exporter-chrome-1.0.4.zip
- Firefox:
  https://github.com/tacosandtypescript-debug/of-downloader-browser-extensions/releases/latest/download/of_downloader_exporter-firefox-1.0.5.zip

### Chrome

Chrome no permite instalar extensiones locales con un solo clic si no estan en
Chrome Web Store.

1. Descarga el ZIP de Chrome.
2. Descomprimelo.
3. Abre `chrome://extensions`.
4. Activa **Modo de desarrollador**.
5. Pulsa **Cargar descomprimida**.
6. Selecciona la carpeta que contiene `manifest.json`.

Si aparece “Falta el archivo de manifiesto”, seleccionaste la carpeta equivocada:
entra una carpeta mas adentro hasta ver `manifest.json`.

### Firefox

Usa el ZIP de Firefox desde las releases. Si tienes el complemento firmado desde
Mozilla Add-ons, puedes usar ese en lugar del ZIP local.

## Conectar la cuenta

1. Abre OnlyFans en Chrome o Firefox.
2. Inicia sesion.
3. Pulsa la extension **OF Downloader Exporter**.
4. Exporta `OFBackup-auth.json`.
5. En OF Downloader usa:

```bash
of importar
of probar
```

En Termux se abre el selector Android. En Windows/Linux se abre el explorador de
archivos. Si el selector falla, tambien puedes pasar la ruta:

```bash
of importar ~/Downloads/OFBackup-auth.json
```

Para ver el flujo completo de exportar, pasar el archivo entre movil y PC e
importarlo:

```bash
of cookie ayuda
```

Tambien puedes evitar mover archivos:

```bash
of recibir-cookie
```

Ese comando muestra una URL local y un codigo temporal. En la extension pulsa
**Enviar a OF Downloader**, escribe esos dos datos y la app guarda el acceso.
Usalo solo en una Wi-Fi de confianza o hotspot propio.

La app solo conserva:

- `sess`
- `auth_id`
- `x-bc`
- `User-Agent`

Despues de importar, borra `OFBackup-auth.json` de Descargas.

### Pasar la cookie entre movil y PC

No pegues la cookie en chats ni la escribas a mano. La forma correcta es mover
el archivo `OFBackup-auth.json` como archivo:

- PC a movil: cable USB, Google Drive, Nearby Share, Telegram guardado como
  archivo o copiarlo a Descargas del telefono.
- Movil a PC: Google Drive, cable USB, Nearby Share, correo propio como archivo
  adjunto o descargarlo en `Downloads`.

Luego ejecuta:

```bash
of importar
of probar
```

Si el selector no abre, usa `of importar RUTA/OFBackup-auth.json`.

## Menu actual

```text
DESCARGAS
[1] Elegir perfil de mis suscripciones
[2] Descargar perfil por usuario o enlace
[3] Descargar publicacion por enlace

MI CUENTA
[4] Conectar o renovar acceso
[5] Probar acceso

HERRAMIENTAS
[6] Cambiar carpeta de descargas
[7] Ver diagnostico
[8] Actualizar OF Downloader y reiniciar
[9] Actualizar motor de descarga
[10] Google Drive
[0] Salir
```

Comandos directos:

```bash
of
of perfiles
of usuario NOMBRE
of "https://onlyfans.com/..."
of probar
of diagnostico
of actualizar-app
of recibir-cookie
of drive estado
of drive pendientes
of drive limpiar
```

## Google Drive

OF Downloader usa `rclone` para subir a Google Drive. La primera configuracion
requiere iniciar sesion en Google desde el flujo de `rclone config`.

En Termux, `rclone` debe existir dentro del Debian interno que usa OF Downloader.
Si `of diagnostico` muestra `rclone no instalado`, ejecuta:

```bash
pkg install -y proot-distro
proot-distro login --shared-home ofbackup-debian -- apt-get update
proot-distro login --shared-home ofbackup-debian -- apt-get install -y rclone
```

Comandos:

```bash
of drive configurar
of drive instalar
of drive activar
of drive subir
of drive pendientes
of drive limpiar
of drive limpiar todo
of drive estado
of drive desactivar
```

Por defecto:

- Remote: `gdrive`
- Carpeta en Drive: `OFDownloader`
- No borra archivos locales despues de subir.
- Si falla una subida, queda en pendientes y se puede reintentar con `of drive subir`.
- `of drive pendientes` muestra la cola.
- `of drive limpiar` borra pendientes cuyo archivo local ya no existe.
- `of drive limpiar todo` vacia toda la cola pendiente.
- `of drive instalar` intenta instalar `rclone` si no quedo instalado.

Comando avanzado para revisar deteccion de un perfil:

```bash
of probar-perfil NOMBRE
```

## Rutas importantes

### Termux

- Repo: `~/of-downloader`
- Descargas: `/root/storage/downloads/OFBackup`
- Config privada: `/root/.config/ofbackup`
- Config OF-Scraper: `/root/.config/ofscraper`
- Log descarga: `/root/storage/downloads/OFBackup/ultima-descarga.log`
- Log perfiles: `/root/storage/downloads/OFBackup/perfiles-suscritos.log`
- Log prueba perfil: `/root/storage/downloads/OFBackup/prueba-perfil.log`

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

Desde el menu:

```text
8. Actualizar OF Downloader y reiniciar
```

Manual en Termux:

```bash
cd ~/of-downloader
git pull --ff-only origin main
bash instalar-termux.sh
```

Manual en Linux:

```bash
cd ~/of-downloader
git pull --ff-only origin main
bash instalar-linux.sh
```

Manual en Windows:

```powershell
cd "$env:USERPROFILE\of-downloader"
git pull --ff-only origin main
powershell -NoProfile -ExecutionPolicy Bypass -File .\instalar-windows.ps1
```

## Reinstalar limpio

### Termux

```bash
rm -rf ~/of-downloader
gh repo clone tacosandtypescript-debug/of-downloader
cd of-downloader
bash instalar-termux.sh
```

Para borrar tambien configuracion/cookies:

```bash
rm -rf /root/.config/ofbackup /root/.config/ofscraper
```

### Windows

```powershell
Remove-Item -Recurse -Force "$env:USERPROFILE\of-downloader"
Remove-Item -Recurse -Force "$env:LOCALAPPDATA\Programs\OFDownloader"
gh repo clone tacosandtypescript-debug/of-downloader "$env:USERPROFILE\of-downloader"
cd "$env:USERPROFILE\of-downloader"
powershell -NoProfile -ExecutionPolicy Bypass -File .\instalar-windows.ps1
```

Para borrar tambien configuracion/cookies:

```powershell
Remove-Item -Recurse -Force "$env:USERPROFILE\.config\ofbackup"
Remove-Item -Recurse -Force "$env:USERPROFILE\.config\ofscraper"
```

## Seguridad

- No pegues cookies en chats, issues ni capturas.
- No publiques `OFBackup-auth.json`, `auth.json` ni `config.json`.
- Si una cookie se filtro, cierra esa sesion en el navegador y exporta otra.
- Usa solo contenido al que tu cuenta tenga acceso legitimo.

## Desarrollo

```bash
python -m unittest discover -s tests
```

Archivos principales:

```text
ofbackup_cli.py              Menu terminal
instalar-termux.sh           Instalador Termux
instalar-linux.sh            Instalador Linux
instalar-windows.ps1         Instalador Windows
ofbackup                     Launcher Termux
of-downloader-linux          Launcher Linux
of-windows.cmd               Launcher Windows terminal
tests/                       Pruebas automaticas
docs/                        Recursos visuales
```
