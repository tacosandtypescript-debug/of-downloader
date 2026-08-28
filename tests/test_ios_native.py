import json
import os
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
IOS_ROOT = ROOT / "ios"
sys.path.insert(0, str(IOS_ROOT))

from of_ios.api import (  # noqa: E402
    ApiError,
    OnlyFansApi,
    SigningRules,
    _items_and_more,
    _parse_rules,
    signed_headers,
)
from of_ios.build import prepare_engine  # noqa: E402
from of_ios.cli import build_parser, interactive, main  # noqa: E402
from of_ios.config import ConfigError, import_auth, parse_auth_export  # noqa: E402
from of_ios.media import download_url, iter_direct_media, safe_name  # noqa: E402
from of_ios.selftest import run_selftest  # noqa: E402


class IOSNativeTests(unittest.TestCase):
    def test_prepare_engine_compiles_and_checks_local_storage(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "source"
            app_home = Path(directory) / "app"
            downloads = app_home / "Descargas"
            root.mkdir()
            (root / "module.py").write_text("VALUE = 1\n", encoding="utf-8")
            report = prepare_engine(root, app_home, downloads)
            self.assertTrue(report.ok)
            self.assertTrue((root / "__pycache__").is_dir())
            self.assertFalse((app_home / ".of-ios-write-test").exists())
            self.assertFalse((downloads / ".of-ios-write-test").exists())

    def test_nested_auth_export_is_accepted(self):
        values = parse_auth_export(
            {
                "format": "ofbackup-auth",
                "auth": {
                    "sess": "secret",
                    "auth_id": "123",
                    "x-bc": "xbc",
                    "user_agent": "agent",
                },
            }
        )
        self.assertEqual(values["auth_id"], "123")

    def test_cookie_header_and_field_aliases_are_accepted(self):
        values = parse_auth_export(
            {
                "cookie": "sess=session-value; auth_id=123; x_bc=bc-value",
                "User-Agent": "agent-value",
            }
        )
        self.assertEqual(
            values,
            {
                "sess": "session-value",
                "auth_id": "123",
                "x-bc": "bc-value",
                "user_agent": "agent-value",
            },
        )

    def test_cookie_editor_export_accepts_onlyfans_domains(self):
        values = parse_auth_export(
            [
                {"domain": ".onlyfans.com", "name": "sess", "value": "session-value"},
                {"domain": "api.onlyfans.com", "name": "auth_id", "value": "123"},
                {"domain": "www.onlyfans.com", "name": "x-bc", "value": "bc-value"},
                {
                    "domain": ".example.invalid",
                    "name": "x-bc",
                    "value": "must-not-be-used",
                },
                {"domain": ".onlyfans.com", "name": "User-Agent", "value": "agent-value"},
            ]
        )
        self.assertEqual(values["x-bc"], "bc-value")
        self.assertEqual(values["user_agent"], "agent-value")

    def test_arbitrary_json_filename_can_be_imported(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "3a5e4375-34b6-4d18-b5d7-2975c2976f99.json"
            source.write_text(
                '{"auth": {"sess": "session-value", "auth_id": "123", '
                '"x-bc": "bc-value", "user_agent": "agent-value"}}',
                encoding="utf-8",
            )
            private = root / "private" / "auth.json"
            with mock.patch("of_ios.config.AUTH_PATH", private):
                imported = import_auth(source)
            self.assertEqual(imported, private)
            self.assertEqual(json.loads(private.read_text(encoding="utf-8"))["auth_id"], "123")

    def test_import_without_path_discovers_uuid_json_in_current_folder(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "notes.json").write_text('{"not_auth": true}', encoding="utf-8")
            source = root / "3a5e4375-34b6-4d18-b5d7-2975c2976f99.json"
            source.write_text(
                '{"auth": {"sess": "session-value", "auth_id": "123", '
                '"x-bc": "bc-value", "user_agent": "agent-value"}}',
                encoding="utf-8",
            )
            private = root / "private" / "auth.json"
            with (
                mock.patch("of_ios.config.Path.cwd", return_value=root),
                mock.patch("of_ios.config.Path.home", return_value=root),
                mock.patch("of_ios.config.AUTH_PATH", private),
            ):
                self.assertEqual(import_auth(), private)
            self.assertEqual(json.loads(private.read_text(encoding="utf-8"))["auth_id"], "123")

    def test_import_without_path_refuses_multiple_valid_json_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            payload = (
                '{"auth": {"sess": "session-value", "auth_id": "123", '
                '"x-bc": "bc-value", "user_agent": "agent-value"}}'
            )
            (root / "first.json").write_text(payload, encoding="utf-8")
            (root / "second.json").write_text(payload, encoding="utf-8")
            private = root / "private" / "auth.json"
            with (
                mock.patch("of_ios.config.Path.cwd", return_value=root),
                mock.patch("of_ios.config.Path.home", return_value=root),
                mock.patch("of_ios.config.AUTH_PATH", private),
            ):
                with self.assertRaisesRegex(ConfigError, "Indica la ruta exacta"):
                    import_auth()
            self.assertFalse(private.exists())

    def test_invalid_auth_id_is_rejected(self):
        with self.assertRaises(ConfigError):
            parse_auth_export(
                {"sess": "s", "auth_id": "x", "x-bc": "b", "user_agent": "u"}
            )

    def test_signing_is_deterministic(self):
        rules = SigningRules("static", "{}:{}", (0, 2, 4), -10)
        auth = {
            "sess": "secret",
            "auth_id": "123",
            "x-bc": "xbc",
            "user_agent": "agent",
        }
        headers = signed_headers(
            "https://onlyfans.com/api2/v2/users/me", auth, rules, now_ms=1000
        )
        self.assertEqual(headers["time"], "1000")
        self.assertTrue(headers["sign"])
        self.assertNotIn("secret", headers["sign"])

    def test_signing_uses_dynamic_app_token_when_rules_provide_one(self):
        rules = SigningRules("static", "{}:{}", (0, 2, 4), -10, "dynamic-token")
        auth = {
            "sess": "secret",
            "auth_id": "123",
            "x-bc": "xbc",
            "user_agent": "agent",
        }
        headers = signed_headers(
            "https://onlyfans.com/api2/v2/users/me", auth, rules, now_ms=1000
        )
        self.assertEqual(headers["app-token"], "dynamic-token")

    def test_prefix_suffix_signing_rules_are_supported(self):
        rules = _parse_rules(
            {
                "static_param": "static",
                "prefix": "prefix",
                "suffix": "suffix",
                "checksum_indexes": [0, 1],
                "checksum_constant": 0,
                "app-token": "dynamic-token",
            }
        )
        self.assertEqual(rules.format, "prefix:{}:{:x}:suffix")
        self.assertEqual(rules.app_token, "dynamic-token")

    def test_list_response_shapes_are_normalized(self):
        batch, more = _items_and_more({"data": {"posts": [{"id": 1}], "hasNext": True}})
        self.assertEqual(batch, [{"id": 1}])
        self.assertTrue(more)
        batch, more = _items_and_more([{"id": 2}])
        self.assertEqual(batch, [{"id": 2}])
        self.assertIsNone(more)

    def test_direct_and_drm_media_are_classified(self):
        post = {
            "media": [
                {"id": 1, "files": {"full": {"url": "https://cdn/x.jpg"}}},
                {"id": 2, "files": {"drm": {"manifest": "x"}}},
                {"id": 3, "canView": False},
                {"id": 4, "files": {"full": {"url": "https://cdn/x.m3u8"}}},
                {"id": 5, "source": {"source": "https://cdn/y.mp4"}},
                {"id": 6, "isDrm": True},
            ]
        }
        statuses = [status for _, _, status in iter_direct_media(post)]
        self.assertEqual(
            statuses, ["direct", "drm", "locked", "unsupported", "direct", "drm"]
        )

    def test_safe_name_removes_path_characters(self):
        self.assertEqual(safe_name("../a/b", "x"), "a_b")

    def test_profile_url_rejects_other_hosts_before_network(self):
        api = object.__new__(OnlyFansApi)
        with self.assertRaises(ApiError):
            api.profile("https://example.invalid/person")

    def test_cli_exposes_android_like_commands_without_android_runtime(self):
        parser = build_parser()
        self.assertEqual(parser.parse_args(["importar"]).command, "importar")
        self.assertEqual(parser.parse_args(["probar"]).command, "probar")
        self.assertEqual(parser.parse_args(["perfiles"]).command, "perfiles")
        self.assertEqual(parser.parse_args(["usuario", "creator"]).value, "creator")
        self.assertEqual(
            parser.parse_args(["publicacion", "https://onlyfans.com/creator/42"]).value,
            "https://onlyfans.com/creator/42",
        )
        self.assertEqual(parser.parse_args(["probar-perfil", "creator"]).value, "creator")
        self.assertEqual(parser.parse_args(["compilar"]).command, "compilar")
        self.assertEqual(parser.parse_args(["verificar-ios"]).command, "verificar-ios")

    def test_compile_command_dispatches_to_native_builder(self):
        with mock.patch("of_ios.cli.cmd_build", return_value=0) as builder:
            self.assertEqual(main(["compilar"]), 0)
        builder.assert_called_once_with()

    def test_selftest_command_dispatches_to_local_check(self):
        with mock.patch("of_ios.cli.cmd_selftest", return_value=0) as selftest:
            self.assertEqual(main(["verificar-ios"]), 0)
        selftest.assert_called_once_with()

    def test_selftest_passes_without_auth_for_local_engine(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            app_home = root / "app"
            auth_path = app_home / ".private" / "auth.json"
            with (
                mock.patch("of_ios.selftest.AUTH_PATH", auth_path),
                mock.patch("of_ios.config.AUTH_PATH", auth_path),
            ):
                report = run_selftest(IOS_ROOT, app_home, app_home / "Descargas")
            self.assertTrue(report.ok)
            self.assertTrue(report.compiled_ok)
            self.assertIsNone(report.auth_ok)

    def test_selftest_fails_when_python_compilation_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "source"
            app_home = Path(directory) / "app"
            (root / "of_ios").mkdir(parents=True)
            for path in (
                "of-ios.py",
                "of_ios/__init__.py",
                "of_ios/config.py",
                "of_ios/api.py",
                "of_ios/media.py",
                "of_ios/selftest.py",
            ):
                (root / path).write_text("VALUE = 1\n", encoding="utf-8")
            (root / "of_ios/cli.py").write_text("def broken(:\n", encoding="utf-8")
            auth_path = app_home / ".private" / "auth.json"
            with (
                mock.patch("of_ios.selftest.AUTH_PATH", auth_path),
                mock.patch("of_ios.config.AUTH_PATH", auth_path),
            ):
                report = run_selftest(root, app_home, app_home / "Descargas")
            self.assertFalse(report.ok)
            self.assertFalse(report.compiled_ok)

    def test_direct_onlyfans_url_keeps_original_shortcut(self):
        with mock.patch("of_ios.cli.cmd_publication", return_value=0) as publication:
            self.assertEqual(main(["https://onlyfans.com/creator/42"]), 0)
        publication.assert_called_once_with("https://onlyfans.com/creator/42")

    def test_profiles_command_keeps_selection_download_flow(self):
        with mock.patch("of_ios.cli.cmd_choose_profile", return_value=0) as chooser:
            self.assertEqual(main(["perfiles"]), 0)
        chooser.assert_called_once_with()

    def test_interactive_menu_returns_to_menu_after_an_action(self):
        with mock.patch(
            "of_ios.cli._prompt", side_effect=["7", "", "0"]
        ), mock.patch("of_ios.cli.cmd_build", return_value=0) as builder:
            self.assertEqual(interactive(), 0)
        builder.assert_called_once_with()

    def test_post_id_extraction_accepts_onlyfans_url(self):
        self.assertEqual(
            OnlyFansApi.extract_post_id("https://onlyfans.com/creator/42"), "42"
        )
        with self.assertRaises(ApiError):
            OnlyFansApi.extract_post_id("https://example.invalid/creator/42")

    def test_download_writes_atomic_file_and_reuses_existing(self):
        payload = b"native-ios-test-media"

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                self.send_response(200)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *_args):
                return

        server = HTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as directory:
                target = Path(directory) / "media.bin"
                url = f"http://127.0.0.1:{server.server_port}/media.bin"
                self.assertTrue(download_url(url, target, "test-agent", ""))
                self.assertEqual(target.read_bytes(), payload)
                self.assertFalse(target.with_suffix(".bin.part").exists())
                self.assertFalse(download_url(url, target, "test-agent", ""))
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
