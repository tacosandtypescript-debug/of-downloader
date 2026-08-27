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

from of_ios.api import ApiError, OnlyFansApi, SigningRules, signed_headers  # noqa: E402
from of_ios.cli import build_parser, main  # noqa: E402
from of_ios.config import ConfigError, parse_auth_export  # noqa: E402
from of_ios.media import download_url, iter_direct_media, safe_name  # noqa: E402


class IOSNativeTests(unittest.TestCase):
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

    def test_direct_and_drm_media_are_classified(self):
        post = {
            "media": [
                {"id": 1, "files": {"full": {"url": "https://cdn/x.jpg"}}},
                {"id": 2, "files": {"drm": {"manifest": "x"}}},
                {"id": 3, "canView": False},
                {"id": 4, "files": {"full": {"url": "https://cdn/x.m3u8"}}},
            ]
        }
        statuses = [status for _, _, status in iter_direct_media(post)]
        self.assertEqual(statuses, ["direct", "drm", "locked", "unsupported"])

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

    def test_direct_onlyfans_url_keeps_original_shortcut(self):
        with mock.patch("of_ios.cli.cmd_publication", return_value=0) as publication:
            self.assertEqual(main(["https://onlyfans.com/creator/42"]), 0)
        publication.assert_called_once_with("https://onlyfans.com/creator/42")

    def test_profiles_command_keeps_selection_download_flow(self):
        with mock.patch("of_ios.cli.cmd_choose_profile", return_value=0) as chooser:
            self.assertEqual(main(["perfiles"]), 0)
        chooser.assert_called_once_with()

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
