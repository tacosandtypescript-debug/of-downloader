# OF Downloader nativo para a-Shell (iOS) · motor 2.18.0

Esta variante ejecuta autenticación, consultas y descargas dentro de a-Shell.
No usa SSH, Termux, Linux remoto, `proot` ni OF-Scraper.

## Instalar

En a-Shell completo (no a-Shell mini), ejecuta:

```sh
curl -fsSL https://raw.githubusercontent.com/tacosandtypescript-debug/of-downloader/main/instalar-ios.sh | sh
```

Después:

```sh
of
```

El instalador crea `of` como comando principal y `of-ios` como alias.

El instalador descarga los módulos desde `main`, comprueba que no estén vacíos
y ejecuta `python3 -m compileall` dentro de la carpeta de a-Shell. No instala
OF-Scraper, módulos C ni un backend remoto.

## Importar el acceso

Guarda `OFBackup-auth.json` en Archivos > En mi iPhone > a-Shell y ejecuta:

```sh
of importar OFBackup-auth.json
of probar
```

El programa almacena únicamente `sess`, `auth_id`, `x-bc` y `user_agent` en
`~/OFDownloader/.private/auth.json`. Elimina el JSON original después de
importarlo.

## Descargar

```sh
of perfiles
of listar-perfiles
of usuario NOMBRE
of publicacion https://onlyfans.com/usuario/123456789
of "https://onlyfans.com/usuario/123456789"
of probar-perfil NOMBRE
```

`of perfiles` conserva el flujo original: muestra tus suscripciones, eliges una
y empieza su descarga. `of listar-perfiles` solo muestra la lista.

El menú permanece abierto después de cada operación. Para preparar el motor de
forma explícita usa:

```sh
of compilar
```

Ese comando compila el bytecode Python disponible en a-Shell y comprueba que
`~/OFDownloader` y `~/OFDownloader/Descargas` sean escribibles. También aparece
como `[7] Preparar/compilar motor iOS` dentro del menú.

Los medios quedan en `~/OFDownloader/Descargas/NOMBRE/`. La descarga es
secuencial para respetar la memoria y el modelo de ejecución de iOS.

## Límites de la primera versión nativa

- Mantén a-Shell abierto y en primer plano durante la descarga.
- Descarga archivos directos accesibles de timeline, archivados y streams.
- Permite seleccionar una suscripción desde el menú interactivo.
- Acepta perfiles por usuario/enlace y publicaciones por ID/enlace.
- Conserva el atajo del CLI original: un enlace de OnlyFans como único
  argumento se interpreta como publicación (si termina en un ID) o perfil.
- Omite contenido bloqueado y DRM; no intenta eludir protecciones.
- No depende de módulos Python con extensiones C ni de procesos hijos.
- Las descargas largas deben mantenerse en primer plano dentro de a-Shell.
- La comprobación final debe realizarse físicamente en a-Shell sobre iOS.
