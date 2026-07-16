import tempfile
import unittest
import json
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


if __name__ == "__main__":
    unittest.main()
