import tempfile
import unittest
import json
import io
from unittest import mock
from pathlib import Path

import ofbackup_cli


class CookieTests(unittest.TestCase):
    def test_extracts_required_values(self):
        result = ofbackup_cli.parse_cookie_header(
            "Cookie: sess=abc123; auth_id=456; other=value"
        )
        self.assertEqual(result["sess"], "abc123")
        self.assertEqual(result["auth_id"], "456")

    def test_fallback_parser_keeps_equals_inside_value(self):
        result = ofbackup_cli.parse_cookie_header("sess=a=b=c; auth_id=42")
        self.assertEqual(result["sess"], "a=b=c")

    def test_extracts_required_values_from_exported_json(self):
        exported = json.dumps(
            [
                {"domain": "onlyfans.com", "name": "sess", "value": "fake-session"},
                {"domain": ".onlyfans.com", "name": "auth_id", "value": "12345"},
                {"domain": ".onlyfans.com", "name": "csrf", "value": "discard-me"},
            ]
        )
        result = ofbackup_cli.parse_cookie_header(exported)
        self.assertEqual(result, {"sess": "fake-session", "auth_id": "12345"})

    def test_ignores_cookies_from_other_domains(self):
        exported = json.dumps(
            [{"domain": "example.com", "name": "sess", "value": "not-allowed"}]
        )
        self.assertEqual(ofbackup_cli.parse_cookie_header(exported), {})

    def test_extracts_complete_cookie_helper_json(self):
        exported = json.dumps(
            {
                "auth": {
                    "cookie": "sess=session-value; auth_id=42",
                    "x-bc": "xbc-value",
                    "user_agent": "Exact Browser Agent",
                }
            }
        )
        self.assertEqual(
            ofbackup_cli.parse_cookie_header(exported),
            {
                "sess": "session-value",
                "auth_id": "42",
                "x-bc": "xbc-value",
                "user_agent": "Exact Browser Agent",
            },
        )


class UrlTests(unittest.TestCase):
    def test_accepts_onlyfans_url(self):
        value = "https://onlyfans.com/123456/user"
        self.assertEqual(ofbackup_cli.normalize_url(value), value)

    def test_accepts_numeric_post_id(self):
        self.assertEqual(ofbackup_cli.normalize_url("123456"), "123456")

    def test_rejects_other_domains(self):
        with self.assertRaises(ofbackup_cli.UserError):
            ofbackup_cli.normalize_url("https://example.com/file")


