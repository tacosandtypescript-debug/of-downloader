"""Control y lectura de procesos externos del backend."""

from __future__ import annotations

from queue import Queue

try:
    import psutil
except ImportError:  # pragma: no cover - el instalador incluye psutil
    psutil = None


class PausableProcess:
    """Suspende y reanuda OF-Scraper junto con sus procesos hijos."""

    def __init__(self, pid: int):
        self.process = None
        if psutil is not None and isinstance(pid, int) and pid > 0:
            try:
                self.process = psutil.Process(pid)
            except (psutil.Error, OSError, TypeError, ValueError):
                self.process = None
        self.paused = False

    @property
    def available(self) -> bool:
        return self.process is not None

    def _processes(self):
        if not self.process:
            return []
        try:
            return [self.process, *self.process.children(recursive=True)]
        except (psutil.Error, OSError):
            return [self.process]

    def pause(self) -> bool:
        if not self.process or self.paused:
            return False
        for process in self._processes():
            try:
                process.suspend()
            except (psutil.Error, OSError):
                continue
        self.paused = True
        return True

    def resume(self) -> bool:
        if not self.process or not self.paused:
            return False
        for process in reversed(self._processes()):
            try:
                process.resume()
            except (psutil.Error, OSError):
                continue
        self.paused = False
        return True

    def terminate(self) -> bool:
        """Termina el proceso y sus hijos, incluso si estaban pausados."""
        if not self.process:
            return False
        if self.paused:
            self.resume()
        terminated = False
        for process in reversed(self._processes()):
            try:
                process.terminate()
                terminated = True
            except (psutil.Error, OSError):
                continue
        return terminated


def read_process_output(stream, output: Queue[str | None]) -> None:
    """Entrega cada actualización separada por salto de línea o retorno de carro."""
    buffer: list[str] = []
    try:
        while True:
            char = stream.read(1)
            if not char:
                break
            if char in "\r\n":
                if buffer:
                    output.put("".join(buffer))
                    buffer.clear()
            else:
                buffer.append(char)
        if buffer:
            output.put("".join(buffer))
    finally:
        output.put(None)

