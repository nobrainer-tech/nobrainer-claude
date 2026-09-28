#!/usr/bin/env python3
"""Preview, install and restore a bounded Claude Code setup."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import uuid

ROOT = Path(__file__).resolve().parent
START = "<!-- NOBRAINER-CLAUDE:START -->"
END = "<!-- NOBRAINER-CLAUDE:END -->"
MINIMUM = (2, 1, 280)
AGENTS = ("nbc-scout", "nbc-builder", "nbc-reviewer")
OWNED_PATHS = {"CLAUDE.md", "settings.json", *(f"agents/{name}.md" for name in AGENTS)}
UNCHECKED = object()


def digest(data: bytes | None) -> str | None:
    return hashlib.sha256(data).hexdigest() if data is not None else None


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key; reconcile the source before installing")
        result[key] = value
    return result


def read_json(data: bytes) -> dict:
    result = json.loads(data.decode("utf-8"), object_pairs_hook=unique_object)
    if not isinstance(result, dict):
        raise ValueError("Expected a JSON object")
    return result


def enabled(value) -> bool:
    return str(value).lower() not in ("none", "", "0", "false")


def safe_path(home: Path, relative: str) -> Path:
    if relative not in OWNED_PATHS:
        raise ValueError("Unrecognized managed path")
    target = home / relative
    for part in (target, *target.parents):
        if part == home:
            break
        if part.is_symlink():
            raise ValueError(f"Managed target uses a symlink: {relative}")
        if part.exists() and part != target and not part.is_dir():
            raise ValueError(f"Managed parent is not a directory: {relative}")
    if target.exists() and not target.is_file():
        raise ValueError(f"Managed target is not a file: {relative}")
    return target


def detect_version(binary: str) -> tuple[int, int, int]:
    # Resolve first: subprocess alone cannot find an npm-style claude.cmd shim on Windows.
    resolved = shutil.which(binary)
    if not resolved:
        raise ValueError(f"Claude Code CLI not found: {binary}; install it or pass --claude-bin PATH")
    result = subprocess.run([resolved, "--version"], capture_output=True, text=True, timeout=15, check=True)
    match = re.search(r"\b(\d+)\.(\d+)\.(\d+)\b", result.stdout)
    if not match:
        raise ValueError("Could not read the Claude Code version")
    return tuple(map(int, match.groups()))


def find_flow(home: Path, explicit: Path | None = None) -> str | None:
    candidates = [explicit] if explicit else [home / "skills" / name / "SKILL.md" for name in ("nobrainer-tech-flow", "nobrainer-ultra")]
    for candidate in candidates:
        if candidate is None:
            continue
        candidate = candidate.expanduser()
        if candidate.is_dir():
            candidate = candidate / "SKILL.md"
        if not candidate.is_file():
            continue
        text = candidate.read_text(encoding="utf-8")
        header = re.match(r"\A---\r?\n(.*?)\r?\n---(?:\r?\n|$)", text, re.S)
        match = re.search(r"^name:\s*[\"']?(nobrainer-tech-flow|nobrainer-ultra)[\"']?\s*$", header.group(1), re.M) if header else None
        if match:
            return match.group(1)
    return None


def merge_memory(original: str, block: str) -> str:
    block = block.rstrip("\n")
    counts = original.count(START), original.count(END)
    if counts == (0, 0):
        separator = "" if not original or original.endswith("\n\n") else "\n" if original.endswith("\n") else "\n\n"
        return original + separator + block + "\n"
    if counts != (1, 1):
        raise ValueError("Missing or duplicate memory markers")
    first, last = original.index(START), original.index(END)
    if first > last or (first and original[first - 1] != "\n") or (last and original[last - 1] != "\n"):
        raise ValueError("Malformed memory marker boundaries")
    if original[first + len(START):first + len(START) + 1] not in ("\n", "\r"):
        raise ValueError("Malformed memory start marker")
    tail = last + len(END)
    if original[tail:tail + 1] not in ("", "\n", "\r"):
        raise ValueError("Malformed memory end marker")
    return original[:first] + block + original[tail:]


def owned_agent(payload: bytes, name: str) -> bool:
    text = payload.decode("utf-8")
    header = re.match(r"\A---\r?\n(.*?)\r?\n---\r?\n<!-- managed-by: nobrainer-claude -->\r?\n", text, re.S)
    if not header:
        return False
    names = re.findall(r"^name:\s*(.*?)\s*$", header.group(1), re.M)
    return len(names) == 1 and names[0] in (name, f'"{name}"', f"'{name}'")


def plan_install(home: Path, version: tuple[int, int, int], opus_main=False, enable_auto_memory=False, flow_skill=None) -> dict:
    if not home.is_dir():
        raise ValueError("An existing Claude configuration directory is required")
    home = home.resolve()
    paths = {name: safe_path(home, name) for name in sorted(OWNED_PATHS)}
    if (home / "agents").is_dir():
        for candidate in (home / "agents").rglob("*.md"):
            if candidate in paths.values():
                continue
            text = candidate.read_text(encoding="utf-8")
            header = re.match(r"\A---\r?\n(.*?)\r?\n---(?:\r?\n|$)", text, re.S)
            match = re.search(r"^name:\s*[\"']?(nbc-scout|nbc-builder|nbc-reviewer)[\"']?\s*$", header.group(1), re.M) if header else None
            if match:
                raise ValueError(f"Agent name already exists elsewhere: {match.group(1)}")
    before = {name: path.read_bytes() if path.exists() else None for name, path in paths.items()}
    modes = {name: stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o600 for name, path in paths.items()}
    try:
        settings = read_json(before["settings.json"]) if before["settings.json"] is not None else {}
    except ValueError as error:
        raise ValueError(f"settings.json is not valid JSON; fix it first ({error})") from error
    for key in ("model", "effortLevel"):
        if key in settings and not isinstance(settings[key], str):
            raise ValueError(f"settings.{key} must be a string")
    if "autoMemoryEnabled" in settings and not isinstance(settings["autoMemoryEnabled"], bool):
        raise ValueError("settings.autoMemoryEnabled must be a boolean")
    environment = settings.get("env", {})
    if not isinstance(environment, dict):
        raise ValueError("settings.env must be an object")
    flow = find_flow(home, flow_skill)
    blockers = []
    if version < MINIMUM:
        blockers.append("Claude Code >=2.1.280 required; update through the official installer")
    if not flow:
        blockers.append("Install and discover nobrainer-tech-flow first, or provide --flow-skill for its installed SKILL.md")
    if enabled(environment.get("CLAUDE_CODE_SUBAGENT_MODEL_FORCE")) or enabled(os.environ.get("CLAUDE_CODE_SUBAGENT_MODEL_FORCE")):
        blockers.append("Forced subagent model override detected; reconcile it before installing role-specific models")
    changes = {}
    if opus_main:
        provider_keys = ("CLAUDE_CODE_USE_BEDROCK", "CLAUDE_CODE_USE_VERTEX", "CLAUDE_CODE_USE_FOUNDRY", "CLAUDE_CODE_USE_MANTLE", "ANTHROPIC_BASE_URL", "ANTHROPIC_MODEL")
        if any(enabled(environment.get(key)) or enabled(os.environ.get(key)) for key in provider_keys):
            blockers.append("Custom provider/model environment detected; select the provider's Opus deployment manually")
        if settings.get("model") != "claude-opus-5-5":
            changes["model"] = {"before": settings.get("model"), "after": "claude-opus-5-5"}
            settings["model"] = "claude-opus-5-5"
    if enable_auto_memory:
        if enabled(environment.get("CLAUDE_CODE_DISABLE_AUTO_MEMORY")) or enabled(os.environ.get("CLAUDE_CODE_DISABLE_AUTO_MEMORY")):
            blockers.append("Auto-memory environment override detected; reconcile it before enabling memory")
        if settings.get("autoMemoryEnabled") is not True:
            changes["autoMemoryEnabled"] = {"before": settings.get("autoMemoryEnabled"), "after": True}
            settings["autoMemoryEnabled"] = True
    after = dict(before)
    if changes:
        after["settings.json"] = (json.dumps(settings, indent=2, ensure_ascii=False) + "\n").encode()
    memory = (ROOT / "templates/memory.md").read_text(encoding="utf-8").replace("{{FLOW_ENTRY}}", flow or "nobrainer-ultra")
    after["CLAUDE.md"] = merge_memory((before["CLAUDE.md"] or b"").decode("utf-8"), memory).encode()
    for name in AGENTS:
        relative = f"agents/{name}.md"
        payload = (ROOT / "templates" / relative).read_bytes()
        prior = before[relative]
        if prior is not None and prior != payload and not owned_agent(prior, name):
            raise ValueError(f"Foreign agent definition would be overwritten: {relative}")
        after[relative] = payload
    writes = [name for name in sorted(OWNED_PATHS) if before[name] != after[name]]
    summary = {"claude_dir": str(home), "cli_version": ".".join(map(str, version)), "flow_entry": flow,
               "ready": not blockers, "blockers": blockers, "will_write": writes, "settings_changes": changes,
               "preserved_effort": settings.get("effortLevel"), "runtime_verification": "REQUIRED: /memory, /agents, /model and one bounded task",
               "existing_instruction_imports": bool(re.search(r"(?m)^@", (before["CLAUDE.md"] or b"").decode("utf-8")))}
    return {"home": home, "before": before, "after": after, "modes": modes, "summary": summary}


def atomic_write(path: Path, data: bytes, mode: int, expected=UNCHECKED) -> None:
    descriptor, temporary = tempfile.mkstemp(prefix=".nbc-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, mode)
        if expected is not UNCHECKED:
            if path.is_symlink() or (path.exists() and not path.is_file()) or current(path) != expected:
                raise ValueError(f"File changed at write boundary: {path.name}")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def current(path: Path) -> bytes | None:
    return path.read_bytes() if path.exists() else None


def apply_plan(plan: dict) -> Path | None:
    if not plan["summary"]["ready"]:
        raise ValueError("Preflight blockers must be resolved before apply")
    names = plan["summary"]["will_write"]
    if not names:
        return None
    home = plan["home"]
    store = home / ".nobrainer-claude" / "backups"
    if (home / ".nobrainer-claude").is_symlink() or store.is_symlink():
        raise ValueError("Backup directory must not be a symlink")
    backup = store / uuid.uuid4().hex
    backup.mkdir(parents=True, mode=0o700)
    records = []
    for name in names:
        prior = plan["before"][name]
        if prior is not None:
            saved = backup / "files" / name
            saved.parent.mkdir(parents=True, exist_ok=True)
            atomic_write(saved, prior, 0o600)
        records.append({"path": name, "before": digest(prior), "after": digest(plan["after"][name]), "mode": plan["modes"][name]})
    manifest = {"format": 1, "state": "prepared", "records": records}
    atomic_write(backup / "manifest.json", (json.dumps(manifest, indent=2) + "\n").encode(), 0o600)
    written = []
    try:
        for name in names:
            target = safe_path(home, name)
            if current(target) != plan["before"][name]:
                raise ValueError(f"File changed after preview: {name}")
            target.parent.mkdir(parents=True, exist_ok=True)
            written.append(name)
            atomic_write(target, plan["after"][name], plan["modes"][name], expected=plan["before"][name])
            if target.read_bytes() != plan["after"][name]:
                raise ValueError(f"Readback failed: {name}")
        manifest["state"] = "applied"
        atomic_write(backup / "manifest.json", (json.dumps(manifest, indent=2) + "\n").encode(), 0o600)
    except Exception as error:
        conflicts = []
        for name in reversed(written):
            target = safe_path(home, name)
            if current(target) == plan["before"][name]:
                continue
            if current(target) != plan["after"][name]:
                conflicts.append(name)
                continue
            prior = plan["before"][name]
            try:
                if prior is None:
                    target.unlink()
                else:
                    atomic_write(target, prior, plan["modes"][name], expected=plan["after"][name])
            except (OSError, ValueError):
                conflicts.append(name)
        raise ValueError(f"Apply failed; recovery at {backup}; concurrent conflicts: {conflicts}. {error}") from error
    return backup


def restore(home: Path, backup: Path) -> dict:
    home = home.resolve(strict=True)
    expected = home / ".nobrainer-claude" / "backups"
    if backup.is_symlink() or expected.is_symlink() or (home / ".nobrainer-claude").is_symlink():
        raise ValueError("Unsafe backup path")
    backup = backup.resolve(strict=True)
    if backup.parent != expected.resolve(strict=True):
        raise ValueError("Backup must belong to this Claude configuration directory")
    manifest_path = backup / "manifest.json"
    if manifest_path.is_symlink():
        raise ValueError("Unsafe manifest path")
    manifest = read_json(manifest_path.read_bytes())
    if manifest.get("format") != 1 or manifest.get("state") not in ("prepared", "applied", "restored"):
        raise ValueError("Backup is not a completed installation")
    records = manifest.get("records")
    if not isinstance(records, list) or not records:
        raise ValueError("Malformed backup records")
    seen = set()
    prepared = []
    for entry in records:
        if not isinstance(entry, dict) or set(entry) != {"path", "before", "after", "mode"}:
            raise ValueError("Malformed backup record")
        name = entry["path"]
        if not isinstance(name, str) or name in seen:
            raise ValueError("Invalid or duplicate backup path")
        seen.add(name)
        if not isinstance(entry["mode"], int) or isinstance(entry["mode"], bool) or not 0 <= entry["mode"] <= 0o777:
            raise ValueError("Invalid backup file mode")
        for key in ("before", "after"):
            value = entry[key]
            if not (key == "before" and value is None) and not (isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value)):
                raise ValueError("Invalid backup hash")
        target = safe_path(home, name)
        prior = None
        if entry["before"] is not None:
            saved = backup / "files" / name
            if any(part.is_symlink() for part in (saved, *saved.parents) if part != backup.parent):
                raise ValueError("Unsafe preimage path")
            prior = saved.read_bytes()
            if digest(prior) != entry["before"]:
                raise ValueError("Backup preimage hash mismatch")
        after = current(target)
        permitted = {entry["before"]} if manifest["state"] == "restored" else {entry["before"], entry["after"]}
        if digest(after) not in permitted:
            raise ValueError(f"Later edits detected; restore refused: {name}")
        prepared.append((name, target, prior, entry["mode"], after))
    if manifest["state"] == "restored":
        return {"restored": True, "already_restored": True}
    restored = []
    try:
        for name, target, prior, mode, after in prepared:
            safe_path(home, name)
            if current(target) != after:
                raise ValueError(f"File changed during restore: {name}")
            if prior == after:
                continue
            restored.append((name, target, prior, mode, after))
            if prior is None:
                target.unlink()
            else:
                atomic_write(target, prior, mode, expected=after)
            if current(target) != prior:
                raise ValueError(f"Restore readback failed: {name}")
        manifest["state"] = "restored"
        atomic_write(manifest_path, (json.dumps(manifest, indent=2) + "\n").encode(), 0o600)
    except Exception as error:
        conflicts = []
        for name, target, prior, mode, after in reversed(restored):
            safe_path(home, name)
            if current(target) == after:
                continue
            if current(target) != prior:
                conflicts.append(name)
                continue
            try:
                if after is None:
                    target.unlink(missing_ok=True)
                else:
                    atomic_write(target, after, mode, expected=prior)
            except (OSError, ValueError):
                conflicts.append(name)
        raise ValueError(f"Restore failed; installation retained where possible; concurrent conflicts: {conflicts}. {error}") from error
    return {"restored": True, "files": len(prepared)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--apply", action="store_true")
    mode.add_argument("--restore", type=Path, metavar="BACKUP")
    # An empty CLAUDE_CONFIG_DIR must not resolve to the current directory.
    parser.add_argument("--claude-dir", type=Path, default=Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude"))
    parser.add_argument("--claude-bin", default="claude")
    parser.add_argument("--flow-skill", type=Path)
    parser.add_argument("--opus-main", action="store_true", help="explicitly set the default model to claude-opus-5-5")
    parser.add_argument("--enable-auto-memory", action="store_true", help="explicitly enable Claude Code native auto memory")
    options = parser.parse_args()
    home = options.claude_dir.expanduser()
    if options.restore:
        if options.opus_main or options.enable_auto_memory:
            parser.error("Restore cannot be combined with setup changes")
        print(json.dumps(restore(home, options.restore.expanduser()), indent=2))
        return 0
    plan = plan_install(home, detect_version(options.claude_bin), options.opus_main, options.enable_auto_memory, options.flow_skill)
    if options.apply and plan["summary"]["ready"]:
        backup = apply_plan(plan)
        plan["summary"]["backup"] = str(backup) if backup else None
        plan["summary"]["readback"] = "PASS"
    print(json.dumps(plan["summary"], indent=2, ensure_ascii=False))
    if options.apply and not plan["summary"]["ready"]:
        print("Setup stopped: nothing was written; resolve the blockers above first", file=sys.stderr)
    return 0 if plan["summary"]["ready"] else 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, OSError, subprocess.SubprocessError, UnicodeError) as error:
        print(f"Setup stopped: {error}", file=sys.stderr)
        sys.exit(2)
