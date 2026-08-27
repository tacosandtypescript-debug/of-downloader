# OF Downloader nativo para a-Shell (iOS)

Esta variante ejecuta autenticación, consultas y descargas dentro de a-Shell.
No usa SSH, Termux, Linux remoto, `proot` ni OF-Scraper.

## Instalar

En a-Shell completo (no a-Shell mini), ejecuta:

```sh
curl -fsSL https://raw.githubusercontent.com/tacosandtypescript-debug/of-downloader/main/instalar-ios.sh | sh
```

Después:

```sh
of-ios
```

## Importar el acceso

Guarda `OFBackup-auth.json` en Archivos > En mi iPhone > a-Shell y ejecuta:

```sh
of-ios importar OFBackup-auth.json
of-ios probar
```

El programa almacena únicamente `sess`, `auth_id`, `x-bc` y `user_agent` en
`~/OFDownloader/.private/auth.json`. Elimina el JSON original después de
importarlo.

## Descargar

```sh
of-ios perfiles
of-ios usuario NOMBRE
```

Los medios quedan en `~/OFDownloader/Descargas/NOMBRE/`. La descarga es
secuencial para respetar la memoria y el modelo de ejecución de iOS.

## Límites de la primera versión nativa

- Mantén a-Shell abierto y en primer plano durante la descarga.
- Descarga archivos directos accesibles de timeline, archivados y streams.
- Omite contenido bloqueado y DRM; no intenta eludir protecciones.
- No depende de módulos Python con extensiones C ni de procesos hijos.
- La comprobación final debe realizarse físicamente en a-Shell sobre iOS.
