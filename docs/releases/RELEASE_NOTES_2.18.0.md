# OF Downloader iOS 2.18.0

- El menú nativo de a-Shell permanece abierto después de cada operación.
- Se añadió `of compilar` (`build`, `preparar`) para compilar bytecode Python y
  comprobar que las carpetas locales sean escribibles.
- El instalador iOS descarga cada módulo mediante un archivo temporal, valida
  que no esté vacío y ejecuta `compileall` antes de crear los lanzadores.
- La variante continúa usando únicamente la biblioteca estándar, sin
  OF-Scraper, procesos hijos, SSH, Termux remoto ni dependencias nativas.
