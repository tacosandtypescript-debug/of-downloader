"""Pruebas de endurecimiento: origen del receptor, fachadas y codificación."""

import io
import json
import socket
import threading
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import ofbackup_cli
from backend import auth as backend_auth
from backend import constants

ROOT = Path(__file__).resolve().parents[1]


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _post(url: str, payload: dict, origin: str | None = None) -> tuple[int, dict]:
    data = json.dumps(payload).encode("utf-8")
    request = Request(url, data=data, method="POST")
    request.add_header("Content-Type", "application/json")
    if origin is not None:
        request.add_header("Origin", origin)
    try:
        with urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        body = error.read().decode("utf-8")
        return error.code, (json.loads(body) if body else {})


class ReceiverOriginTests(unittest.TestCase):
    def test_sin_cabecera_origin_se_permite(self):
        self.assertTrue(ofbackup_cli.receiver_origin_allowed(None))
        self.assertTrue(ofbackup_cli.receiver_origin_allowed(""))

    def test_extensiones_permitidas(self):
        for origin in (
            "chrome-extension://abcdefghijklmnop",
            "moz-extension://11111111-2222-3333-4444-555555555555",
            "safari-web-extension://ABCDEF",
        ):
            self.assertTrue(ofbackup_cli.receiver_origin_allowed(origin), origin)

    def test_onlyfans_permitido(self):
        self.assertTrue(ofbackup_cli.receiver_origin_allowed("https://onlyfans.com"))
        self.assertTrue(
            ofbackup_cli.receiver_origin_allowed("https://www.onlyfans.com")
        )

    def test_webs_de_terceros_bloqueadas(self):
        for origin in (
            "https://evil.example",
            "http://localhost:3000",
            "https://onlyfans.com.evil.example",
            "https://notonlyfans.com",
            "null",
        ):
            self.assertFalse(ofbackup_cli.receiver_origin_allowed(origin), origin)


class ReceiverEndpointTests(unittest.TestCase):
    """Comprueba el receptor real: rechaza webs ajenas y acepta la extensión."""

    def test_pair_y_upload_con_origen_de_extension(self):
        port = _free_port()
        captured: list[dict] = []
        output = io.StringIO()
        with mock.patch.object(
            ofbackup_cli, "save_credentials", lambda values, username="": captured.append(values)
        ):
            with redirect_stdout(output):
                worker = threading.Thread(
                    target=ofbackup_cli.receive_credentials_locally,
                    kwargs={"port": port, "timeout": 20},
                    daemon=True,
                )
                worker.start()
                try:
                    base = f"http://127.0.0.1:{port}"
                    # Margen amplio para runners de CI lentos (macOS tarda en
                    # arrancar el primer socket).
                    deadline = datetime.now().timestamp() + 15
                    while True:
                        try:
                            urlopen(base + "/discover", timeout=1).read()
                            break
                        except OSError:
                            if datetime.now().timestamp() > deadline:
                                self.fail("El receptor no arrancó a tiempo.")
                            threading.Event().wait(0.05)

                    # Una web cualquiera no puede emparejarse...
                    status, _ = _post(base + "/pair", {}, origin="https://evil.example")
                    self.assertEqual(status, 403)
                    # ...pero la extensión sí.
                    status, body = _post(
                        base + "/pair", {}, origin="chrome-extension://abcdefghijklmnop"
                    )
                    self.assertEqual(status, 200)
                    token = body["token"]

                    # Token incorrecto: rechazado.
                    status, _ = _post(
                        base + "/upload",
                        {"token": "incorrecto", "auth": {}},
                        origin="chrome-extension://abcdefghijklmnop",
                    )
                    self.assertEqual(status, 403)

                    values = {
                        "format": "ofbackup-auth",
                        "version": 1,
                        "created_at": datetime.now(timezone.utc).isoformat(),
                        "auth": {
                            "sess": "sess-de-prueba",
                            "auth_id": "123456",
                            "x-bc": "xbc-de-prueba",
                            "user_agent": "UA/1.0",
                        },
                    }
                    status, _ = _post(
                        base + "/upload",
                        {"token": token, "auth": values},
                        origin="chrome-extension://abcdefghijklmnop",
                    )
                    self.assertEqual(status, 200)
                    self.assertEqual(len(captured), 1)
                    self.assertEqual(captured[0]["auth_id"], "123456")
                finally:
                    worker.join(timeout=25)


class ConstantSourceTests(unittest.TestCase):
    def test_version_y_token_son_unicos(self):
        self.assertEqual(ofbackup_cli.APP_VERSION, constants.APP_VERSION)
        self.assertEqual(ofbackup_cli.DEFAULT_APP_TOKEN, constants.DEFAULT_APP_TOKEN)
        self.assertEqual(
            ofbackup_cli.MAX_AUTH_EXPORT_SIZE, constants.MAX_AUTH_EXPORT_SIZE
        )
        self.assertEqual(backend_auth.AuthService.APP_VERSION, constants.APP_VERSION)

    def test_la_fachada_de_auth_delega(self):
        service = backend_auth.AuthService()
        self.assertEqual(
            service.parse_cookie_header("sess=abc; auth_id=1"),
            ofbackup_cli.parse_cookie_header("sess=abc; auth_id=1"),
        )
        self.assertEqual(service.auth_path, ofbackup_cli.AUTH_PATH)
        self.assertEqual(
            service.default_export_path, ofbackup_cli.EXPORTED_AUTH_PATH
        )
        with mock.patch.object(ofbackup_cli, "test_credentials", return_value=7) as mocked:
            self.assertEqual(service.test_credentials(timeout=3), 7)
            mocked.assert_called_once_with(timeout=3)


class EncodingTests(unittest.TestCase):
    """Evita que vuelvan a colarse textos con doble codificación UTF-8."""

    # backend/web_dashboard.py contiene a propósito los literales corruptos en
    # su tabla de reparación, así que se excluye de esta comprobación.
    FILES = ("ofbackup_cli.py", "web/index.html")

    def test_sin_mojibake_en_los_archivos_de_usuario(self):
        marker = "Ã"
        for relative in self.FILES:
            text = (ROOT / relative).read_text(encoding="utf-8")
            offenders = [
                f"{relative}:{index}"
                for index, line in enumerate(text.splitlines(), start=1)
                if marker in line
            ]
            self.assertEqual(offenders, [], f"Texto mal codificado en {offenders}")

    def test_el_dashboard_normaliza_el_tipo_de_trabajo(self):
        text = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        self.assertNotIn("kind: selectedType,", text)
        self.assertIn("['profile', 'post'].includes(selectedType)", text)


if __name__ == "__main__":
    unittest.main()
