# Despliegue

Los scripts reales viven aquí. En la raíz del repositorio quedan atajos
cortos con los nombres públicos (`instalar-termux.sh`, `instalar-linux.sh`,
`instalar-windows.ps1`, `instalar-ios.sh`, `actualizar-termux.sh`) para no
romper `curl | sh`, el README y las instalaciones ya hechas.

| Plataforma | Instalar | Actualizar | Arrancar |
|---|---|---|---|
| Windows | `deploy/windows/instalar.ps1` | el propio instalador | `deploy/windows/launcher.cmd` |
| Linux | `deploy/linux/instalar.sh` | `of actualizar-app` | `deploy/linux/launcher.sh` |
| Termux | `deploy/termux/instalar.sh` | `deploy/termux/actualizar.sh` | `deploy/termux/launcher` |
| iOS / a-Shell | `deploy/ios/instalar.sh` | reinstalar el script | `ios/of-ios.py` |

Cada instalador copia `ofbackup_cli.py`, `backend/`, `frontend/` y, en
escritorio, `web/` al entorno privado de la aplicación. Los comandos públicos
`of` y `ofbackup` no cambian.
