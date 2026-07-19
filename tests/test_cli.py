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

    def test_extracts_username_from_profile_media_url(self):
        self.assertEqual(
            ofbackup_cli.profile_username(
                "https://onlyfans.com/luceroguevara.oficial/media"
            ),
            "luceroguevara.oficial",
        )

    def test_extracts_username_from_markdown_link(self):
        self.assertEqual(
            ofbackup_cli.profile_username(
                "[perfil](https://onlyfans.com/luceroguevara.oficial)"
            ),
            "luceroguevara.oficial",
        )

    def test_extracts_username_from_embedded_text(self):
        self.assertEqual(
            ofbackup_cli.profile_username(
                "Usuario o enlace: https://onlyfans.com/luceroguevara.oficial"
            ),
            "luceroguevara.oficial",
        )

    def test_post_url_is_not_mistaken_for_profile(self):
        self.assertIsNone(
            ofbackup_cli.profile_username("https://onlyfans.com/123456/user")
        )

    def test_profile_url_is_routed_to_complete_user_download(self):
        with (
            mock.patch.object(
                ofbackup_cli, "download_user", return_value=0
            ) as download_user,
            mock.patch("builtins.print"),
        ):
            self.assertEqual(
                ofbackup_cli.download_link(
                    "https://onlyfans.com/luceroguevara.oficial/media"
                ),
                0,
            )
        download_user.assert_called_once_with("luceroguevara.oficial", source="enlace")


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


