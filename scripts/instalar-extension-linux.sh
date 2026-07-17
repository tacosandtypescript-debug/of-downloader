#!/usr/bin/env bash
set -euo pipefail

REPOSITORY="tacosandtypescript-debug/of-downloader"
ARCHIVE="of_downloader_exporter-chrome-1.0.2.zip"
DESTINATION="${OFDOWNLOADER_EXTENSION_DIR:-$HOME/OFDownloader-Extension}"
CACHE_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/of-downloader-extension"

for command in gh unzip; do
    if ! command -v "$command" >/dev/null 2>&1; then
        echo "✗ Falta el comando '$command'. Instálalo y vuelve a ejecutar este script."
        exit 2
    fi
done

if ! gh auth status >/dev/null 2>&1; then
    echo "GitHub necesita autorizar esta descarga porque el repositorio es privado."
    echo "Ejecuta: gh auth login"
    exit 2
fi

mkdir -p "$CACHE_DIR" "$DESTINATION"
echo "Descargando OF Downloader Exporter para Linux…"
gh release download \
    --repo "$REPOSITORY" \
    --pattern "$ARCHIVE" \
    --dir "$CACHE_DIR" \
    --clobber

unzip -oq "$CACHE_DIR/$ARCHIVE" -d "$DESTINATION"

for required in manifest.json popup/exporter.html popup/exporter.js lib/export-data.js; do
    if [[ ! -f "$DESTINATION/$required" ]]; then
        echo "✗ El paquete está incompleto: falta $required"
        exit 2
    fi
done

echo
echo "✓ Extensión preparada correctamente en:"
echo "  $DESTINATION"
echo
echo "Ahora abre chrome://extensions o chromium://extensions:"
echo "  1. Activa Modo de desarrollador."
echo "  2. Pulsa Cargar descomprimida."
echo "  3. Selecciona exactamente esta carpeta: $DESTINATION"
