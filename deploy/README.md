# Despliegue

Los instaladores por plataforma siguen siendo los puntos de entrada públicos:

- `instalar-windows.ps1`
- `instalar-linux.sh`
- `instalar-termux.sh`

Cada instalador copia el CLI y los paquetes `backend/` y `frontend/` al entorno
privado de la aplicación. Los lanzadores no cambian sus comandos públicos.

