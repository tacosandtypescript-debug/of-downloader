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

El instalador:

1. Actualiza los paquetes de Termux.
2. Solicita acceso a la carpeta Descargas de Android.
3. Instala un contenedor Debian sin necesidad de root.
4. Instala Python 3.13, FFmpeg y OF-Scraper.
5. Crea el comando global `ofbackup`.

Se usa Debian porque Termux ofrece actualmente Python 3.14 y OF-Scraper 3.14.7
requiere Python 3.11, 3.12 o 3.13.

Abre el menú con:

```bash
ofbackup
```

También puedes descargar directamente con un enlace:

```bash
ofbackup "https://onlyfans.com/ID/usuario"
```

Otros comandos:

```bash
ofbackup configurar
ofbackup usuario NOMBRE
ofbackup diagnostico
ofbackup actualizar
```

La Cookie se solicita mediante una entrada oculta y no aparece en el historial
del terminal. Se extraen automáticamente `sess` y `auth_id`; `x-bc` se solicita
por separado. Los archivos de autenticación se guardan con permisos `0600`.

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
- La autenticación de Termux se almacena en `~/.config/ofscraper/main_profile`.
