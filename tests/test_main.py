import os
import tempfile
import unittest
from pathlib import Path

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

            main.load_dotenv(env_path)
            config = main.load_config()

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


if __name__ == "__main__":
    unittest.main()
