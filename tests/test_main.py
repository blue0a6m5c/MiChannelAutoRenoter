import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import main


class LoadConfigTests(unittest.TestCase):
    def test_load_config_reads_dotenv_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            env_path = Path(tmpdir) / ".env"
            env_path.write_text(
                "MISSKEY_API_BASE_URL=https://example.test\n"
                "MISSKEY_ACCESS_TOKEN=token-123\n"
                "MISSKEY_CHANNEL_ID=channel-abc\n"
                "MISSKEY_MODE=antenna\n"
                "MISSKEY_ANTENNA_ID=antenna-1\n"
                "MISSKEY_KEYWORDS=hello, #news\n"
                "MISSKEY_MEDIA_MODE=required\n",
                encoding="utf-8",
            )
            os.environ.pop("MISSKEY_API_BASE_URL", None)
            os.environ.pop("MISSKEY_ACCESS_TOKEN", None)
            os.environ.pop("MISSKEY_CHANNEL_ID", None)
            os.environ.pop("MISSKEY_MODE", None)
            os.environ.pop("MISSKEY_ANTENNA_ID", None)
            os.environ.pop("MISSKEY_KEYWORDS", None)
            os.environ.pop("MISSKEY_MEDIA_MODE", None)

            real_env_path = Path(__file__).resolve().parent.parent / ".env"
            backup_path = real_env_path.with_suffix(".bak")
            if real_env_path.exists():
                real_env_path.replace(backup_path)
            try:
                main.load_dotenv(env_path)
                config = main.load_config()
            finally:
                if backup_path.exists():
                    backup_path.replace(real_env_path)

        self.assertEqual(config["base_url"], "https://example.test")
        self.assertEqual(config["token"], "token-123")
        self.assertEqual(config["channel_id"], "channel-abc")
        self.assertEqual(config["mode"], "antenna")
        self.assertEqual(config["antenna_id"], "antenna-1")
        self.assertEqual(config["keywords"], ["hello", "#news"])
        self.assertEqual(config["media_mode"], "required")

    def test_resolve_keywords_reads_external_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            keywords_path = Path(tmpdir) / "keywords.txt"
            keywords_path.write_text("foo\n#bar\n baz \n", encoding="utf-8")
            config = {"keywords": ["env-word"], "keywords_file": str(keywords_path)}
            keywords = main.resolve_keywords(config)

        self.assertEqual(keywords, ["env-word", "foo", "#bar", "baz"])

    def test_matches_media_requirement(self) -> None:
        note_with_media = {"id": "1", "files": [{"id": "file-1"}]}
        note_without_media = {"id": "2"}

        self.assertTrue(main.matches_media_requirement(note_with_media, "required"))
        self.assertFalse(main.matches_media_requirement(note_with_media, "absent"))
        self.assertTrue(main.matches_media_requirement(note_without_media, "absent"))
        self.assertTrue(main.matches_media_requirement(note_without_media, "any"))

    def test_dotenv_values_override_existing_environment(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            env_path = Path(tmpdir) / ".env"
            env_path.write_text("MISSKEY_ACCESS_TOKEN=from-dotenv\n", encoding="utf-8")
            os.environ["MISSKEY_ACCESS_TOKEN"] = "old-value"
            main.load_dotenv(env_path)

        self.assertEqual(os.environ["MISSKEY_ACCESS_TOKEN"], "from-dotenv")

    def test_should_process_note_skips_renotes_and_self_posts(self) -> None:
        config = {"skip_renotes": True, "ignore_self": True, "self_user_id": "user-1"}

        self.assertFalse(main.should_process_note({"id": "1", "renoteId": "orig"}, config, []))
        self.assertFalse(main.should_process_note({"id": "2", "renote": {"id": "orig"}}, config, []))
        self.assertFalse(main.should_process_note({"id": "3", "user": {"id": "user-1"}}, config, []))
        self.assertTrue(main.should_process_note({"id": "4", "text": "hello"}, config, []))

    def test_request_json_includes_token_in_payload(self) -> None:
        class FakeResponse:
            def __init__(self, payload: dict) -> None:
                self._payload = payload

            def read(self) -> bytes:
                return json.dumps(self._payload).encode("utf-8")

            def __enter__(self) -> "FakeResponse":
                return self

            def __exit__(self, exc_type, exc_val, exc_tb) -> None:
                return None

        captured = {}

        def fake_urlopen(request, timeout=20):
            captured["url"] = request.full_url
            captured["data"] = request.data
            captured["headers"] = dict(request.header_items())
            return FakeResponse({"ok": True})

        with patch("main.urllib.request.urlopen", side_effect=fake_urlopen):
            response = main.request_json("https://example.test", "token-123", "notes/global-timeline", {"limit": 3})

        self.assertEqual(response, {"ok": True})
        self.assertEqual(captured["url"], "https://example.test/api/notes/global-timeline")
        self.assertEqual(json.loads(captured["data"].decode("utf-8")), {"i": "token-123", "limit": 3})
        self.assertIn("Content-Type", captured["headers"])


if __name__ == "__main__":
    unittest.main()
