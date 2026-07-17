<p align="center">
  <img src="docs/banner.svg" alt="OF Downloader" width="100%">
</p>

<p align="center">
  <strong>Descarga publicaciones permitidas por tu cuenta desde un menú sencillo en Termux.</strong>
</p>

<p align="center">
  <a href="https://github.com/tacosandtypescript-debug/respaldo_of/releases/latest/download/of_downloader_exporter-chrome-1.0.1.zip"><strong>Descargar extensión para Chrome</strong></a>
  ·
  <a href="#instalar-of-downloader-en-termux">Instalar en Termux</a>
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
- Interfaz adicional para Windows y Linux de escritorio.

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

### [⬇️ Descargar OF Downloader Exporter para Chrome](https://github.com/tacosandtypescript-debug/respaldo_of/releases/latest/download/of_downloader_exporter-chrome-1.0.1.zip)

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
gh repo clone tacosandtypescript-debug/respaldo_of
cd respaldo_of
bash instalar-termux.sh
```

La primera instalación prepara Debian, Python, FFmpeg y OF-Scraper; puede tardar
varios minutos. La barra indicará el avance. Si falla, consulta:

```bash
tail -n 30 ~/ofbackup-instalacion.log
```

### Actualizar sin reinstalar todo

```bash
cd ~/respaldo_of
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

## Windows y Linux de escritorio

Se requiere Python 3.11, 3.12 o 3.13.

- Windows: ejecuta `iniciar.bat`.
- Linux: ejecuta `bash iniciar.sh`.

## Desarrollo

```bash
python -m unittest discover -s tests
npm run test:extension
npm run build:chrome
npx web-ext lint --source-dir extension
```

El código de Firefox está en `extension/`. La variante local de Chrome se
genera en `build/chrome/`; los ZIP y directorios generados no se guardan en Git.
