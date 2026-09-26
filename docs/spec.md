# NoBrainer Claude setup contract

SPEC_ID: NOBRAINER-CLAUDE-20260927
STATUS: IMPLEMENTED
RELEASE: 0.1.0
OWNER_AUTHORITY: Build and release a public Claude Code adapter and website, compatible with Opus 5.5 orchestration and useful delegated work.

## Outcome

A developer can give Claude Code the public repository URL, inspect a read-only install plan, and apply a small setup that combines persistent instructions, named native subagents and the current nobrainer-tech-flow. Opus 5.5 is an explicit optional model preset; existing MAIN model and effort stay unchanged by default.

## Scope and acceptance

- Installer: Python 3.11+, explicit `--check` or `--apply`, optional `--claude-dir`, `--opus-main`, and `--enable-auto-memory`. Claude Code >=2.1.280 required for the supported profile. No credentials, network installation, model requests, permission changes or agent-team enablement.
- Instructions: one managed block in user `CLAUDE.md`; preserve every byte outside that block and existing imports. Malformed or duplicate markers fail before writing.
- Delegation: three named native definitions: Haiku scout, Sonnet builder, Sonnet reviewer. MAIN chooses useful independent work and verifies it. Aliases depend on provider and account; actual model readback is required. No invented concurrency knob or token-saving guarantee.
- Memory: `CLAUDE.md` holds explicit workflow policy; auto memory holds reviewed durable lessons. The installer does not write project `MEMORY.md` files or import private owner memory. Auto-memory remains unchanged unless explicitly selected.
- Settings: preserve all unrelated JSON keys, model and effort by default. `--opus-main` explicitly selects `claude-opus-5-5`; provider/access support remains a runtime check.
- Recovery: private preimage backup and manifest, atomic individual writes, rollback on failure, idempotence, and guarded restore that refuses to overwrite later edits.
- Distribution: public `nobrainer-tech/nobrainer-claude`, MIT license, cross-platform CI, versioned release, stable site at `https://nobrainer.tech/claude/`, prominent reciprocal repo/site links and copyable installation prompt.
- Website: English, Signature colors/type, an honest Opus-to-workers tree, memory explanation and one clear installation CTA. Native settings and verified limits only.

## Exclusions

Do not change the owner's live Claude installation or model settings while testing. Do not modify other dirty repositories, move data, copy provider keys, enable permission bypass, install legacy leaked-prompt skills, or publish social posts as part of this release.

## Proof

Temporary-home tests cover preservation, repeat apply, conflicts, unsafe paths, rollback and restore drift. Inspect actual CLI discovery where available, without billing a model request. Browser checks cover mobile/desktop, images, copy feedback and overflow. Release proof requires exact GitHub commit/CI/release and public file hashes plus browser readback. No configuration test is described as an Opus 5.5 runtime task.
