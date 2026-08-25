#!/usr/bin/env python3
"""Envía el APK mediante un bot de Telegram sin poner el token en la línea de comandos."""

from __future__ import annotations

import argparse
import getpass
import json
import os
from pathlib import Path
from urllib import error, request


DEFAULT_APK = Path(__file__).resolve().parents[1] / "android" / "build" / "outputs" / "apk" / "debug" / "android-debug.apk"


def send_document(token: str, chat_id: str, apk: Path, caption: str) -> dict:
    boundary = "----OFDOWNLOADER_TELEGRAM_BOUNDARY"
    body = bytearray()

    def field(name: str, value: str) -> None:
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        body.extend(value.encode())
        body.extend(b"\r\n")

    field("chat_id", chat_id)
    field("caption", caption)
    body.extend(f"--{boundary}\r\n".encode())
    body.extend(
        f'Content-Disposition: form-data; name="document"; filename="{apk.name}"\r\n'
        "Content-Type: application/vnd.android.package-archive\r\n\r\n".encode()
    )
    body.extend(apk.read_bytes())
    body.extend(f"\r\n--{boundary}--\r\n".encode())

    endpoint = f"https://api.telegram.org/bot{token}/sendDocument"
    req = request.Request(
        endpoint,
        data=bytes(body),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=60) as response:
            result = json.loads(response.read().decode("utf-8"))
    except (error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"No se pudo contactar con Telegram: {exc}") from exc
    if not result.get("ok"):
        raise RuntimeError(f"Telegram rechazó el envío: {result.get('description', 'error desconocido')}")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apk", type=Path, default=DEFAULT_APK)
    parser.add_argument("--caption", default="OF Downloader Companion · APK de prueba")
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="pedir token oculto y chat ID sin mostrarlos en pantalla",
    )
    args = parser.parse_args()

    if args.interactive:
        token = getpass.getpass("Token nuevo del bot (no se mostrará): ").strip()
        chat_id = input("Chat ID de destino: ").strip()
    else:
        token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        raise SystemExit(
            "Faltan credenciales. Usa --interactive o define TELEGRAM_BOT_TOKEN y TELEGRAM_CHAT_ID."
        )
    if not args.apk.is_file():
        raise SystemExit(f"No existe el APK: {args.apk}")

    send_document(token, chat_id, args.apk, args.caption)
    print(f"APK enviado a Telegram: {args.apk.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
