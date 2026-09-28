import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
SPEC = importlib.util.spec_from_file_location("nobrainer_claude_install_cli", ROOT / "install.py")
installer = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = installer
SPEC.loader.exec_module(installer)

FLOW_HEADER = "---\nname: nobrainer-tech-flow\ndescription: Flow entry\n---\n"


def write_fake_cli(directory: Path, version: str = "2.1.284") -> Path:
    """Create an executable that prints a Claude Code style version line."""
    if os.name == "nt":
        path = directory / "claude.cmd"
        path.write_text(f"@echo off\r\necho {version} (Claude Code)\r\n", encoding="utf-8")
    else:
        path = directory / "claude"
        path.write_text(f"#!/bin/sh\necho '{version} (Claude Code)'\n", encoding="utf-8")
        path.chmod(0o755)
    return path


class MainTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name)
        self.home = self.root / ".claude"
        self.home.mkdir()

    def install_flow(self):
        skill = self.home / "skills" / "nobrainer-tech-flow" / "SKILL.md"
        skill.parent.mkdir(parents=True)
        skill.write_text(FLOW_HEADER, encoding="utf-8")

    def run_main(self, *arguments, version=(2, 1, 284)):
        stdout, stderr = io.StringIO(), io.StringIO()
        with mock.patch.object(installer, "detect_version", return_value=version), \
                mock.patch.object(sys, "argv", ["install.py", *arguments]), \
                contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = installer.main()
        return code, stdout.getvalue(), stderr.getvalue()

    def test_apply_with_blockers_prints_them_and_writes_nothing(self):
        code, out, err = self.run_main("--claude-dir", str(self.home), "--apply")

        summary = json.loads(out)
        self.assertEqual(code, 2)
        self.assertFalse(summary["ready"])
        self.assertTrue(any("nobrainer-tech-flow" in item for item in summary["blockers"]))
        self.assertNotIn("readback", summary)
        self.assertIn("nothing was written", err)
        self.assertEqual(list(self.home.iterdir()), [])

    def test_check_signals_readiness_through_the_exit_code_and_stays_read_only(self):
        blocked_code, blocked_out, blocked_err = self.run_main("--claude-dir", str(self.home), "--check")
        self.install_flow()
        ready_code, ready_out, _ = self.run_main("--claude-dir", str(self.home), "--check")

        self.assertEqual(blocked_code, 2)
        self.assertFalse(json.loads(blocked_out)["ready"])
        self.assertEqual(blocked_err, "")
        self.assertEqual(ready_code, 0)
        self.assertTrue(json.loads(ready_out)["ready"])
        self.assertEqual(sorted(path.name for path in self.home.iterdir()), ["skills"])

    def test_apply_writes_reads_back_and_reports_the_backup(self):
        self.install_flow()

        code, out, _ = self.run_main("--claude-dir", str(self.home), "--apply")

        summary = json.loads(out)
        self.assertEqual(code, 0)
        self.assertEqual(summary["readback"], "PASS")
        self.assertTrue(Path(summary["backup"]).is_dir())
        self.assertTrue((self.home / "CLAUDE.md").is_file())
        self.assertTrue((self.home / "agents" / "nbc-scout.md").is_file())

    def test_unreadable_settings_name_the_file_and_leave_the_directory_untouched(self):
        self.install_flow()
        settings = self.home / "settings.json"
        settings.write_text('{\n  // comment\n  "model": "haiku",\n}\n', encoding="utf-8")
        before = settings.read_bytes()

        with self.assertRaisesRegex(ValueError, "settings.json is not valid JSON"):
            self.run_main("--claude-dir", str(self.home), "--apply")

        self.assertEqual(settings.read_bytes(), before)
        self.assertEqual(sorted(path.name for path in self.home.iterdir()), ["settings.json", "skills"])

    def test_restore_cannot_be_combined_with_setup_options(self):
        with self.assertRaises(SystemExit) as raised, contextlib.redirect_stderr(io.StringIO()):
            self.run_main("--claude-dir", str(self.home), "--restore", str(self.root / "backup"), "--opus-main")

        self.assertEqual(raised.exception.code, 2)

    def test_empty_config_directory_variable_falls_back_to_the_home_default(self):
        self.install_flow()
        elsewhere = self.root / "elsewhere"
        elsewhere.mkdir()

        with mock.patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": ""}), \
                mock.patch.object(Path, "home", return_value=self.root), \
                mock.patch.object(Path, "cwd", return_value=elsewhere):
            code, out, _ = self.run_main("--check")

        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["claude_dir"], str(self.home.resolve()))

    def test_configured_config_directory_is_honored(self):
        custom = self.root / "custom"
        (custom / "skills" / "nobrainer-tech-flow").mkdir(parents=True)
        (custom / "skills" / "nobrainer-tech-flow" / "SKILL.md").write_text(FLOW_HEADER, encoding="utf-8")

        with mock.patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": str(custom)}):
            code, out, _ = self.run_main("--check")

        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["claude_dir"], str(custom.resolve()))


class DetectVersionTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.bin = Path(self.temporary_directory.name)

    def test_reads_the_version_from_an_explicit_binary_path(self):
        cli = write_fake_cli(self.bin, "2.1.284")

        self.assertEqual(installer.detect_version(str(cli)), (2, 1, 284))

    def test_resolves_the_bare_command_name_through_path(self):
        write_fake_cli(self.bin, "2.1.280")
        search_path = str(self.bin) + os.pathsep + os.environ.get("PATH", "")

        with mock.patch.dict(os.environ, {"PATH": search_path}):
            self.assertEqual(installer.detect_version("claude"), (2, 1, 280))

    def test_missing_binary_points_at_the_override_option(self):
        with mock.patch.dict(os.environ, {"PATH": str(self.bin)}):
            with self.assertRaisesRegex(ValueError, "--claude-bin"):
                installer.detect_version("claude")


if __name__ == "__main__":
    unittest.main()
