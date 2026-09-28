import importlib.util
from pathlib import Path
import re
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
SPEC = importlib.util.spec_from_file_location("nobrainer_claude_install_templates", ROOT / "install.py")
installer = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = installer
SPEC.loader.exec_module(installer)

AGENT_DIR = ROOT / "templates" / "agents"
FRONTMATTER_KEYS = {"name", "description", "tools", "model", "maxTurns"}
READ_ONLY_TOOLS = {"Read", "Glob", "Grep"}
ROLE_MODELS = {"nbc-scout": "haiku", "nbc-builder": "sonnet", "nbc-reviewer": "sonnet"}
DELEGATION_TOOLS = {"Agent", "Task"}


def read_agent(name: str) -> tuple[dict, bytes]:
    payload = (AGENT_DIR / f"{name}.md").read_bytes()
    header = re.match(r"\A---\r?\n(.*?)\r?\n---\r?\n", payload.decode("utf-8"), re.S)
    fields = {}
    for line in header.group(1).splitlines():
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip()
    return fields, payload


def tool_set(fields: dict) -> set:
    return {tool.strip() for tool in fields["tools"].split(",") if tool.strip()}


class AgentTemplateTests(unittest.TestCase):
    def test_templates_match_the_names_the_installer_manages(self):
        self.assertEqual({path.stem for path in AGENT_DIR.glob("*.md")}, set(installer.AGENTS))
        for name in installer.AGENTS:
            with self.subTest(agent=name):
                fields, payload = read_agent(name)
                self.assertEqual(fields["name"], name)
                self.assertTrue(installer.owned_agent(payload, name))

    def test_frontmatter_uses_only_the_documented_fields(self):
        for name in installer.AGENTS:
            with self.subTest(agent=name):
                fields, _ = read_agent(name)
                self.assertEqual(set(fields), FRONTMATTER_KEYS)
                self.assertTrue(fields["description"])
                self.assertTrue(fields["maxTurns"].isdigit() and int(fields["maxTurns"]) > 0)

    def test_workers_hold_no_delegation_tool(self):
        for name in installer.AGENTS:
            with self.subTest(agent=name):
                fields, _ = read_agent(name)
                self.assertFalse(tool_set(fields) & DELEGATION_TOOLS)
                self.assertNotIn("(", fields["tools"])

    def test_only_the_builder_can_change_files_or_run_commands(self):
        for name in ("nbc-scout", "nbc-reviewer"):
            with self.subTest(agent=name):
                self.assertEqual(tool_set(read_agent(name)[0]), READ_ONLY_TOOLS)
        self.assertEqual(tool_set(read_agent("nbc-builder")[0]), READ_ONLY_TOOLS | {"Edit", "Write", "Bash"})

    def test_role_models_match_the_public_contract(self):
        for name, model in ROLE_MODELS.items():
            with self.subTest(agent=name):
                self.assertEqual(read_agent(name)[0]["model"], model)


class MemoryTemplateTests(unittest.TestCase):
    def setUp(self):
        self.text = (ROOT / "templates" / "memory.md").read_text(encoding="utf-8")

    def test_block_is_delimited_by_exactly_one_marker_pair(self):
        self.assertEqual((self.text.count(installer.START), self.text.count(installer.END)), (1, 1))
        self.assertTrue(self.text.startswith(installer.START))
        self.assertTrue(self.text.rstrip().endswith(installer.END))

    def test_flow_entry_placeholder_appears_exactly_once(self):
        self.assertEqual(self.text.count("{{FLOW_ENTRY}}"), 1)
        self.assertEqual(set(re.findall(r"\{\{[A-Z_]+\}\}", self.text)), {"{{FLOW_ENTRY}}"})

    def test_block_adds_no_imports_and_no_machine_specific_paths(self):
        self.assertIsNone(re.search(r"(?m)^\s*@", self.text))
        self.assertNotIn("\\`", self.text)
        for fragment in ("/Users/", "/home/", "C:\\", "~/"):
            self.assertNotIn(fragment, self.text)


if __name__ == "__main__":
    unittest.main()
