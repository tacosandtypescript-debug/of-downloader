<p align="center">
  <img src="docs/banner.svg" alt="OF Downloader" width="100%">
</p>

<p align="center">
  <strong>Una interfaz sencilla para Linux y Termux que organiza el contenido permitido por tu cuenta.</strong>
</p>

<p align="center">
  <a href="#instalar-of-downloader-en-linux"><strong>Instalar en Linux</strong></a>
  ·
  <a href="#instalar-of-downloader-en-termux">Instalar en Termux</a>
  ·
  <a href="https://github.com/tacosandtypescript-debug/of-downloader/releases/latest/download/of_downloader_exporter-chrome-1.0.2.zip">Extensión para Chrome</a>
  ·
  <a href="#usar-la-extensión-y-cargar-el-acceso">Cargar el acceso</a>
</p>

> [!IMPORTANT]
> El repositorio y sus publicaciones son privados. Debes iniciar sesión en
> GitHub con la cuenta autorizada para descargar la extensión.

OF Downloader organiza contenido al que tu propia cuenta ya tiene acceso. No
evita suscripciones ni muros de pago. Utilízalo respetando las condiciones del
servicio, los derechos de los creadores y la legislación aplicable.

## Qué incluye

- Menú interactivo y con colores para Termux.
- Descarga mediante un enlace o por nombre de usuario.
- Extensión local para exportar los datos necesarios desde Chrome PC.
- Importación segura de `OFBackup-auth.json` desde Descargas.
- Comprobación de la sesión sin descargar contenido.
- Barra de progreso compacta y registro de errores privado.
- Menú de terminal para Linux y Termux; interfaz gráfica adicional para Windows.

## Elige dónde quieres usarlo

