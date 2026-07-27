import io
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import ofbackup_cli
from backend import web_dashboard


class DashboardAvailabilityTests(unittest.TestCase):
    def test_dashboard_is_hidden_in_termux(self):
        with mock.patch.dict(ofbackup_cli.os.environ, {"OFDOWNLOADER_PLATFORM": "TERMUX"}, clear=True):
            self.assertFalse(ofbackup_cli.desktop_dashboard_available())

    def test_dashboard_is_available_on_linux_pc(self):
        with mock.patch.dict(ofbackup_cli.os.environ, {"OFDOWNLOADER_PLATFORM": "LINUX"}, clear=True):
            self.assertTrue(ofbackup_cli.desktop_dashboard_available())

    def test_web_download_bypasses_profile_confirmation(self):
        with mock.patch.object(ofbackup_cli, "download_user", return_value=0) as download:
            self.assertEqual(ofbackup_cli.download_web_target("@demo_user"), 0)
        download.assert_called_once_with("demo_user", source="selector")

    def test_menu_shows_dashboard_only_on_pc(self):
        def render(platform):
            output = io.StringIO()
            with (
                mock.patch.dict(ofbackup_cli.os.environ, {"OFDOWNLOADER_PLATFORM": platform}, clear=True),
                mock.patch.object(ofbackup_cli.sys, "stdout", output),
                mock.patch.object(ofbackup_cli, "credentials_ready", return_value=False),
                mock.patch.object(ofbackup_cli, "get_state", return_value={"download_dir": "downloads"}),
                mock.patch("builtins.input", return_value="0"),
            ):
                ofbackup_cli.menu()
            return output.getvalue()

        self.assertIn("[13] Abrir dashboard", render("LINUX"))
        self.assertNotIn("[13] Abrir dashboard", render("TERMUX"))


class DashboardServerTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parents[1]
        self.app = web_dashboard.DashboardApplication(self.root, "test-token")
        self.server = web_dashboard._available_server(self.app, 0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def test_index_injects_session_token(self):
        text = urlopen(self.url + "/", timeout=3).read().decode("utf-8")
        self.assertIn("test-token", text)
        self.assertNotIn("__OFD_TOKEN__", text)

    def test_api_rejects_missing_token(self):
        with self.assertRaises(HTTPError) as caught:
            urlopen(self.url + "/api/status", timeout=3)
        self.assertEqual(caught.exception.code, 403)

    def test_status_never_contains_saved_cookie_values(self):
        request = Request(self.url + "/api/status", headers={"X-OFD-Token": "test-token"})
        data = json.loads(urlopen(request, timeout=3).read())
        serialized = json.dumps(data)
        self.assertNotIn('"sess"', serialized)
        self.assertNotIn('"x-bc"', serialized)

    def test_dashboard_parses_live_file_queue_counters(self):
        job = web_dashboard.DashboardJob(id="1", target="demo", kind="profile")
        web_dashboard.update_dashboard_job_from_line(
            job,
            "[########] 45% Fotos 12/30 · Videos 4/19 · Omitidos 2 · "
            "Velocidad 2.4/s · ETA 00:25 · C:\\downloads\\foto-12.jpg",
        )
        self.assertEqual(job.current_file, "C:\\downloads\\foto-12.jpg")
        self.assertEqual((job.processed_images, job.detected_images), (12, 30))
        self.assertEqual((job.processed_videos, job.detected_videos), (4, 19))
        self.assertEqual(job.skipped, 2)
        self.assertEqual(job.speed, "2.4/s")
        self.assertEqual(job.eta, "00:25")

    def test_public_job_does_not_copy_process_controller_locks(self):
        job = web_dashboard.DashboardJob(id="1", target="demo", kind="profile")
        job.controller = mock.Mock(lock=threading.Lock())
        public = web_dashboard._public_job(job)
        self.assertEqual(public["id"], "1")
        self.assertNotIn("controller", public)


class DashboardAuthImportTests(unittest.TestCase):
    def test_import_saves_only_supported_auth_fields(self):
        export = {
            "format": "ofbackup-auth",
            "version": 1,
            "created_at": "2026-07-27T00:00:00Z",
            "auth": {
                "sess": "fake-session",
                "auth_id": "12345",
                "x-bc": "fake-xbc",
                "user_agent": "Test Browser",
                "ignored": "secret-extra",
            },
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            auth_path = root / "ofscraper" / "main_profile" / "auth.json"
            state_path = root / "settings.json"
            config_path = root / "ofscraper" / "config.json"
            app = web_dashboard.DashboardApplication(Path(__file__).resolve().parents[1], "token")
            with (
                mock.patch.object(ofbackup_cli, "AUTH_PATH", auth_path),
                mock.patch.object(ofbackup_cli, "STATE_PATH", state_path),
                mock.patch.object(ofbackup_cli, "OFSCRAPER_CONFIG_PATH", config_path),
            ):
                result = app.import_auth({"filename": "OFBackup-auth.json", "content": json.dumps(export)})
            saved = json.loads(auth_path.read_text(encoding="utf-8"))
        self.assertTrue(result["connected"])
        self.assertEqual(saved["sess"], "fake-session")
        self.assertEqual(saved["auth_id"], "12345")
        self.assertNotIn("ignored", saved)
        self.assertNotIn("secret-extra", json.dumps(result))


if __name__ == "__main__":
    unittest.main()
