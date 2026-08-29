# Despliegue

Los instaladores de la raíz del repositorio son los puntos de entrada públicos.
No los muevas: README, `curl | sh` y el actualizador de Termux apuntan a esas rutas.

| Plataforma | Instalar | Actualizar | Arrancar |
|---|---|---|---|
| Windows | `instalar-windows.ps1` | el propio instalador | `of-windows.cmd` |
| Linux | `instalar-linux.sh` | `of actualizar-app` | `of-downloader-linux` |
| Termux | `instalar-termux.sh` | `actualizar-termux.sh` | `ofbackup` |
| iOS / a-Shell | `instalar-ios.sh` | reinstalar el script | `ios/of-ios.py` |

Los scripts de esta carpeta solo reenvían a esos archivos:

```text
deploy/windows/instalar.ps1  → instalar-windows.ps1
deploy/linux/instalar.sh     → instalar-linux.sh
deploy/termux/instalar.sh    → instalar-termux.sh
```

Cada instalador copia `ofbackup_cli.py`, `backend/`, `frontend/` y, en
escritorio, `web/` al entorno privado de la aplicación. Los comandos públicos
`of` y `ofbackup` no cambian.
