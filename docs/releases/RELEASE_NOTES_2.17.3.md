# OF Downloader 2.17.3

## Progreso en vivo

- El backend expone `/api/events` mediante Server-Sent Events.
- La cola envía snapshots cuando cambia el estado de un trabajo.
- El dashboard puede actualizar la cola sin esperar al siguiente sondeo.
