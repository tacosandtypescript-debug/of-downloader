#!/bin/sh
set -eu

BASE_URL="https://raw.githubusercontent.com/tacosandtypescript-debug/of-downloader/main/ios"
APP_DIR="${HOME}/Documents/of-downloader-ios"
if [ "$(basename "${HOME}")" = "Documents" ]; then
    APP_DIR="${HOME}/of-downloader-ios"
fi
BIN_DIR="${HOME}/Documents/bin"
if [ "$(basename "${HOME}")" = "Documents" ]; then
    BIN_DIR="${HOME}/bin"
fi

mkdir -p "${APP_DIR}/of_ios" "${BIN_DIR}"
for file in __init__.py config.py api.py media.py cli.py; do
    curl -fsSL "${BASE_URL}/of_ios/${file}" -o "${APP_DIR}/of_ios/${file}"
done
curl -fsSL "${BASE_URL}/of-ios.py" -o "${APP_DIR}/of-ios.py"

for launcher in of-ios of; do
    cat > "${BIN_DIR}/${launcher}" <<EOF
#!/bin/sh
exec python3 "${APP_DIR}/of-ios.py" "\$@"
EOF
    chmod 700 "${BIN_DIR}/${launcher}"
done

echo "✓ OF Downloader iOS nativo instalado."
echo "Ejecuta: of (también disponible como of-ios)"
echo "Los archivos se guardarán dentro de Documents/OFDownloader."
