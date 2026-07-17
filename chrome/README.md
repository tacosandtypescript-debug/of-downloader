# OF Downloader Exporter para Chrome

Extensión local para Chrome PC. Genera `OFBackup-auth.json`, compatible con el
comando `of importar` de OF Downloader.

## Descargar

[⬇️ Descargar la versión preparada para Chrome](https://github.com/tacosandtypescript-debug/respaldo_of/releases/latest/download/of_downloader_exporter-chrome-1.0.1.zip)

El repositorio es privado: GitHub solicitará iniciar sesión.

## Instalar

1. Descomprime el ZIP en una carpeta que no vayas a borrar.
2. Abre `chrome://extensions`.
3. Activa **Modo de desarrollador**.
4. Pulsa **Cargar descomprimida**.
5. Elige la carpeta que contiene `manifest.json`.

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
