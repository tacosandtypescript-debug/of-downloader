# Contribuir

Gracias por tomarte el tiempo de mejorar OF Downloader.

## Entorno

- Python 3.11, 3.12 o 3.13. En Windows evita 3.13 con OF-Scraper 3.14.7.
- La suite **no necesita** instalar `ofscraper` ni FFmpeg: usa `unittest` con
  dobles de prueba. `psutil` es opcional (pausar/reanudar procesos).

```bash
python -m venv .venv
.venv/bin/python -m pip install --upgrade pip psutil ruff   # Windows: .venv\Scripts\python
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m ruff check .
```

## Reglas del proyecto

1. **Una sola implementación de cada cosa sensible.** Si un módulo de
   `backend/` o `frontend/` es una fachada, debe limitarse a delegar en el
   CLI y no duplicar lógica de credenciales o de red.
2. **No añadas `shell=True`.** Los subprocesos usan listas de argumentos.
3. **Todo en UTF-8.** El archivo `tests/test_hardening.py` falla si aparece
   texto con doble codificación en `ofbackup_cli.py` o `web/index.html`.
4. **Nunca subas credenciales** ni activos generados (`.gitignore` ya cubre
   `OFBackup-auth*.json`, `auth.json` y los logs).
5. **Documenta los cambios en español**, igual que el resto del repositorio.

## Antes de abrir un pull request

- [ ] `python -m unittest discover -s tests -v` termina en verde.
- [ ] `ruff check .` no reporta errores.
- [ ] Si tocas la interfaz, probaste el dashboard con `of dashboard`.
- [ ] Describiste el cambio y cómo verificarlo.

Los cambios que afecten a credenciales, al receptor local o al dashboard deben
explicar su impacto de seguridad en la descripción del PR.
