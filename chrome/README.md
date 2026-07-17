# OF Downloader Exporter para Chrome

Extensión local para Chrome PC. Genera `OFBackup-auth.json`, compatible con el
comando `of importar` de OF Downloader.

## Descargar

[⬇️ Descargar la versión preparada para Chrome](https://github.com/tacosandtypescript-debug/of-downloader/releases/latest/download/of_downloader_exporter-chrome-1.0.2.zip)

El repositorio es privado: GitHub solicitará iniciar sesión.

## Instalar

1. Descomprime el ZIP en una carpeta que no vayas a borrar.
2. Abre `chrome://extensions`.
3. Activa **Modo de desarrollador**.
4. Pulsa **Cargar descomprimida**.
5. Elige la carpeta que contiene `manifest.json`.

No cargues directamente la carpeta `chrome/` del repositorio: es una plantilla
parcial usada durante la construcción. La carpeta correcta contiene
`manifest.json`, `popup/`, `lib/`, `content/` e `icons/` al mismo nivel.

### Linux: preparación automática

Desde el repositorio ejecuta:

```bash
bash scripts/instalar-extension-linux.sh
```

Después selecciona `~/OFDownloader-Extension` mediante **Cargar descomprimida**.

Si utilizas Chromium sustituye `chrome://extensions` por
`chromium://extensions`. La versión 1.0.2 ya no exige Chrome 122, por lo que
funciona también con versiones anteriores que admitan Manifest V3.

### Errores habituales

- **Manifest file is missing or unreadable:** seleccionaste el ZIP, la carpeta
  exterior equivocada o `chrome/`. Elige la carpeta que contiene `manifest.json`.
- **No se pudo cargar el icono o el popup:** el paquete está incompleto; vuelve
  a ejecutar el instalador de Linux.
- **La extensión abre pero no exporta:** abre OnlyFans, inicia sesión, recarga la
  pestaña y vuelve a pulsar **Exportar**.

Chrome para Android no admite extensiones locales. La exportación debe hacerse
desde Chrome en un PC.

## Usar

1. Inicia sesión en OnlyFans desde Chrome.
2. Recarga la página.
3. Abre **OF Downloader Exporter**.
4. Pulsa **Exportar para OF Downloader**.
5. Pasa `OFBackup-auth.json` a la carpeta Download del teléfono.
6. En Termux ejecuta `of importar` y después `of probar`.

El archivo contiene credenciales de sesión. No lo compartas y elimínalo
después de importarlo.

## Construir desde el código

```bash
npm run test:extension
npm run build:chrome
```

El resultado queda en `build/chrome` y el ZIP en `artifacts/`.
