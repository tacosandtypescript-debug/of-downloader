# OF Backup

OF Backup permite descargar y organizar contenido al que tu propia cuenta tenga
acceso. Incluye una interfaz gráfica para Windows/Linux de escritorio y un menú
interactivo para Termux.

No evita muros de pago: necesitas acceso válido al contenido y eres responsable
de cumplir las condiciones del servicio y la legislación aplicable.

## Termux (Android)

Usa Termux instalado desde F-Droid o desde las publicaciones oficiales de
GitHub. La versión antigua de Google Play no está soportada.

### Instalación rápida desde GitHub

El repositorio es privado, por lo que primero debes autenticar GitHub CLI en
Termux:

```bash
pkg update -y && pkg install -y git gh
gh auth login
```

Después puedes descargar e instalar todo con una sola línea:

```bash
gh repo clone tacosandtypescript-debug/respaldo_of && cd respaldo_of && bash instalar-termux.sh
```

Repositorio: <https://github.com/tacosandtypescript-debug/respaldo_of>

Si ya descargaste o copiaste la carpeta del proyecto, utiliza la instalación
local indicada a continuación.

Desde la carpeta del repositorio:

```bash
chmod +x instalar-termux.sh
./instalar-termux.sh
```

La primera instalación puede tardar bastante según la velocidad del móvil y
la conexión. Durante la preparación de Python y OF-Scraper pueden transcurrir
varios minutos sin texto nuevo en pantalla; no cierres Termux mientras el
proceso continúe. Es recomendable usar Wi-Fi y mantener el móvil cargando.

El instalador muestra una barra de progreso compacta y guarda el detalle en
`~/ofbackup-instalacion.log`. Si un comando falla, se detiene, marca el paso en
rojo, muestra las últimas líneas útiles y propone una corrección. Para ver toda
la salida mientras instala, utiliza `OFBACKUP_VERBOSE=1 bash instalar-termux.sh`.

El instalador:

1. Actualiza los paquetes de Termux.
2. Instala el comando de Termux:API y solicita acceso a Descargas.
3. Instala un contenedor Debian sin necesidad de root.
4. Instala Python 3.13, FFmpeg y OF-Scraper.
5. Crea el comando global `of` y conserva `ofbackup` como alias.

Se usa Debian porque Termux ofrece actualmente Python 3.14 y OF-Scraper 3.14.7
requiere Python 3.11, 3.12 o 3.13.

Abre el menú con:

```bash
of
```

También puedes descargar directamente con un enlace:

```bash
of "https://onlyfans.com/ID/usuario"
```

Otros comandos:

```bash
of configurar
of importar
of probar
of usuario NOMBRE
of diagnostico
of actualizar
```

El nombre anterior `ofbackup` sigue funcionando para mantener compatibilidad.

### Conectar la cuenta desde Firefox Android o Chrome PC

OF Backup 2.2.0 incorpora **OF Backup Exporter**, una extensión situada en la
carpeta `extension/` y preparada para Firefox Android y escritorio. El flujo es:

1. Instala una copia firmada de la extensión en Firefox.
2. Abre OnlyFans, inicia sesión y recarga la página.
3. Abre la extensión y pulsa **Exportar para OF Backup**.
4. En Termux ejecuta `of importar` o usa la opción **Conectar mi cuenta**.
5. Elige `OFBackup-auth.json` con el selector Android.
6. Ejecuta `of probar` para confirmar la sesión sin descargar contenido.

La variante para Chrome PC se genera desde `chrome/` con:

```bash
npm run build:chrome
```

El comando crea `build/chrome`, que puede cargarse desde `chrome://extensions`
con **Modo de desarrollador > Cargar descomprimida**, y también crea
`artifacts/of_backup_exporter-chrome-1.0.0.zip`. Firefox y Chrome producen el
mismo archivo compatible con `of importar`.

El selector necesita dos componentes: el paquete `termux-api`, instalado por el
script, y la aplicación complementaria **Termux:API**. Termux y Termux:API deben
proceder de la misma fuente; no mezcles instalaciones de F-Droid y GitHub.