class JsonTests(unittest.TestCase):
    def test_secure_json_round_trip(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "private" / "settings.json"
            ofbackup_cli.secure_write_json(path, {"ok": True})
            self.assertEqual(ofbackup_cli.read_json(path), {"ok": True})

    def test_config_includes_discord_workaround(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config_path = root / "ofscraper" / "config.json"
            state = {"download_dir": str(root / "downloads")}
            with mock.patch.object(ofbackup_cli, "OFSCRAPER_CONFIG_PATH", config_path):
                ofbackup_cli.write_ofscraper_config(state)
            config = ofbackup_cli.read_json(config_path)
            self.assertEqual(config["discord"], "")
            self.assertEqual(
                config["file_options"]["save_location"], str(root / "downloads")
            )


class AuthImportTests(unittest.TestCase):
    def export_data(self):
        return {
            "format": "ofbackup-auth",
            "version": 1,
            "created_at": "2026-07-17T12:00:00.000Z",
            "auth": {
                "sess": "fake-session",
                "auth_id": "12345",
                "x-bc": "fake-xbc",
                "user_agent": "Firefox Android Test",
                "ignored": "discard-me",
            },
            "ignored": "discard-me",
        }

    def test_parses_versioned_export_and_discards_unknown_fields(self):
        self.assertEqual(
            ofbackup_cli.parse_auth_export(self.export_data()),
            {
                "sess": "fake-session",
                "auth_id": "12345",
                "x-bc": "fake-xbc",
                "user_agent": "Firefox Android Test",
            },
        )

    def test_rejects_wrong_format_and_non_numeric_auth_id(self):
        data = self.export_data()
        data["format"] = "something-else"
        with self.assertRaises(ofbackup_cli.UserError):
            ofbackup_cli.parse_auth_export(data)

        data = self.export_data()
        data["created_at"] = "not-a-date"
        with self.assertRaises(ofbackup_cli.UserError):
            ofbackup_cli.parse_auth_export(data)

        data = self.export_data()
        data["auth"]["auth_id"] = "not-a-number"
        with self.assertRaises(ofbackup_cli.UserError):
            ofbackup_cli.parse_auth_export(data)

    def test_rejects_oversized_file_without_replacing_credentials(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "large.json"
            path.write_bytes(b"x" * (ofbackup_cli.MAX_AUTH_EXPORT_SIZE + 1))
            with mock.patch.object(ofbackup_cli, "save_credentials") as save:
                with self.assertRaises(ofbackup_cli.UserError):
                    ofbackup_cli.import_credentials_file(path)
            save.assert_not_called()

    def test_import_removes_matching_download_export(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            selected = root / "selected.json"
            original = root / "OFBackup-auth.json"
            raw = json.dumps(self.export_data()).encode()
            selected.write_bytes(raw)
            original.write_bytes(raw)
            with (
                mock.patch.object(ofbackup_cli, "EXPORTED_AUTH_PATH", original),
                mock.patch.object(ofbackup_cli, "save_credentials") as save,
                mock.patch("builtins.print"),
            ):
                ofbackup_cli.import_credentials_file(selected)
            save.assert_called_once()
            self.assertFalse(original.exists())

    def test_import_preserves_different_download_export(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            selected = root / "selected.json"
            original = root / "OFBackup-auth.json"
            selected.write_text(json.dumps(self.export_data()), encoding="utf-8")
            other = self.export_data()
            other["auth"]["sess"] = "other-session"
            original.write_text(json.dumps(other), encoding="utf-8")
            with (
                mock.patch.object(ofbackup_cli, "EXPORTED_AUTH_PATH", original),
                mock.patch.object(ofbackup_cli, "save_credentials"),
                mock.patch("builtins.print"),
            ):
                ofbackup_cli.import_credentials_file(selected)
            self.assertTrue(original.exists())

    def test_configure_requests_android_picker(self):
        with mock.patch("builtins.input", return_value="1"):
            self.assertEqual(
                ofbackup_cli.configure_credentials(),
                ofbackup_cli.IMPORT_REQUEST_EXIT,
            )


class ExecutableTests(unittest.TestCase):
    def test_finds_ofscraper_next_to_virtualenv_python(self):
        with tempfile.TemporaryDirectory() as temporary:
            scripts = Path(temporary)
            python = scripts / "python"
            ofscraper = scripts / "ofscraper"
            python.touch()
            ofscraper.touch()
            with (
                mock.patch.object(ofbackup_cli.sys, "executable", str(python)),
                mock.patch.object(ofbackup_cli.shutil, "which", return_value=None),
                mock.patch.dict(ofbackup_cli.os.environ, {}, clear=True),
            ):
                self.assertEqual(ofbackup_cli.find_ofscraper_binary(), str(ofscraper))


class DownloadTests(unittest.TestCase):
    def test_traceback_is_failure_even_with_zero_exit_code(self):
        process = mock.Mock()
        process.stdout = io.StringIO(
            "Traceback (most recent call last):\nTypeError: example\n"
        )
        process.wait.return_value = 0
        with (
            mock.patch.object(ofbackup_cli, "require_credentials"),
            mock.patch.object(ofbackup_cli, "write_ofscraper_config"),
            mock.patch.object(ofbackup_cli, "ofscraper_binary", return_value="ofscraper"),
            mock.patch.object(
                ofbackup_cli.subprocess, "Popen", return_value=process
            ) as popen,
            mock.patch("builtins.print"),
        ):
            self.assertEqual(ofbackup_cli.run_ofscraper(["manual"]), 1)
        popen.assert_called_once_with(
            ["ofscraper", "manual", "--auth-fail"],
            stdout=ofbackup_cli.subprocess.PIPE,
            stderr=ofbackup_cli.subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )

    def test_auth_failure_is_detected_without_opening_internal_menu(self):
        process = mock.Mock()
        process.stdout = io.StringIO("Auth Failed\nauth failed quitting on error\n")
        process.wait.return_value = 0
        with (
            mock.patch.object(ofbackup_cli, "require_credentials"),
            mock.patch.object(ofbackup_cli, "write_ofscraper_config"),
            mock.patch.object(ofbackup_cli, "ofscraper_binary", return_value="ofscraper"),
            mock.patch.object(ofbackup_cli.subprocess, "Popen", return_value=process),
            mock.patch("builtins.print"),
        ):
            self.assertEqual(ofbackup_cli.run_ofscraper(["manual"]), 1)

    def test_auth_fail_option_precedes_root_arguments(self):
        self.assertEqual(
            ofbackup_cli.build_ofscraper_command(
                "ofscraper", ["--username", "example"]
            ),
            ["ofscraper", "--auth-fail", "--username", "example"],
        )


if __name__ == "__main__":
    unittest.main()
