# OF Downloader iOS 2.18.1

- `of importar` descubre archivos JSON de acceso aunque tengan un nombre
  personalizado o UUID; si hay varios, se puede indicar la ruta exacta.
- El importador nativo acepta objetos anidados, headers `Cookie`, aliases de
  `User-Agent`/`x-bc` y listas de cookies cuyo dominio pertenece a OnlyFans.
- Se añadió cobertura de pruebas para el flujo de Archivos y la importación
  desde una carpeta sin usar credenciales reales.
- El lanzador fija `OF_IOS_HOME` en Documents para que la configuración y las
  descargas sigan siendo las mismas aunque se cambie de carpeta.
- La variante sigue siendo local para a-Shell: biblioteca estándar de Python,
  sin Termux remoto, SSH, OF-Scraper ni procesos auxiliares.
