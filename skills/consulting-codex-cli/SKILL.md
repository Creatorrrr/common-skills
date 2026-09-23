---
name: consulting-codex-cli
description: Use when a non-Codex agent wants to consult the local Codex CLI for a second opinion, code review, design feedback, or an ongoing cross-model dialogue. Codex must never invoke codex exec on itself.
---

# Consult Codex CLI from another agent

This skill is for Claude Code, Antigravity, and other **non-Codex** callers. If the immediate caller is Codex, warn and stop; the wrapper also refuses recursive `codex exec` with a nonzero exit. The launcher at [scripts/consult_codex_cli.sh](scripts/consult_codex_cli.sh) uses `../../lib/consultation_runner.py`; keep the common-skills checkout together when installing or copying it.

## Defaults

| Setting | Default | CLI form |
| --- | --- | --- |
| Model | `gpt-6-sol` | `-m gpt-6-sol` |
| Reasoning effort | `max` | `-c model_reasoning_effort="max"` |
| Speed | standard | `-c service_tier="default"` |
| Approval | automatic review, on request | `--approve-for-me` and `-c approval_policy="on-request"` |
| Sandbox | workspace-write via automatic review | `--approve-for-me` |
| Working directory | caller's current directory | `-C <directory>` |
| Spend and token caps | none | no cap flags |

Keep the user's explicit model, effort, speed, and path choices. Fast mode is opt-in through `--fast`; `--standard` selects the default service tier. If this account rejects `gpt-6-sol`, report the error and let the user choose a supported model. Do not silently downgrade it or change effort because a run is slow.

## Conversation continuity

By default, calls from the **same identifiable caller conversation** and physical working directory resume one Codex CLI conversation. A new caller conversation gets a separate state key even in the same repository. The wrapper accepts the immediate caller's current session ID or explicit per-call `--caller-kind` and `--caller-session-id`. If the ID cannot be established, it warns and runs independently. It never uses `--last` or a workdir-only key.

Do not reuse an ID from a prior task or from an outer agent's inherited environment. A host without a reliable current session ID should keep the one-shot fallback until an integration can pass that ID on every invocation.

| Request | Wrapper option | Effect |
| --- | --- | --- |
| Normal follow-up | none | Resume this caller's saved Codex thread ID |
| Independent question | `--one-shot` | Start separately without changing saved state |
| Replace current consultation | `--new-session` | Retire the old mapping before CLI invocation |
| Another thread within this caller | `--chain NAME` | Parent-scoped named conversation |
| Intentionally share across callers | `--shared-chain NAME` | Cross-caller conversation, only on explicit user request |
| Inspect or clear mapping | `--status`, `--reset-session`, `--reset-chain NAME`, `--reset-shared-chain NAME` | State only; Codex thread remains |

`--status` remains available while a consultation is running. A confirmed failure before Codex starts preserves the prior mapping; an uncertain failure after launch blocks it until `--new-session` or an explicit reset. Once Codex has started, a failed `--new-session` never restores the old thread pointer.

## Invocation

```bash
/path/to/consult_codex_cli.sh "user prompt here"
```

Use stdin for detailed or shell-sensitive prompts:

```bash
/path/to/consult_codex_cli.sh <<'PROMPT'
<user prompt verbatim>
PROMPT
```

When a prompt is supplied as arguments, stdin is ignored. Choose one input form per call.

Explicit controls:

```bash
/path/to/consult_codex_cli.sh --new-session "Start a separate review"
/path/to/consult_codex_cli.sh --one-shot "Independent check"
/path/to/consult_codex_cli.sh --chain architecture "Follow up here"
/path/to/consult_codex_cli.sh --model <supported-model> --effort high --fast "Review this"
```

The wrapper runs `codex exec --json`, stores its exact `thread.started.thread_id` only after a completed turn, and resumes through `codex exec resume <id>`. It checks that a resumed turn reports the same ID and prints only the final answer. Root-level working-directory and automatic-review options are placed before `exec resume`, because the resume subcommand does not accept those flags itself.

## Waiting and response

Use a generous host timeout; `max` effort can take many minutes. Do not start a duplicate call because one is slow. Present Codex's response before synthesizing your own assessment, and explain any disagreement. Do not bypass approvals or sandboxing without the user's explicit request.
