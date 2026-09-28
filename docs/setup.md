# Install without losing your setup

## 1. Check the actual client

Run `claude --version`. The supported profile requires **2.1.280 or later**, the documented minimum for Opus 5.5. Update using the [official installation method](https://code.claude.com/docs/en/setup) for your system if needed. Do not assume a version string proves account access.

Read existing user and project `CLAUDE.md` files, imports, `.claude/agents` definitions and applicable managed settings. Existing instructions can outrank or conflict with this adapter. In particular, imported rules may route workers to models unavailable in Claude Code. Resolve that deliberately; this installer never rewrites imported files.

## 2. Install the latest stable nobrainer-tech-flow

Check the [latest stable release](https://github.com/nobrainer-tech/nobrainer-tech-flow/releases/latest) and its [canonical installation contract](https://github.com/nobrainer-tech/nobrainer-tech-flow/blob/main/docs/INSTALL.md) at setup time. On September 28, 2026, the latest-stable check returned **v2.0.0** at immutable commit `ce1bc2033482e222c70e3d365e76be57b8f2394c`. That is a dated readback, not a version to keep using after a newer stable release appears. Select the full commit SHA belonging to the latest stable release and set `FLOW_COMMIT` below before running the commands. Do not install a prerelease, floating branch, or historical `nobrainer-ultra` alias.

```bash
FLOW_COMMIT="<full commit SHA for the latest stable release>"
git clone --no-checkout https://github.com/nobrainer-tech/nobrainer-tech-flow.git
git -C nobrainer-tech-flow checkout --detach "$FLOW_COMMIT"
test "$(git -C nobrainer-tech-flow rev-parse HEAD)" = "$FLOW_COMMIT"
python3 nobrainer-tech-flow/scripts/validate_skills.py --suite
python3 nobrainer-tech-flow/scripts/install_skills.py --client claude --mode copy
```

The first installer run is a read-only preview. Inspect every target and conflict; apply only that same reviewed commit after the preview is clean:

```bash
python3 nobrainer-tech-flow/scripts/install_skills.py --client claude --mode copy --apply
```

Stop if validation or preview fails. For a custom Claude config directory, pass the official Flow installer's `--dest PATH/skills` on both preview and apply. Use copy mode on Windows to avoid requiring symlink privileges. Preserve unrelated skills and instructions; never substitute a dirty private checkout.

Restart Claude Code when required and verify that the exact installed Flow source is the selected release and the entry point is discovered. The NoBrainer Claude installer accepts only `name: nobrainer-tech-flow`; an old `nobrainer-ultra` file does not satisfy this prerequisite. A matching file is source evidence, not proof that a named workflow runs correctly in the client.

## 3. Preview and apply the adapter

Run `python3 install.py --check` from this repository. Review target files and blockers. The base setup appends or updates a single managed block in `CLAUDE.md` and installs three owned definitions under `agents/`. Existing model, effort, permissions, auto-memory settings and imports are preserved.

Apply or restore while no other process is editing these configuration files. The tool rechecks contents at the write boundary and refuses observed drift, but a portable file installer cannot lock out arbitrary external editors.

Use `--opus-main` only to choose Opus 5.5 as the persistent default. Use `--enable-auto-memory` only to enable native auto memory explicitly. Preview and apply must use the same options. No network code is fetched and no model request is made by this installer.

The JSON summary lists owned setting changes without printing unrelated settings or credentials. Proposed instruction and worker contents are inspectable in `templates/`. Apply verifies written bytes and prints the backup directory.

## 4. Verify a fresh session

Open Claude Code in a small test repository. Inspect `/memory`, `/agents`, `/model` and `/context`. Confirm the selected model and which instruction files loaded. Ask for one small read-only discovery task using `nbc-scout`, then inspect the actual model and returned file references. Follow with an implementation/review example only inside a disposable or explicitly authorized scope.

Settings, aliases, environment variables and managed policy can affect routing. Agent definitions do not prove a worker ran on the requested model. Record any fallback and do not call the setup runtime-verified until this check passes on your client/account.

## 5. Keep memory useful

Keep explicit policy in `CLAUDE.md`, durable learned preferences and project context in native auto memory, and live execution status in the project's task record. Review `/memory` periodically. Do not store credentials, private raw payloads or every terminal result in memory. This installer never creates or replaces project `MEMORY.md` files.

When upgrading this toolkit, preview first. Its managed block is updated in place; surrounding content stays intact. Unknown agent files with conflicting names stop installation. Restore is guarded against later edits and requires the original backup manifest.

An interrupted apply may leave a `prepared` backup. Restore accepts it only when every managed target still matches either its recorded preimage or installed bytes. Any third state stops recovery for manual reconciliation.
