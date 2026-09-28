import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
SPEC = importlib.util.spec_from_file_location("nobrainer_claude_install", ROOT / "install.py")
installer = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = installer
SPEC.loader.exec_module(installer)


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.home = Path(self.temporary_directory.name) / ".claude"
        self.home.mkdir()
        self.flow_skill = self.home / "skills" / "nobrainer-tech-flow" / "SKILL.md"
        self.flow_skill.parent.mkdir(parents=True)
        self.flow_skill.write_text(
            "---\nname: nobrainer-tech-flow\ndescription: Flow entry\n---\n",
            encoding="utf-8",
        )
        self.settings = {
            "model": "claude-sonnet-4-5",
            "effortLevel": "high",
            "env": {"KEEP_ME": "value"},
            "theme": "dark",
        }
        self.settings_bytes = (json.dumps(self.settings, indent=2) + "\n").encode()
        (self.home / "settings.json").write_bytes(self.settings_bytes)

    def make_plan(self, **options):
        return installer.plan_install(self.home, (2, 1, 280), **options)

    def apply(self, **options):
        return installer.apply_plan(self.make_plan(**options))

    def test_check_plan_is_read_only_and_preserves_bytes_outside_memory_block(self):
        prefix = b"@import shared\r\n\r\nowner before\r\n"
        suffix = b"\r\nowner after\r\n"
        original = prefix + installer.START.encode() + b"\r\nold managed text\r\n" + installer.END.encode() + suffix
        instructions = self.home / "CLAUDE.md"
        instructions.write_bytes(original)
        plan = self.make_plan()

        self.assertTrue(plan["summary"]["ready"])
        self.assertEqual(plan["summary"]["will_write"], ["CLAUDE.md", "agents/nbc-builder.md", "agents/nbc-reviewer.md", "agents/nbc-scout.md"])
        self.assertTrue(plan["summary"]["existing_instruction_imports"])
        updated = plan["after"]["CLAUDE.md"]
        self.assertTrue(updated.startswith(prefix))
        self.assertTrue(updated.endswith(suffix))
        self.assertEqual(instructions.read_bytes(), original)
        self.assertEqual((self.home / "settings.json").read_bytes(), self.settings_bytes)
        self.assertFalse((self.home / ".nobrainer-claude").exists())
        self.assertFalse((self.home / "agents").exists())

    def test_default_plan_preserves_model_effort_and_settings_bytes(self):
        plan = self.make_plan()

        self.assertEqual(plan["after"]["settings.json"], self.settings_bytes)
        self.assertEqual(plan["summary"]["preserved_effort"], "high")
        self.assertEqual(plan["summary"]["settings_changes"], {})

    def test_opus_and_auto_memory_change_only_when_explicit(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            plan = self.make_plan(opus_main=True, enable_auto_memory=True)

        settings = json.loads(plan["after"]["settings.json"])
        self.assertEqual(settings["model"], "claude-opus-5-5")
        self.assertTrue(settings["autoMemoryEnabled"])
        self.assertEqual(settings["effortLevel"], "high")
        self.assertEqual(settings["env"], {"KEEP_ME": "value"})
        self.assertEqual(set(plan["summary"]["settings_changes"]), {"model", "autoMemoryEnabled"})

    def test_old_cli_version_is_reported_as_blocker(self):
        plan = installer.plan_install(self.home, (2, 1, 279), flow_skill=self.flow_skill)

        self.assertFalse(plan["summary"]["ready"])
        self.assertTrue(any(">=2.1.280" in item for item in plan["summary"]["blockers"]))

    def test_missing_flow_is_reported_as_blocker(self):
        self.flow_skill.unlink()
        plan = self.make_plan()

        self.assertFalse(plan["summary"]["ready"])
        self.assertTrue(any("nobrainer-tech-flow" in item for item in plan["summary"]["blockers"]))

    def test_setup_guide_selects_a_current_stable_flow_commit(self):
        setup = (ROOT / "docs/setup.md").read_text(encoding="utf-8")

        self.assertIn("/releases/latest", setup)
        self.assertIn("FLOW_COMMIT", setup)
        self.assertIn("checkout --detach", setup)
        self.assertNotIn("v1.14.1", setup)
        self.assertNotIn("f39b0444d29febe00403a870d334b6292fe4a118", setup)

    def test_legacy_ultra_entry_does_not_satisfy_current_flow_requirement(self):
        self.flow_skill.unlink()
        legacy = self.home / "skills" / "nobrainer-ultra" / "SKILL.md"
        legacy.parent.mkdir(parents=True)
        legacy.write_text(
            "---\nname: nobrainer-ultra\ndescription: Historical Flow alias\n---\n",
            encoding="utf-8",
        )

        plan = self.make_plan()

        self.assertFalse(plan["summary"]["ready"])
        self.assertIsNone(plan["summary"]["flow_entry"])
        self.assertTrue(any("nobrainer-tech-flow" in item for item in plan["summary"]["blockers"]))

    def test_explicit_legacy_ultra_path_is_rejected(self):
        legacy = self.home / "legacy" / "SKILL.md"
        legacy.parent.mkdir()
        legacy.write_text(
            "---\nname: nobrainer-ultra\ndescription: Historical Flow alias\n---\n",
            encoding="utf-8",
        )

        plan = self.make_plan(flow_skill=legacy)

        self.assertFalse(plan["summary"]["ready"])
        self.assertIsNone(plan["summary"]["flow_entry"])
        self.assertTrue(any("nobrainer-tech-flow" in item for item in plan["summary"]["blockers"]))

    def test_apply_is_idempotent(self):
        backup = self.apply()
        first_result = {
            name: (self.home / name).read_bytes()
            for name in ("CLAUDE.md", "agents/nbc-builder.md", "agents/nbc-reviewer.md", "agents/nbc-scout.md")
        }
        second_plan = self.make_plan()

        self.assertIsNotNone(backup)
        self.assertEqual(second_plan["summary"]["will_write"], [])
        self.assertIsNone(installer.apply_plan(second_plan))
        self.assertEqual(
            {name: (self.home / name).read_bytes() for name in first_result},
            first_result,
        )

    def test_foreign_agent_definition_is_not_overwritten(self):
        target = self.home / "agents" / "nbc-builder.md"
        target.parent.mkdir()
        foreign = b"owner-authored agent definition\n"
        target.write_bytes(foreign)

        with self.assertRaisesRegex(ValueError, "Foreign agent definition"):
            self.make_plan()

        self.assertEqual(target.read_bytes(), foreign)

    def test_foreign_marker_mention_does_not_claim_agent_ownership(self):
        target = self.home / "agents" / "nbc-builder.md"
        target.parent.mkdir()
        foreign_definitions = (
            b"---\nname: nbc-builder\ndescription: Foreign\n---\n"
            b"This foreign agent mentions <!-- managed-by: nobrainer-claude --> later.\n",
            b"---\nname: another-builder\ndescription: Foreign\n---\n"
            b"<!-- managed-by: nobrainer-claude -->\nForeign body.\n",
        )

        for foreign in foreign_definitions:
            with self.subTest(foreign=foreign):
                target.write_bytes(foreign)
                with self.assertRaisesRegex(ValueError, "Foreign agent definition"):
                    self.make_plan()
                self.assertEqual(target.read_bytes(), foreign)

    def test_nested_agent_with_managed_name_is_rejected(self):
        nested_agent = self.home / "agents" / "nested" / "scout.md"
        nested_agent.parent.mkdir(parents=True)
        nested_agent.write_text(
            "---\nname: nbc-scout\ndescription: Existing scout\n---\n",
            encoding="utf-8",
        )

        with self.assertRaisesRegex(ValueError, "Agent name already exists elsewhere: nbc-scout"):
            self.make_plan()

    def test_forced_subagent_model_in_settings_is_a_blocker(self):
        settings = dict(self.settings)
        settings["env"] = dict(self.settings["env"], CLAUDE_CODE_SUBAGENT_MODEL_FORCE="sonnet")
        (self.home / "settings.json").write_text(json.dumps(settings), encoding="utf-8")

        plan = self.make_plan()

        self.assertFalse(plan["summary"]["ready"])
        self.assertTrue(any("Forced subagent model override" in item for item in plan["summary"]["blockers"]))

    def test_forced_subagent_model_in_process_environment_is_a_blocker(self):
        with mock.patch.dict(os.environ, {"CLAUDE_CODE_SUBAGENT_MODEL_FORCE": "1"}):
            plan = self.make_plan()

        self.assertFalse(plan["summary"]["ready"])
        self.assertTrue(any("Forced subagent model override" in item for item in plan["summary"]["blockers"]))

    def test_custom_provider_blocks_explicit_opus_selection(self):
        settings = dict(self.settings)
        settings["env"] = dict(self.settings["env"], ANTHROPIC_BASE_URL="https://provider.example")
        (self.home / "settings.json").write_text(json.dumps(settings), encoding="utf-8")

        with mock.patch.dict(os.environ, {}, clear=True):
            plan = self.make_plan(opus_main=True)

        self.assertFalse(plan["summary"]["ready"])
        self.assertTrue(any("Custom provider/model environment" in item for item in plan["summary"]["blockers"]))
        with self.assertRaisesRegex(ValueError, "Preflight blockers"):
            installer.apply_plan(plan)
        self.assertFalse((self.home / "CLAUDE.md").exists())

    def test_symlink_agent_target_is_rejected(self):
        external = Path(self.temporary_directory.name) / "outside-agent.md"
        external.write_bytes(b"outside bytes\n")
        target = self.home / "agents" / "nbc-scout.md"
        target.parent.mkdir()
        try:
            target.symlink_to(external)
        except OSError as error:
            if os.name == "nt" and getattr(error, "winerror", None) == 1314:
                self.skipTest("Windows symlink creation requires the SeCreateSymbolicLinkPrivilege")
            raise

        with self.assertRaisesRegex(ValueError, "symlink"):
            self.make_plan()

        self.assertEqual(external.read_bytes(), b"outside bytes\n")

    def test_mantle_provider_blocks_generic_opus_preset(self):
        with mock.patch.dict(os.environ, {"CLAUDE_CODE_USE_MANTLE": "1"}, clear=True):
            plan = self.make_plan(opus_main=True)
        self.assertFalse(plan["summary"]["ready"])
        with self.assertRaisesRegex(ValueError, "Preflight blockers"):
            installer.apply_plan(plan)
        self.assertEqual((self.home / "settings.json").read_bytes(), self.settings_bytes)

    def test_owned_quoted_agent_name_can_be_updated(self):
        target = self.home / "agents" / "nbc-scout.md"
        target.parent.mkdir()
        template = (ROOT / "templates/agents/nbc-scout.md").read_text(encoding="utf-8")
        for quote in ('"', "'"):
            with self.subTest(quote=quote):
                target.write_text(template.replace("name: nbc-scout", f"name: {quote}nbc-scout{quote}"), encoding="utf-8")
                plan = self.make_plan()
                self.assertTrue(plan["summary"]["ready"])
                self.assertIn("agents/nbc-scout.md", plan["summary"]["will_write"])

    def test_malformed_memory_markers_are_rejected(self):
        cases = (
            installer.START + "\nmissing end",
            "missing start\n" + installer.END,
            installer.END + "\n" + installer.START,
            "prefix" + installer.START + "\nbody\n" + installer.END,
            installer.START + "inline body\n" + installer.END,
            installer.START + "\nbody" + installer.END,
            installer.START + "\nbody\n" + installer.END + "trailing",
            installer.START + "\nfirst\n" + installer.END + "\n" + installer.START + "\nsecond\n" + installer.END,
        )
        for text in cases:
            with self.subTest(text=text):
                with self.assertRaises(ValueError):
                    installer.merge_memory(text, "replacement")

    def test_duplicate_json_keys_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "Duplicate JSON key"):
            installer.read_json(b'{"model":"first","model":"second"}')

    def test_apply_rolls_back_when_atomic_write_fails_after_replacement(self):
        original_instructions = b"owner instructions\n"
        (self.home / "CLAUDE.md").write_bytes(original_instructions)
        plan = self.make_plan()
        target = plan["home"] / "agents" / "nbc-builder.md"
        real_atomic_write = installer.atomic_write

        def replace_then_fail(path, data, mode, expected=installer.UNCHECKED):
            real_atomic_write(path, data, mode, expected=expected)
            if Path(path) == target:
                raise OSError("injected post-replacement failure")

        with mock.patch.object(installer, "atomic_write", side_effect=replace_then_fail):
            with self.assertRaisesRegex(ValueError, "Apply failed"):
                installer.apply_plan(plan)

        self.assertEqual((self.home / "CLAUDE.md").read_bytes(), original_instructions)
        self.assertFalse(target.exists())
        self.assertFalse((self.home / "agents" / "nbc-reviewer.md").exists())
        self.assertFalse((self.home / "agents" / "nbc-scout.md").exists())

    def test_failed_apply_compensation_recovers_from_prepared_backup(self):
        original_instructions = b"owner instructions\n"
        original_builder = (
            b"---\nname: nbc-builder\ndescription: Prior managed builder\n---\n"
            b"<!-- managed-by: nobrainer-claude -->\nPrior body.\n"
        )
        (self.home / "CLAUDE.md").write_bytes(original_instructions)
        builder_path = self.home / "agents" / "nbc-builder.md"
        builder_path.parent.mkdir()
        builder_path.write_bytes(original_builder)
        plan = self.make_plan()
        builder_path = plan["home"] / "agents" / "nbc-builder.md"
        installed_builder = plan["after"]["agents/nbc-builder.md"]
        real_atomic_write = installer.atomic_write
        apply_failure_injected = False
        compensation_failure_injected = False

        def fail_write_and_compensation(path, data, mode, expected=installer.UNCHECKED):
            nonlocal apply_failure_injected, compensation_failure_injected
            if Path(path) == builder_path and data == installed_builder and not apply_failure_injected:
                real_atomic_write(path, data, mode, expected=expected)
                apply_failure_injected = True
                raise OSError("injected apply failure after replacement")
            if Path(path) == builder_path and data == original_builder and expected == installed_builder:
                compensation_failure_injected = True
                raise OSError("injected compensation failure")
            real_atomic_write(path, data, mode, expected=expected)

        with mock.patch.object(installer, "atomic_write", side_effect=fail_write_and_compensation):
            with self.assertRaisesRegex(ValueError, "agents/nbc-builder.md"):
                installer.apply_plan(plan)

        self.assertTrue(apply_failure_injected)
        self.assertTrue(compensation_failure_injected)
        backups = list((self.home / ".nobrainer-claude" / "backups").iterdir())
        self.assertEqual(len(backups), 1)
        backup = backups[0]
        manifest = json.loads((backup / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["state"], "prepared")
        self.assertEqual((self.home / "CLAUDE.md").read_bytes(), original_instructions)
        self.assertEqual(builder_path.read_bytes(), installed_builder)

        result = installer.restore(self.home, backup)

        self.assertTrue(result["restored"])
        self.assertEqual((self.home / "CLAUDE.md").read_bytes(), original_instructions)
        self.assertEqual(builder_path.read_bytes(), original_builder)
        for name in ("nbc-reviewer", "nbc-scout"):
            self.assertFalse((self.home / "agents" / f"{name}.md").exists())

    def test_restore_failure_rolls_back_already_restored_files(self):
        original_instructions = b"owner instructions\n"
        (self.home / "CLAUDE.md").write_bytes(original_instructions)
        with mock.patch.dict(os.environ, {}, clear=True):
            plan = self.make_plan(opus_main=True)
        backup = installer.apply_plan(plan)
        installed = {
            name: (plan["home"] / name).read_bytes()
            for name in plan["summary"]["will_write"]
        }
        settings_path = plan["home"] / "settings.json"
        real_atomic_write = installer.atomic_write

        def restore_then_fail(path, data, mode, expected=installer.UNCHECKED):
            real_atomic_write(path, data, mode, expected=expected)
            if Path(path) == settings_path and data == self.settings_bytes:
                raise OSError("injected restore failure after replacement")

        with mock.patch.object(installer, "atomic_write", side_effect=restore_then_fail):
            with self.assertRaisesRegex(ValueError, "Restore failed"):
                installer.restore(self.home, backup)

        self.assertEqual(
            {name: (plan["home"] / name).read_bytes() for name in installed},
            installed,
        )
        manifest = json.loads((backup / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["state"], "applied")

    def test_atomic_write_guard_preserves_write_injected_before_replace(self):
        target = self.home / "guarded.txt"
        original = b"planned preimage\n"
        concurrent = b"concurrent owner edit\n"
        target.write_bytes(original)
        real_chmod = os.chmod
        real_replace = os.replace

        def write_concurrent_edit_before_guard(path, mode):
            target.write_bytes(concurrent)
            real_chmod(path, mode)

        with mock.patch.object(installer.os, "chmod", side_effect=write_concurrent_edit_before_guard):
            with mock.patch.object(installer.os, "replace", wraps=real_replace) as replace:
                with self.assertRaisesRegex(ValueError, "File changed at write boundary"):
                    installer.atomic_write(target, b"installer payload\n", 0o600, expected=original)

        replace.assert_not_called()
        self.assertEqual(target.read_bytes(), concurrent)

    def test_restore_rejects_later_edits_without_changing_other_files(self):
        (self.home / "CLAUDE.md").write_bytes(b"original instructions\n")
        backup = self.apply()
        changed = self.home / "CLAUDE.md"
        changed.write_bytes(changed.read_bytes() + b"later owner edit\n")
        expected = changed.read_bytes()
        installed_agent = self.home / "agents" / "nbc-builder.md"
        agent_before_restore = installed_agent.read_bytes()

        with self.assertRaisesRegex(ValueError, "Later edits detected"):
            installer.restore(self.home, backup)

        self.assertEqual(changed.read_bytes(), expected)
        self.assertEqual(installed_agent.read_bytes(), agent_before_restore)

    def test_restore_restores_preimages_and_is_idempotent(self):
        original = b"existing user instructions\n"
        (self.home / "CLAUDE.md").write_bytes(original)
        backup = self.apply()

        result = installer.restore(self.home, backup)
        repeated_result = installer.restore(self.home, backup)

        self.assertEqual(result, {"restored": True, "files": 4})
        self.assertEqual(repeated_result, {"restored": True, "already_restored": True})
        self.assertEqual((self.home / "CLAUDE.md").read_bytes(), original)
        for name in installer.AGENTS:
            self.assertFalse((self.home / "agents" / f"{name}.md").exists())

    def test_restore_rejects_corrupt_preimage_before_mutating_targets(self):
        original = b"existing user instructions\n"
        (self.home / "CLAUDE.md").write_bytes(original)
        backup = self.apply()
        installed = (self.home / "CLAUDE.md").read_bytes()
        preimage = backup / "files" / "CLAUDE.md"
        preimage.write_bytes(b"corrupted preimage\n")

        with self.assertRaisesRegex(ValueError, "preimage hash mismatch"):
            installer.restore(self.home, backup)

        self.assertEqual((self.home / "CLAUDE.md").read_bytes(), installed)
        self.assertTrue((self.home / "agents" / "nbc-builder.md").exists())


if __name__ == "__main__":
    unittest.main()
