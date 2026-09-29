<!-- NOBRAINER-CLAUDE:START -->
## nobrainer-claude

Use nobrainer-tech-flow (https://github.com/nobrainer-tech/nobrainer-tech-flow) through the installed `{{FLOW_ENTRY}}` skill. Read its current instructions and the project's own rules. Load relevant modules on demand; do not copy the entire skills catalog into context.

Keep the owner's chosen MAIN model and effort. This setup supports Opus 5.5 as the orchestrator when selected and available. MAIN owns the goal, decisions, integration and final verification.

Delegate useful independent work to native Claude Code subagents: `nbc-scout` for bounded read-only discovery, `nbc-builder` for an exclusive implementation slice, and `nbc-reviewer` for independent read-only review. Their Haiku/Sonnet aliases resolve according to the current provider and account. Confirm actual model availability; never hide a fallback or substitute a model silently. Do small tasks directly. Use concurrency only for genuinely ready independent work, not a fixed quota.

Give each worker the outcome, necessary context, exclusive write scope, acceptance check and stop conditions, plus any Flow rule it must follow: workers cannot load skills. Workers must not recursively delegate. MAIN inspects the returned files and evidence before accepting work; a worker's report alone is not verification.

Use `CLAUDE.md` for explicit instructions. Use native auto memory only when enabled, for durable verified project facts and lessons with provenance. Do not store secrets, credentials, raw private payloads or transient task status in memory. Keep the current plan and next step in the project's existing task record. Inspect `/memory`, `/context`, `/agents` and `/model` when diagnosing loading or routing; configuration is not proof of runtime behavior.
<!-- NOBRAINER-CLAUDE:END -->