class ThemeTests(unittest.TestCase):
    def test_ascii_logo_fits_the_termux_header(self):
        self.assertEqual(len(ofbackup_cli.MENU_LOGO_LINES), 4)
        self.assertTrue(all(len(line) <= 44 for line in ofbackup_cli.MENU_LOGO_LINES))
        self.assertTrue(any("⣿" in line for line in ofbackup_cli.MENU_LOGO_LINES))

    def test_logo_is_composed_on_the_right_without_a_rigid_border(self):
        output = io.StringIO()
        with mock.patch.object(ofbackup_cli.sys, "stdout", output):
            ofbackup_cli.menu_brand_line("OF DOWNLOADER", ofbackup_cli.MENU_LOGO_LINES[0])
        rendered = output.getvalue().rstrip("\n")
        self.assertLessEqual(len(rendered), 30)
        self.assertLess(rendered.index("OF DOWNLOADER"), rendered.index("⣠"))

    def test_plain_text_is_kept_when_colors_are_not_supported(self):
        output = io.StringIO()
        with mock.patch.object(ofbackup_cli.sys, "stdout", output):
            self.assertEqual(ofbackup_cli.styled("OF Downloader", "cyan"), "OF Downloader")

    def test_color_theme_uses_truecolor_when_available(self):
        output = mock.Mock()
        output.isatty.return_value = True
        with (
            mock.patch.object(ofbackup_cli.sys, "stdout", output),
            mock.patch.object(ofbackup_cli.os, "name", "posix"),
            mock.patch.dict(ofbackup_cli.os.environ, {}, clear=True),
        ):
            value = ofbackup_cli.styled("OF Downloader", "cyan", bold=True)
        self.assertIn("38;2;0;175;240", value)

    def test_windows_classic_powershell_disables_ansi(self):
        output = mock.Mock()
        output.isatty.return_value = True
        with (
            mock.patch.object(ofbackup_cli.sys, "stdout", output),
            mock.patch.object(ofbackup_cli.os, "name", "nt"),
            mock.patch.dict(ofbackup_cli.os.environ, {}, clear=True),
        ):
            self.assertEqual(ofbackup_cli.styled("OF Downloader", "cyan"), "OF Downloader")

    def test_windows_terminal_enables_ansi(self):
        output = mock.Mock()
        output.isatty.return_value = True
        with (
            mock.patch.object(ofbackup_cli.sys, "stdout", output),
            mock.patch.object(ofbackup_cli.os, "name", "nt"),
            mock.patch.dict(ofbackup_cli.os.environ, {"WT_SESSION": "1"}, clear=True),
        ):
            value = ofbackup_cli.styled("OF Downloader", "cyan", bold=True)
        self.assertIn("38;2;0;175;240", value)

    def test_repository_update_badges_have_clear_states(self):
        output = io.StringIO()
        with mock.patch.object(ofbackup_cli.sys, "stdout", output):
            self.assertIn("DISPONIBLE", ofbackup_cli.repository_update_badge("available"))
            self.assertIn("AL DÍA", ofbackup_cli.repository_update_badge("current"))

    def test_update_command_requests_wrapper_restart(self):
        self.assertEqual(
            ofbackup_cli.main(["actualizar-app"]),
            ofbackup_cli.APP_UPDATE_REQUEST_EXIT,
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

    def test_parses_cookie_helper_json_when_selected_by_file_picker(self):
        data = {
            "auth": {
                "cookie": "sess=fallback-session; auth_id=12345",
                "x-bc": "fallback-xbc",
                "user_agent": "Firefox Android Test",
            }
        }
        self.assertEqual(
            ofbackup_cli.parse_auth_export(data),
            {
                "sess": "fallback-session",
                "auth_id": "12345",
                "x-bc": "fallback-xbc",
                "user_agent": "Firefox Android Test",
            },
        )

    def test_cookie_export_without_xbc_explains_missing_fields(self):
        data = [
            {"domain": "onlyfans.com", "name": "sess", "value": "fake-session"},
            {"domain": "onlyfans.com", "name": "auth_id", "value": "12345"},
        ]
        with self.assertRaisesRegex(ofbackup_cli.UserError, "x-bc"):
            ofbackup_cli.parse_auth_export(data)

    def test_rejects_wrong_format_and_non_numeric_auth_id(self):
        data = self.export_data()
        data["format"] = "something-else"
        self.assertEqual(
            ofbackup_cli.parse_auth_export(data)["sess"],
            "fake-session",
        )

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

    def test_default_auth_export_path_uses_windows_downloads(self):
        with (
            mock.patch.object(ofbackup_cli.os, "name", "nt"),
            mock.patch.object(ofbackup_cli, "HOME", Path("C:/Users/Test")),
            mock.patch.dict(ofbackup_cli.os.environ, {}, clear=True),
        ):
            self.assertEqual(
                ofbackup_cli.default_auth_export_path(),
                Path("C:/Users/Test") / "Downloads" / ofbackup_cli.AUTH_EXPORT_FILENAME,
            )

    def test_import_command_accepts_direct_path_on_windows(self):
        with (
            mock.patch.dict(ofbackup_cli.os.environ, {"OFDOWNLOADER_PLATFORM": "WINDOWS"}),
            mock.patch.object(ofbackup_cli, "import_credentials_file") as importer,
        ):
            self.assertEqual(ofbackup_cli.main(["importar", "C:/Temp/OFBackup-auth.json"]), 0)
        importer.assert_called_once_with(Path("C:/Temp/OFBackup-auth.json"))

    def test_import_command_uses_default_downloads_file_on_windows(self):
        with tempfile.TemporaryDirectory() as temporary:
            default = Path(temporary) / "Downloads" / "OFBackup-auth.json"
            default.parent.mkdir()
            default.write_text("{}", encoding="utf-8")
            with (
                mock.patch.dict(
                    ofbackup_cli.os.environ,
                    {"OFDOWNLOADER_PLATFORM": "WINDOWS"},
                ),
                mock.patch.object(
                    ofbackup_cli,
                    "default_auth_export_path",
                    return_value=default,
                ),
                mock.patch.object(ofbackup_cli, "select_auth_export_file", return_value=None),
                mock.patch.object(ofbackup_cli, "import_credentials_file") as importer,
            ):
                self.assertEqual(ofbackup_cli.main(["importar"]), 0)
        importer.assert_called_once_with(default)

    def test_import_command_uses_selected_file_when_explorer_returns_path(self):
        with tempfile.TemporaryDirectory() as temporary:
            selected = Path(temporary) / "selected-auth.json"
            selected.write_text("{}", encoding="utf-8")
            with (
                mock.patch.dict(
                    ofbackup_cli.os.environ,
                    {"OFDOWNLOADER_PLATFORM": "WINDOWS"},
                ),
                mock.patch.object(
                    ofbackup_cli,
                    "select_auth_export_file",
                    return_value=selected,
                ),
                mock.patch.object(ofbackup_cli, "import_credentials_file") as importer,
            ):
                self.assertEqual(ofbackup_cli.main(["importar"]), 0)
        importer.assert_called_once_with(selected)

    def test_import_command_prompts_for_path_when_default_is_missing_on_windows(self):
        with tempfile.TemporaryDirectory() as temporary:
            selected = Path(temporary) / "custom-auth.json"
            selected.write_text("{}", encoding="utf-8")
            missing = Path(temporary) / "Downloads" / "OFBackup-auth.json"
            with (
                mock.patch.dict(
                    ofbackup_cli.os.environ,
                    {"OFDOWNLOADER_PLATFORM": "WINDOWS"},
                ),
                mock.patch.object(
                    ofbackup_cli,
                    "default_auth_export_path",
                    return_value=missing,
                ),
                mock.patch.object(ofbackup_cli, "select_auth_export_file", return_value=None),
                mock.patch.object(ofbackup_cli, "import_credentials_file") as importer,
                mock.patch("builtins.input", return_value=f'"{selected}"'),
                mock.patch("builtins.print"),
            ):
                self.assertEqual(ofbackup_cli.main(["importar"]), 0)
        importer.assert_called_once_with(selected)

    def test_configure_prompts_for_path_when_default_is_missing_on_windows(self):
        with tempfile.TemporaryDirectory() as temporary:
            selected = Path(temporary) / "custom-auth.json"
            selected.write_text("{}", encoding="utf-8")
            missing = Path(temporary) / "Downloads" / "OFBackup-auth.json"
            with (
                mock.patch.dict(
                    ofbackup_cli.os.environ,
                    {"OFDOWNLOADER_PLATFORM": "WINDOWS"},
                ),
                mock.patch.object(
                    ofbackup_cli,
                    "default_auth_export_path",
                    return_value=missing,
                ),
                mock.patch.object(ofbackup_cli, "select_auth_export_file", return_value=None),
                mock.patch.object(ofbackup_cli, "import_credentials_file") as importer,
                mock.patch("builtins.input", return_value=str(selected)),
                mock.patch("builtins.print"),
            ):
                self.assertEqual(ofbackup_cli.configure_credentials(), 0)
        importer.assert_called_once_with(selected)


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


class AuthenticationTestTests(unittest.TestCase):
    def run_test_with(self, process):
        process.poll.return_value = process.returncode
        process.communicate.return_value = (process.stdout, process.stderr)
        with (
            mock.patch.object(ofbackup_cli, "credentials_ready", return_value=True),
            mock.patch.object(ofbackup_cli, "write_ofscraper_config") as write_config,
            mock.patch.object(
                ofbackup_cli, "ofscraper_binary", return_value="ofscraper"
            ),
            mock.patch.object(
                ofbackup_cli.subprocess, "Popen", return_value=process
            ) as popen,
            mock.patch("builtins.print"),
        ):
            result = ofbackup_cli.test_credentials()
        write_config.assert_called_once_with()
        popen.assert_called_once_with(
            [ofbackup_cli.sys.executable, "-c", ofbackup_cli.AUTH_TEST_SCRIPT],
            stdout=ofbackup_cli.subprocess.PIPE,
            stderr=ofbackup_cli.subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        return result

    def test_valid_cookie_returns_success(self):
        completed = mock.Mock(
            returncode=0, stdout="OFBACKUP_AUTH_OK\n", stderr=""
        )
        self.assertEqual(self.run_test_with(completed), 0)

    def test_rejected_cookie_returns_failure(self):
        completed = mock.Mock(
            returncode=3, stdout="OFBACKUP_AUTH_REJECTED\n", stderr=""
        )
        self.assertEqual(self.run_test_with(completed), 1)

    def test_timeout_returns_failure(self):
        process = mock.Mock()
        process.poll.return_value = None
        process.communicate.side_effect = [
            ("", ""),
        ]
        with (
            mock.patch.object(ofbackup_cli, "credentials_ready", return_value=True),
            mock.patch.object(ofbackup_cli, "write_ofscraper_config"),
            mock.patch.object(
                ofbackup_cli, "ofscraper_binary", return_value="ofscraper"
            ),
            mock.patch.object(
                ofbackup_cli.subprocess,
                "Popen",
                return_value=process,
            ),
            mock.patch.object(ofbackup_cli.time, "monotonic", side_effect=[0, 61, 61]),
            mock.patch("builtins.print"),
        ):
            self.assertEqual(ofbackup_cli.test_credentials(), 1)
        process.terminate.assert_called_once_with()

    def test_missing_credentials_requests_android_picker(self):
        with (
            mock.patch.object(ofbackup_cli, "credentials_ready", return_value=False),
            mock.patch("builtins.print"),
        ):
            self.assertEqual(
                ofbackup_cli.test_credentials(), ofbackup_cli.IMPORT_REQUEST_EXIT
            )


class DownloadTests(unittest.TestCase):
    def test_cdm_startup_check_has_a_short_timeout(self):
        with mock.patch.dict(ofbackup_cli.os.environ, {}, clear=True):
            environment = ofbackup_cli.ofscraper_environment()
        self.assertEqual(environment["OFSC_CDM_TEST_TIMEOUT"], "8")
        self.assertEqual(environment["OFSC_CDM_TEST_NUM_TRIES"], "1")
        self.assertEqual(environment["PYTHONIOENCODING"], "utf-8")

    def test_ofscraper_environment_adds_ffmpeg_dir_when_found(self):
        ffmpeg = Path("C:/Tools/ffmpeg/bin/ffmpeg.exe")
        with (
            mock.patch.dict(ofbackup_cli.os.environ, {"PATH": "C:/Old"}, clear=True),
            mock.patch.object(ofbackup_cli, "find_ffmpeg_binary", return_value=str(ffmpeg)),
        ):
            environment = ofbackup_cli.ofscraper_environment()
        self.assertTrue(environment["PATH"].startswith(str(ffmpeg.parent)))
        self.assertEqual(environment["FFMPEG_BIN"], str(ffmpeg))

    def test_extracts_real_download_percentage(self):
        self.assertEqual(ofbackup_cli.extract_download_percent("Video 73.8%"), 73)
        self.assertIsNone(ofbackup_cli.extract_download_percent("sin porcentaje"))

    def test_extracts_media_totals_from_output(self):
        self.assertEqual(
            ofbackup_cli.extract_media_totals("Images: 27 Videos: 16"),
            (27, 16),
        )
        self.assertEqual(
            ofbackup_cli.extract_media_totals("Se encontraron 9 fotos y 2 videos"),
            (9, 2),
        )

    def test_counts_new_media_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            existing = root / "old.jpg"
            existing.write_bytes(b"old")
            before = ofbackup_cli.media_snapshot(root)
            (root / "new.mp4").write_bytes(b"video")
            (root / "new.webp").write_bytes(b"image")
            (root / "ignored.part").write_bytes(b"partial")
            counts = ofbackup_cli.count_changed_media(
                before, ofbackup_cli.media_snapshot(root)
            )
        self.assertEqual(counts.images, 1)
        self.assertEqual(counts.videos, 1)
        self.assertEqual(counts.other, 0)

    def test_download_user_does_not_force_normal_only(self):
        with (
            tempfile.TemporaryDirectory() as temporary,
            mock.patch.object(
                ofbackup_cli,
                "get_state",
                return_value={"download_dir": temporary, "username": ""},
            ),
            mock.patch.object(ofbackup_cli, "save_state"),
            mock.patch.object(ofbackup_cli, "run_ofscraper", return_value=0) as run,
            mock.patch("builtins.print"),
        ):
            self.assertEqual(ofbackup_cli.download_user("creator.example"), 0)
        arguments = run.call_args.args[0]
        keyword_arguments = run.call_args.kwargs
        self.assertNotIn("--normal-only", arguments)
        self.assertIn("--no-cache", arguments)
        self.assertIn("--no-api-cache", arguments)
        self.assertIn("--update-profile", arguments)
        self.assertIn("--force-all", arguments)
        self.assertIn("--posts", arguments)
        self.assertIn("all", arguments)
        self.assertIn("--download-area", arguments)
        self.assertIn(
            "Timeline,Archived,Pinned,Stories,Streams,Profile,Purchased", arguments
        )
        self.assertEqual(keyword_arguments["mode"], "perfil")


class SubscriptionProfileTests(unittest.TestCase):
    def test_profile_detection_script_compiles(self):
        compile(ofbackup_cli.PROFILE_TEST_SCRIPT, "<profile-test-script>", "exec")

    def test_parse_profile_detection_keeps_deep_count_fields(self):
        detection = ofbackup_cli.parse_profile_detection(
            "OFDOWNLOADER_PROFILE_OK username=creator.example id=123 "
            "posts=9 photos=7 videos=2 archived=1 counted=9 partial=1\n"
        )
        self.assertIsNotNone(detection)
        self.assertEqual(detection.counted, 9)
        self.assertTrue(detection.partial)

    def test_parses_subscription_profiles_from_ofscraper_output(self):
        payload = json.dumps(
            [
                {
                    "id": 123,
                    "username": "creator.free",
                    "displayName": "Creator Free",
                    "isFree": True,
                    "postsCount": 7,
                    "photosCount": 5,
                    "videosCount": 2,
                },
                {"username": "creator.free", "id": 123},
                {
                    "id": 456,
                    "username": "creator.paid",
                    "subscribePrice": 10,
                    "postsCount": "9",
                },
            ]
        )
        profiles = ofbackup_cli.parse_subscriptions_stdout(
            "ruido\n"
            f"{ofbackup_cli.SUBSCRIPTIONS_SENTINEL}{payload}\n"
        )
        self.assertEqual([profile.username for profile in profiles], ["creator.free", "creator.paid"])
        self.assertEqual(profiles[0].status, "gratis")
        self.assertEqual(profiles[0].photos, 5)
        self.assertEqual(profiles[1].status, "pagado")

    def test_parses_subscription_profiles_with_unicode_display_names(self):
        payload = json.dumps(
            [
                {
                    "id": 777,
                    "username": "creator.unicode",
                    "displayName": "Creadora 💙 ñ",
                    "isFree": True,
                }
            ],
            ensure_ascii=False,
        )
        profiles = ofbackup_cli.parse_subscriptions_stdout(
            f"{ofbackup_cli.SUBSCRIPTIONS_SENTINEL}{payload}\n"
        )
        self.assertEqual(profiles[0].username, "creator.unicode")
        self.assertEqual(profiles[0].display_name, "Creadora 💙 ñ")

    def test_choose_profile_can_cancel_after_detection(self):
        profile = ofbackup_cli.SubscriptionProfile(username="creator.free")
        with (
            mock.patch.object(ofbackup_cli, "list_subscription_profiles", return_value=[profile]),
            mock.patch.object(
                ofbackup_cli,
                "detect_profile_counts",
                return_value=ofbackup_cli.ProfileDetection(
                    username="creator.free", posts=7, photos=5, videos=2
                ),
            ),
            mock.patch.object(ofbackup_cli, "download_user", return_value=0) as download,
            mock.patch("builtins.input", side_effect=["1", "n"]),
            mock.patch("builtins.print"),
        ):
            self.assertEqual(ofbackup_cli.choose_profile_and_download(), 0)
        download.assert_not_called()

    def test_choose_profile_downloads_after_confirmation(self):
        profile = ofbackup_cli.SubscriptionProfile(username="creator.free")
        with (
            mock.patch.object(ofbackup_cli, "list_subscription_profiles", return_value=[profile]),
            mock.patch.object(
                ofbackup_cli,
                "detect_profile_counts",
                return_value=ofbackup_cli.ProfileDetection(
                    username="creator.free", posts=7, photos=5, videos=2
                ),
            ),
            mock.patch.object(ofbackup_cli, "download_user", return_value=0) as download,
            mock.patch("builtins.input", side_effect=["1", "s"]),
            mock.patch("builtins.print"),
        ):
            self.assertEqual(ofbackup_cli.choose_profile_and_download(), 0)
        download.assert_called_once_with("creator.free", source="selector")

    def test_profile_lookup_writes_visible_log(self):
        completed = mock.Mock(
            returncode=0,
            stdout=(
                "OFDOWNLOADER_PROFILE_OK username=creator.example id=123 "
                "posts=9 photos=7 videos=2 archived=1\n"
            ),
            stderr="",
        )
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "downloads"
            with (
                mock.patch.object(ofbackup_cli, "require_credentials"),
                mock.patch.object(ofbackup_cli, "write_ofscraper_config"),
                mock.patch.object(ofbackup_cli, "ofscraper_binary", return_value="ofscraper"),
                mock.patch.object(
                    ofbackup_cli,
                    "get_state",
                    return_value={"download_dir": str(destination)},
                ),
                mock.patch.object(ofbackup_cli.subprocess, "run", return_value=completed),
                mock.patch("builtins.print"),
            ):
                self.assertEqual(
                    ofbackup_cli.test_profile_lookup("creator.example"), 0
                )
            log_path = destination / ofbackup_cli.PROFILE_TEST_LOG_NAME
            self.assertTrue(log_path.exists())
            self.assertIn("posts=9", log_path.read_text(encoding="utf-8"))

    def test_traceback_is_failure_even_with_zero_exit_code(self):
        process = mock.Mock()
        process.stdout = io.StringIO(
            "Traceback (most recent call last):\nTypeError: example\n"
        )
        process.wait.return_value = 0
        with (
            tempfile.TemporaryDirectory() as temporary,
            mock.patch.object(ofbackup_cli, "require_credentials"),
            mock.patch.object(ofbackup_cli, "write_ofscraper_config"),
            mock.patch.object(ofbackup_cli, "ofscraper_binary", return_value="ofscraper"),
            mock.patch.object(
                ofbackup_cli,
                "get_state",
                return_value={"download_dir": temporary},
            ),
            mock.patch.object(ofbackup_cli, "APP_DIR", Path(temporary) / "app"),
            mock.patch.object(
                ofbackup_cli, "DOWNLOAD_LOG_PATH", Path(temporary) / "download.log"
            ),
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
            env=mock.ANY,
        )

    def test_auth_failure_is_detected_without_opening_internal_menu(self):
        process = mock.Mock()
        process.stdout = io.StringIO("Auth Failed\nauth failed quitting on error\n")
        process.wait.return_value = 0
        with (
            tempfile.TemporaryDirectory() as temporary,
            mock.patch.object(ofbackup_cli, "require_credentials"),
            mock.patch.object(ofbackup_cli, "write_ofscraper_config"),
            mock.patch.object(ofbackup_cli, "ofscraper_binary", return_value="ofscraper"),
            mock.patch.object(
                ofbackup_cli,
                "get_state",
                return_value={"download_dir": temporary},
            ),
            mock.patch.object(ofbackup_cli, "APP_DIR", Path(temporary) / "app"),
            mock.patch.object(
                ofbackup_cli, "DOWNLOAD_LOG_PATH", Path(temporary) / "download.log"
            ),
            mock.patch.object(ofbackup_cli.subprocess, "Popen", return_value=process),
            mock.patch("builtins.print"),
        ):
            self.assertEqual(ofbackup_cli.run_ofscraper(["manual"]), 1)

    def test_failed_download_mirrors_log_to_download_folder(self):
        process = mock.Mock()
        process.stdout = io.StringIO("Auth Failed\nauth failed quitting on error\n")
        process.wait.return_value = 0
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            app_dir = root / "app"
            log_path = app_dir / "ultima-descarga.log"
            destination = root / "downloads"
            with (
                mock.patch.object(ofbackup_cli, "require_credentials"),
                mock.patch.object(ofbackup_cli, "write_ofscraper_config"),
                mock.patch.object(ofbackup_cli, "ofscraper_binary", return_value="ofscraper"),
                mock.patch.object(
                    ofbackup_cli,
                    "get_state",
                    return_value={"download_dir": str(destination)},
                ),
                mock.patch.object(ofbackup_cli, "APP_DIR", app_dir),
                mock.patch.object(ofbackup_cli, "DOWNLOAD_LOG_PATH", log_path),
                mock.patch.object(ofbackup_cli.subprocess, "Popen", return_value=process),
                mock.patch("builtins.print"),
            ):
                self.assertEqual(
                    ofbackup_cli.run_ofscraper(
                        ["--username", "creator.example"], mode="perfil", target="creator.example"
                    ),
                    1,
                )
            mirrored = destination / ofbackup_cli.PUBLIC_DOWNLOAD_LOG_NAME
            self.assertTrue(mirrored.exists())
            mirrored_text = mirrored.read_text(encoding="utf-8")
            self.assertIn("Modo: perfil", mirrored_text)
            self.assertIn("--username creator.example", mirrored_text)
            self.assertIn("Auth Failed", mirrored_text)

    def test_auth_fail_option_precedes_root_arguments(self):
        self.assertEqual(
            ofbackup_cli.build_ofscraper_command(
                "ofscraper", ["--username", "example"]
            ),
            ["ofscraper", "--auth-fail", "--username", "example"],
        )


if __name__ == "__main__":
    unittest.main()
