# Compatibility and evidence

Verified documentation baseline: September 27, 2026.

| Area | Contract |
|---|---|
| Model | Opus 5.5 uses the explicit ID `claude-opus-5-5` and requires Claude Code >=2.1.280. Alias resolution varies by provider. |
| MAIN | Default installation preserves model and effort. The optional preset changes the default model only; higher-priority environment or managed settings still matter. |
| Workers | Native user agent Markdown with `tools`, `model` and `maxTurns`. Haiku scouts; Sonnet builds and reviews. No recursive delegation tool is granted. |
| Permissions | Scout/reviewer receive Read, Glob and Grep. Builder also receives Edit, Write and Bash under the existing permission system. Prompt rules do not sandbox Bash. |
| Memory | `CLAUDE.md` is explicit instruction memory. Native auto memory is separate and normally enabled by Claude Code. This tool only enables it on an explicit flag. |
| Teams | Experimental agent teams remain untouched. They are a separate coordination model, not necessary for these workers. |
| Platforms | Standard-library Python 3.11+; CI exercises Linux, macOS and Windows. Model availability is not established by cross-platform unit tests. |

Persistent agent-memory frontmatter is deliberately absent from the read-only roles: Claude Code adds memory-writing tools when that feature is enabled. A forced `CLAUDE_CODE_SUBAGENT_MODEL_FORCE` override stops this setup, since it would defeat role-specific model choices.

The installer preserves existing user imports and reports their presence. Check for contradictory routing in `/memory`; installing a managed block cannot repeal higher-priority owner or organization policy. Do not treat file discovery as proof that the running client has loaded a newly created agents directory.

## Evidence levels

- Source contract: checked against the official pages below.
- Installer behavior: temporary-home preservation, conflicts, rollback and restore tests.
- Local host preflight: the inspected host has Claude Code 2.1.241; the installer correctly reports the version blocker without writing.
- Opus 5.5 task execution: **not claimed by the configuration test suite**. Requires a compatible signed-in client, account entitlement and actual model readback.
- An isolated attempt to acquire CLI 2.1.283 was refused by the test host's package-age policy. That policy was not bypassed. Native `doctor` ran only on the pre-existing 2.1.241 client in a separate config directory; it is not 5.5 runtime proof.
- Published distribution and website: release-specific receipts are recorded in the release notes after external readback.

## Primary sources

- [Model configuration](https://code.claude.com/docs/en/model-config): exact model IDs, minimum version, provider aliases and precedence.
- [Custom subagents](https://code.claude.com/docs/en/sub-agents): definitions, tool scope, model selection and memory side effects.
- [Memory](https://code.claude.com/docs/en/memory): explicit instructions, native auto memory and storage behavior.
- [Settings](https://code.claude.com/docs/en/settings): settings scopes and supported fields.
- [Agent teams](https://code.claude.com/docs/en/agent-teams): optional experimental coordination.
- [Permissions](https://code.claude.com/docs/en/permissions): permission rules and enforcement.
- [nobrainer-tech-flow installation](https://github.com/nobrainer-tech/nobrainer-tech-flow/blob/main/docs/INSTALL.md): canonical workflow distribution, preview and conflicts.
