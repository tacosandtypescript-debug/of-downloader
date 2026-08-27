#!/bin/sh
set -eu
umask 077

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
download_file() {
    source_url="$1"
    target_path="$2"
    temporary_path="${target_path}.tmp"
    rm -f "${temporary_path}"
    curl -fsSL "${source_url}" -o "${temporary_path}"
    test -s "${temporary_path}"
    mv -f "${temporary_path}" "${target_path}"
}

for file in __init__.py config.py api.py media.py build.py cli.py; do
    download_file "${BASE_URL}/of_ios/${file}" "${APP_DIR}/of_ios/${file}"
done
download_file "${BASE_URL}/of-ios.py" "${APP_DIR}/of-ios.py"

python3 -m compileall -q "${APP_DIR}"
python3 "${APP_DIR}/of-ios.py" compilar >/dev/null

for launcher in of-ios of; do
    cat > "${BIN_DIR}/${launcher}" <<EOF
#!/bin/sh
exec python3 "${APP_DIR}/of-ios.py" "\$@"
EOF
    chmod 700 "${BIN_DIR}/${launcher}"
done

echo "✓ OF Downloader iOS nativo instalado."
echo "Motor Python local compilado y verificado."
echo "Ejecuta: of (también disponible como of-ios)"
echo "Los archivos se guardarán dentro de Documents/OFDownloader."
