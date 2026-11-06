import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location(
    "sync", Path(__file__).with_name("sync-upstream-release.py"))
sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync)


class ReleaseSyncTests(unittest.TestCase):
    def test_real_git_merge_preserves_ui_and_detects_conflict(self):
        with tempfile.TemporaryDirectory() as directory:
            def git(*args):
                return subprocess.run(["git", "-C", directory, *args], check=True,
                                      text=True, capture_output=True).stdout.strip()

            git("init", "-b", "main")
            git("config", "user.name", "Test")
            git("config", "user.email", "test@example.invalid")
            core = Path(directory, "core.txt")
            core.write_text("base\n")
            git("add", ".")
            git("commit", "-m", "base")
            git("branch", "official")
            Path(directory, "ui.txt").write_text("my custom UI\n")
            git("add", ".")
            git("commit", "-m", "custom UI")
            git("checkout", "official")
            core.write_text("official update\n")
            git("commit", "-am", "official update")

            real_command = sync.command
            def in_repo(*args, **kwargs):
                return real_command("git", "-C", directory, *args[1:], **kwargs)
            with patch.object(sync, "command", side_effect=in_repo):
                clean, output = sync.merge_check("main", "official")
                self.assertTrue(clean)
                tree = output.splitlines()[0]
                self.assertEqual(git("show", f"{tree}:ui.txt"), "my custom UI")
                self.assertEqual(git("show", f"{tree}:core.txt"), "official update")
                git("checkout", "main")
                core.write_text("custom conflicting change\n")
                git("commit", "-am", "conflict")
                clean, output = sync.merge_check("main", "official")
                self.assertFalse(clean)
                self.assertIn("core.txt", output)
                self.assertEqual(git("status", "--porcelain"), "")

    def test_repeated_notice_is_not_duplicated(self):
        existing = {"number": 7, "state": "open", "body":
                    "<!-- upstream-release-sync:tag -->\n@IntMainJhy\n\nconflict"}
        with patch.object(sync, "items", return_value=iter([existing])), \
                patch.object(sync, "api") as api:
            sync.notice("tag", "conflict", "conflict")
            api.assert_not_called()

    def test_resolved_notice_is_reopened_if_conflict_returns(self):
        existing = {"number": 7, "state": "closed", "body":
                    "<!-- upstream-release-sync:tag -->"}
        with patch.object(sync, "items", return_value=iter([existing])), \
                patch.object(sync, "api") as api:
            sync.notice("tag", "conflict", "details")
            self.assertEqual(api.call_args.kwargs["state"], "open")
            self.assertEqual(api.call_args.args[1], "PATCH")

    def test_prerelease_is_rejected(self):
        with patch.object(sync, "api", return_value={"draft": False, "prerelease": True}):
            with self.assertRaisesRegex(RuntimeError, "stable"):
                sync.sync()


if __name__ == "__main__":
    unittest.main()