| Equipo | Instalación | Cómo se abre |
| --- | --- | --- |
| **Linux de escritorio** | [`instalar-linux.sh`](#instalar-of-downloader-en-linux) | Menú de aplicaciones, `of` o `of-downloader` |
| **Android con Termux** | [`instalar-termux.sh`](#instalar-of-downloader-en-termux) | Comando `of` |
| **Chrome o Chromium en PC** | [Descargar extensión](https://github.com/tacosandtypescript-debug/of-downloader/releases/latest/download/of_downloader_exporter-chrome-1.0.2.zip) | Icono de extensiones |
| **Windows** | `iniciar.bat` | Ventana de OF Downloader |

## Instalar OF Downloader en Linux

### Enlace del repositorio

### [Abrir OF Downloader para instalarlo en Linux](https://github.com/tacosandtypescript-debug/of-downloader#instalar-of-downloader-en-linux)

Como el repositorio es privado, primero inicia sesión con GitHub CLI. Después
copia este bloque completo en la terminal:

```bash
sudo apt update && sudo apt install -y git gh
gh auth login
gh repo clone tacosandtypescript-debug/of-downloader
cd of-downloader
bash instalar-linux.sh
```

El instalador comprueba Python y FFmpeg, instala el motor en una carpeta privada
y crea dos accesos al menú de terminal:

- **OF Downloader** en el menú de aplicaciones de Linux, abriendo una terminal.
- `of` y `of-downloader` en `~/.local/bin` para abrirlo desde una terminal.

Puede tardar varios minutos. Si encuentra un error se detiene y deja el detalle
en `/tmp/of-downloader-instalacion.log`.

Las descargas quedan en `~/Downloads/OFDownloader` y la configuración privada en
`~/.config/ofbackup`. Para actualizar una instalación existente:

```bash
cd ~/of-downloader
git pull --ff-only
bash instalar-linux.sh
```

## Guía rápida

```text
Chrome PC                 Teléfono Android                 Termux
─────────                 ────────────────                 ──────
1. Iniciar sesión         3. Guardar el JSON              4. of importar
2. Exportar el JSON  ──────▶  en la carpeta Download  ──────▶  5. of probar
                                                           6. of
```

## Instalar la extensión en Google Chrome

La extensión se instala localmente y no se publica en Chrome Web Store. Chrome
no permite instalar este tipo de extensión directamente con un solo clic: hay
que descomprimirla y usar **Cargar descomprimida**. Esto se hace una sola vez.

> [!NOTE]
> Estas instrucciones son para **Chrome en PC**. Chrome para Android no admite
> extensiones locales.

### 1. Descargar

Pulsa el botón y guarda el ZIP:

### [⬇️ Descargar OF Downloader Exporter para Chrome](https://github.com/tacosandtypescript-debug/of-downloader/releases/latest/download/of_downloader_exporter-chrome-1.0.2.zip)

### 2. Descomprimir

En Windows:

1. Abre la carpeta **Descargas**.
2. Pulsa con el botón derecho sobre el ZIP.
3. Elige **Extraer todo**.
4. Conserva la carpeta extraída. Dentro debe aparecer `manifest.json`.

### 3. Cargar en Chrome

1. Escribe `chrome://extensions` en la barra de direcciones.
2. Activa **Modo de desarrollador** arriba a la derecha.
3. Pulsa **Cargar descomprimida**.
4. Selecciona la carpeta que contiene `manifest.json`.
5. Fija **OF Downloader Exporter** desde el icono de extensiones de Chrome.

> [!WARNING]
> No selecciones la carpeta `chrome/` del código fuente: contiene solamente
> archivos de construcción y no es una extensión completa. Selecciona la carpeta
> extraída del ZIP, donde aparecen juntos `manifest.json`, `popup`, `lib`,
> `content` e `icons`.

### Instalación asistida en Linux

Desde la carpeta clonada del repositorio ejecuta:

```bash
bash scripts/instalar-extension-linux.sh
```

El script descarga la publicación privada, la descomprime en
`~/OFDownloader-Extension`, comprueba que no falten archivos y muestra la ruta
exacta que debes elegir en `chrome://extensions` o `chromium://extensions`.

Cuando el repositorio publique una versión nueva, descarga el ZIP nuevo,
reemplaza la carpeta anterior y pulsa **Actualizar** en `chrome://extensions`.

## Usar la extensión y cargar el acceso

### En Chrome PC

1. Abre `https://onlyfans.com` e inicia sesión.
2. Recarga la página y espera a que termine de cargar.
3. Pulsa el icono **OF Downloader Exporter**.
4. Pulsa **Exportar para OF Downloader**.
5. Chrome guardará `OFBackup-auth.json` en Descargas.

La extensión procesa los datos localmente. No usa servidores propios,
telemetría ni portapapeles.

### Pasar el archivo al teléfono

Coloca `OFBackup-auth.json` en la carpeta **Download** del almacenamiento
interno de Android. Puedes transferirlo por cable o mediante tu almacenamiento
personal. No lo envíes a otras personas ni lo publiques.

### Cargarlo en Termux

Con el selector de Android:

```bash
of importar
```

O indicando la ruta directamente, que suele ser más fiable:

```bash
of importar "$HOME/storage/downloads/OFBackup-auth.json"
```

Comprueba que quedó conectado:

```bash
of probar
```

El resultado correcto es:

```text
✓ COOKIE VÁLIDA
OnlyFans aceptó la sesión.
```

Después elimina `OFBackup-auth.json` de Descargas. OF Downloader conserva solo
los cuatro campos necesarios en un archivo privado con permisos restringidos.

## Instalar OF Downloader en Termux

### Requisitos

- Termux de F-Droid o de las publicaciones oficiales de GitHub.
- La aplicación **Termux:API** de la misma fuente que Termux.
- Una conexión estable, espacio libre y preferiblemente el cargador conectado.
- Acceso a este repositorio privado.

No uses la antigua versión de Termux de Google Play.

### Instalación desde cero

```bash
pkg update -y && pkg install -y git gh
gh auth login
gh repo clone tacosandtypescript-debug/of-downloader
cd of-downloader
bash instalar-termux.sh
```

La primera instalación prepara Debian, Python, FFmpeg y OF-Scraper; puede tardar
varios minutos. La barra indicará el avance. Si falla, consulta:

```bash
tail -n 30 ~/ofbackup-instalacion.log
```

### Actualizaciones automáticas

Al abrir `of`, el menú comprueba durante unos segundos si el repositorio tiene
cambios. Cuando existe una versión nueva muestra **ACTUALIZACIÓN DISPONIBLE**.
Elige la opción **8. Actualizar OF Downloader y reiniciar**. La aplicación:

1. Descarga los cambios con avance rápido y seguro (`git pull --ff-only`).
2. Actualiza sus archivos y componentes cuando sea necesario.
3. Conserva credenciales, configuración y descargas.
4. Reinicia automáticamente el menú.

También puedes solicitarlo directamente:

```bash
of actualizar-app
```

### Actualizar manualmente

```bash
cd ~/of-downloader
git pull
install -m 600 ofbackup_cli.py ~/.local/share/ofbackup/ofbackup_cli.py
install -m 755 ofbackup $PREFIX/bin/of
install -m 755 ofbackup $PREFIX/bin/ofbackup
```

## Descargar contenido

Abre el menú:

```bash
of
```

Para una publicación, elige **1** y pega su enlace. Para un usuario completo,
elige **2** y escribe el nombre sin `@`.

También puedes usar comandos directos:

```bash
of "https://onlyfans.com/ID/usuario"
of usuario NOMBRE
```

Las descargas nuevas se guardan por defecto en:

```text
Descargas/OFDownloader
```

La carpeta se puede cambiar desde la opción **4**.

## Soluciones rápidas

### Android dice que el archivo está vacío

Comprueba el nombre real:

```bash
ls -lh ~/storage/downloads/*.json
```

Luego impórtalo usando exactamente ese nombre:

```bash
of importar "$HOME/storage/downloads/NOMBRE-REAL.json"
```

### La cookie fue rechazada

Vuelve a abrir OnlyFans en Chrome, recarga la página y genera un JSON nuevo.
Los valores `sess`, `auth_id`, `x-bc` y `User-Agent` deben proceder de la misma
sesión.

### La descarga falla

Ejecuta primero:

```bash
of diagnostico
of probar
```

El detalle de la última descarga queda en:

```text
~/.config/ofbackup/ultima-descarga.log
```

## Seguridad

- Nunca publiques `OFBackup-auth.json`, `config.json` ni `auth.json`.
- No pegues cookies en chats, capturas, incidencias o argumentos de comandos.
- Si compartiste un archivo de acceso, cierra esa sesión y genera otro.
- Elimina el JSON exportado después de importarlo.
- Revisa la [política de privacidad de la extensión](extension/PRIVACY.md).

## Windows de escritorio

Se requiere Python 3.11, 3.12 o 3.13.

Ejecuta `iniciar.bat`. En Linux usa el instalador explicado al principio de esta
guía para que se creen correctamente el comando y el acceso del menú.

## Desarrollo

```bash
python -m unittest discover -s tests
npm run test:extension
npm run build:chrome
npx web-ext lint --source-dir extension
```

El código de Firefox está en `extension/`. La variante local de Chrome se
genera en `build/chrome/`; los ZIP y directorios generados no se guardan en Git.
