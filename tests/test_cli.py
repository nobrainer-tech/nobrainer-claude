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


def run_cli(*arguments, version=(2, 1, 284)):
    """Run installer.main() with a stubbed CLI version; return (exit code, stdout, stderr)."""
    stdout, stderr = io.StringIO(), io.StringIO()
    with mock.patch.object(installer, "detect_version", return_value=version), \
            mock.patch.object(sys, "argv", ["install.py", *arguments]), \
            contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        code = installer.main()
    return code, stdout.getvalue(), stderr.getvalue()


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

    def test_apply_with_blockers_prints_them_and_writes_nothing(self):
        code, out, err = run_cli("--claude-dir", str(self.home), "--apply")

        summary = json.loads(out)
        self.assertEqual(code, 2)
        self.assertFalse(summary["ready"])
        self.assertTrue(any("nobrainer-tech-flow" in item for item in summary["blockers"]))
        self.assertNotIn("readback", summary)
        self.assertIn("nothing was written", err)
        self.assertEqual(list(self.home.iterdir()), [])

    def test_check_signals_readiness_through_the_exit_code_and_stays_read_only(self):
        blocked_code, blocked_out, blocked_err = run_cli("--claude-dir", str(self.home), "--check")
        self.install_flow()
        ready_code, ready_out, _ = run_cli("--claude-dir", str(self.home), "--check")

        self.assertEqual(blocked_code, 2)
        self.assertFalse(json.loads(blocked_out)["ready"])
        self.assertEqual(blocked_err, "")
        self.assertEqual(ready_code, 0)
        self.assertTrue(json.loads(ready_out)["ready"])
        self.assertEqual(sorted(path.name for path in self.home.iterdir()), ["skills"])

    def test_apply_writes_reads_back_and_reports_the_backup(self):
        self.install_flow()

        code, out, _ = run_cli("--claude-dir", str(self.home), "--apply")

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
            run_cli("--claude-dir", str(self.home), "--apply")

        self.assertEqual(settings.read_bytes(), before)
        self.assertEqual(sorted(path.name for path in self.home.iterdir()), ["settings.json", "skills"])

    def test_restore_cannot_be_combined_with_setup_options(self):
        with self.assertRaises(SystemExit) as raised, contextlib.redirect_stderr(io.StringIO()):
            run_cli("--claude-dir", str(self.home), "--restore", str(self.root / "backup"), "--opus-main")

        self.assertEqual(raised.exception.code, 2)

    def test_empty_config_directory_variable_falls_back_to_the_home_default(self):
        self.install_flow()
        elsewhere = self.root / "elsewhere"
        elsewhere.mkdir()

        with mock.patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": ""}), \
                mock.patch.object(Path, "home", return_value=self.root), \
                mock.patch.object(Path, "cwd", return_value=elsewhere):
            code, out, _ = run_cli("--check")

        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["claude_dir"], str(self.home.resolve()))

    def test_configured_config_directory_is_honored(self):
        custom = self.root / "custom"
        (custom / "skills" / "nobrainer-tech-flow").mkdir(parents=True)
        (custom / "skills" / "nobrainer-tech-flow" / "SKILL.md").write_text(FLOW_HEADER, encoding="utf-8")

        with mock.patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": str(custom)}):
            code, out, _ = run_cli("--check")

        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["claude_dir"], str(custom.resolve()))


@contextlib.contextmanager
def without_overrides():
    """Run with none of the environment overrides the installer inspects."""
    with mock.patch.dict(os.environ):
        for key in ("SLASH_COMMAND_TOOL_CHAR_BUDGET", "CLAUDE_CODE_SUBAGENT_MODEL_FORCE", "CLAUDE_CODE_DISABLE_AUTO_MEMORY"):
            os.environ.pop(key, None)
        yield


class SkillBudgetTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.home = Path(self.temporary_directory.name) / ".claude"
        skill = self.home / "skills" / "nobrainer-tech-flow" / "SKILL.md"
        skill.parent.mkdir(parents=True)
        skill.write_text(FLOW_HEADER, encoding="utf-8")
        self.settings = self.home / "settings.json"

    def write_settings(self, **values):
        self.settings.write_text(json.dumps(values, indent=2) + "\n", encoding="utf-8")

    def plan(self, **options):
        with without_overrides():
            return installer.plan_install(self.home, (2, 1, 284), **options)

    def test_default_plan_leaves_the_listing_budget_alone(self):
        self.write_settings(theme="dark")

        plan = self.plan()

        self.assertEqual(plan["summary"]["settings_changes"], {})
        self.assertNotIn("settings.json", plan["summary"]["will_write"])

    def test_flag_writes_the_documented_fraction_and_keeps_other_keys(self):
        self.write_settings(model="sonnet", effortLevel="high", env={"KEEP": "1"})

        plan = self.plan(raise_skill_budget=True)

        written = json.loads(plan["after"]["settings.json"])
        self.assertTrue(plan["summary"]["ready"])
        self.assertEqual(written["skillListingBudgetFraction"], 0.02)
        self.assertEqual({key: written[key] for key in ("model", "effortLevel", "env")},
                         {"model": "sonnet", "effortLevel": "high", "env": {"KEEP": "1"}})
        self.assertEqual(plan["summary"]["settings_changes"], {"skillListingBudgetFraction": {"before": None, "after": 0.02}})

    def test_flag_creates_settings_when_none_exist(self):
        plan = self.plan(raise_skill_budget=True)

        self.assertEqual(json.loads(plan["after"]["settings.json"]), {"skillListingBudgetFraction": 0.02})
        self.assertIn("settings.json", plan["summary"]["will_write"])

    def test_lower_value_is_raised_and_a_higher_value_is_kept(self):
        self.write_settings(skillListingBudgetFraction=0.005)
        raised = self.plan(raise_skill_budget=True)
        self.write_settings(skillListingBudgetFraction=0.05)
        kept = self.plan(raise_skill_budget=True)

        self.assertEqual(raised["summary"]["settings_changes"], {"skillListingBudgetFraction": {"before": 0.005, "after": 0.02}})
        self.assertEqual(kept["summary"]["settings_changes"], {})
        self.assertNotIn("settings.json", kept["summary"]["will_write"])

    def test_non_numeric_value_is_rejected_only_when_the_flag_needs_it(self):
        for value in ("large", True, [0.02]):
            with self.subTest(value=value):
                self.write_settings(skillListingBudgetFraction=value)
                self.assertTrue(self.plan()["summary"]["ready"])
                with self.assertRaisesRegex(ValueError, "skillListingBudgetFraction must be a number"):
                    self.plan(raise_skill_budget=True)

    def test_fixed_character_budget_overrides_the_fraction_and_blocks_the_option(self):
        with mock.patch.dict(os.environ, {"SLASH_COMMAND_TOOL_CHAR_BUDGET": "8000"}):
            from_process = installer.plan_install(self.home, (2, 1, 284), raise_skill_budget=True)
        self.write_settings(env={"SLASH_COMMAND_TOOL_CHAR_BUDGET": "8000"})
        from_settings = self.plan(raise_skill_budget=True)

        for plan in (from_process, from_settings):
            self.assertFalse(plan["summary"]["ready"])
            self.assertTrue(any("SLASH_COMMAND_TOOL_CHAR_BUDGET" in item for item in plan["summary"]["blockers"]))

    def test_apply_then_restore_returns_the_original_settings(self):
        self.write_settings(model="sonnet")
        original = self.settings.read_bytes()
        with without_overrides():
            code, out, _ = run_cli("--claude-dir", str(self.home), "--apply", "--raise-skill-budget")
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(self.settings.read_text(encoding="utf-8"))["skillListingBudgetFraction"], 0.02)
            code, _, _ = run_cli("--claude-dir", str(self.home), "--restore", json.loads(out)["backup"])

        self.assertEqual(code, 0)
        self.assertEqual(self.settings.read_bytes(), original)

    def test_restore_cannot_be_combined_with_the_option(self):
        with self.assertRaises(SystemExit) as raised, contextlib.redirect_stderr(io.StringIO()):
            run_cli("--claude-dir", str(self.home), "--restore", str(self.home / "backup"), "--raise-skill-budget")

        self.assertEqual(raised.exception.code, 2)


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