La extensión crea el archivo localmente y no utiliza Google Drive, servidores,
telemetría ni portapapeles. OF Backup valida el archivo, conserva únicamente
`sess`, `auth_id`, `x-bc` y `User-Agent`, y compara su huella SHA-256 antes de
eliminar de Descargas el original. La copia temporal privada siempre se elimina.

`of probar` realiza una única consulta autenticada al perfil mediante el motor
de OF-Scraper. No descarga publicaciones y no imprime cookies, nombres ni
identificadores. Informa si la sesión es válida, fue rechazada o no pudo
comprobarse por un problema técnico.

Los métodos anteriores siguen disponibles: puedes pegar una Cookie normal, una
lista JSON del navegador o el JSON completo de OnlyFans-Cookie-Helper. Las
listas de cookies solo aportan `sess` y `auth_id`; `x-bc` y `User-Agent` deben
pertenecer a esa misma sesión.

La Cookie normal se solicita mediante una entrada oculta y no aparece en el
historial del terminal. Los archivos de autenticación se guardan con permisos
`0600`.

Las descargas se guardan por defecto en `Descargas/OFBackup`. Desde el menú se
puede elegir otra carpeta.

### Error `Python.h: No such file or directory`

Las primeras instalaciones podían quedarse detenidas al compilar `xxhash`,
`lxml`, `psutil` o `faust-cchardet`. El instalador actual ya incluye
`python3-dev` y las bibliotecas necesarias. Si ocurrió con una copia anterior,
actualiza el repositorio y vuelve a ejecutar el instalador:

```bash
cd ~/respaldo_of
git pull
bash instalar-termux.sh
```

No hace falta borrar Debian, las credenciales ni las descargas; el instalador
repara el entorno existente y continúa desde donde quedó.

### Error `getattr() takes 1 positional argument but 2 were given`

OF Backup 2.1.3 incluye una compatibilidad para este fallo de configuración de
OF-Scraper 3.14.7. Actualiza el repositorio y vuelve a ejecutar el instalador:

```bash
cd ~/respaldo_of
git pull
bash instalar-termux.sh
```

El proceso conserva las credenciales y los archivos descargados. Además, el
menú ya detecta un `Traceback` aunque OF-Scraper devuelva por error un código de
salida correcto, por lo que no vuelve a mostrar "Descarga terminada" tras un
fallo interno.

### Mensaje `Auth Failed`

`sess`, `auth_id`, `x-bc` y `User-Agent` deben proceder de la misma sesión del
navegador. No sirve un User-Agent aproximado. OF Backup 2.1.4 también acepta el
JSON completo generado por OnlyFans-Cookie-Helper y extrae esos cuatro campos.
Si OnlyFans rechaza el acceso, OF Backup termina con un mensaje claro en vez de
abrir el menú interno de navegadores de OF-Scraper.

## Windows o Linux de escritorio

Se necesita Python 3.11, 3.12 o 3.13.

- Windows: doble clic en `iniciar.bat`.
- Linux: ejecuta `bash iniciar.sh`.

Los scripts crean `.venv`, actualizan pip e instalan las versiones declaradas en
`requirements.txt` antes de abrir la interfaz.

## Seguridad

- Nunca publiques `config.json` ni `auth.json`.
- Renueva la Cookie si sospechas que alguien pudo verla.
- No escribas Cookies como argumentos de comandos: quedan en el historial.
- No compartas ni conserves `OFBackup-auth.json` después de importarlo.
- La autenticación de Termux se almacena en `~/.config/ofscraper/main_profile`.

## Desarrollo de la extensión

El código fuente, la política de privacidad, la atribución MIT y las
instrucciones de prueba están en `extension/`. Antes de una publicación pública
se generará una versión firmada **unlisted** en Mozilla Add-ons para probarla en
Firefox Android y escritorio. Ejecuta las comprobaciones JavaScript con:

```bash
npm run test:extension
npm run build:chrome
npx web-ext lint --source-dir extension
```
