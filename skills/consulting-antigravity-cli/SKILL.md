---
name: consulting-antigravity-cli
description: Use when a non-Antigravity agent wants to consult the local Antigravity CLI through agy -p for a second opinion, code review, design feedback, or an ongoing cross-model dialogue. Antigravity must never invoke this skill on itself.
---

# Consult Antigravity CLI from another agent

This skill is for Codex, Claude Code, and other **non-Antigravity** callers. An Antigravity agent must not invoke `agy` recursively. The launcher at [scripts/consult_antigravity_cli.sh](scripts/consult_antigravity_cli.sh) uses `../../lib/consultation_runner.py`; keep the common-skills checkout together when installing or copying it.

## Defaults

| Setting | Default |
| --- | --- |
| Model | Antigravity CLI default; no `--model` flag |
| Permission mode | `dangerously-skip-permissions` |
| Sandbox | off unless requested |
| Output | complete answer on stdout, text by default |
| Working directory | caller's current directory |
| Spend and token caps | none |

Honor explicit user overrides. Do not change the model, permission mode, or working directory merely to simplify a call. The CLI runs non-interactively with `-p`. `--permission-mode request-review` avoids the default permission bypass, and `--sandbox` requests terminal sandbox restrictions. Only use a different repository path when the user names it.

## Conversation continuity

By default, calls from the **same identifiable caller conversation** and physical working directory resume the same Antigravity conversation. A new caller conversation starts separately, including when it uses the same repository. The wrapper uses the immediate caller's current session ID or an explicit per-call `--caller-kind` plus `--caller-session-id`. If that identity is unavailable or ambiguous, it warns and performs an independent one-shot call. It never resumes Antigravity's most recent workspace conversation with `--continue`.

Do not use a session ID inherited from an outer agent, shell profile, or earlier task. Antigravity's own conversation ID has not been verified as an ordinary shell environment variable; an Antigravity host integration must pass the current ID explicitly if it wants caller-scoped continuity in other consulting skills.

| Request | Wrapper option | Effect |
| --- | --- | --- |
| Normal follow-up | none | Resume this caller's saved Antigravity ID |
| Independent question | `--one-shot` | Start separately without changing saved state |
| Replace current consultation | `--new-session` | Retire old mapping before CLI invocation |
| Another thread within this caller | `--chain NAME` | Parent-scoped named conversation |
| Intentionally share across callers | `--shared-chain NAME` | Cross-caller conversation, only on explicit user request |
| Inspect or clear mapping | `--status`, `--reset-session`, `--reset-chain NAME`, `--reset-shared-chain NAME` | State only; target conversation remains |

Inherited `CONSULT_ANTIGRAVITY_CHAIN_KEY` is ignored. Old globally keyed chain files are not imported. `--status` remains available while a consultation is running. A confirmed failure before Antigravity starts preserves the prior mapping; an uncertain failure after launch blocks it until `--new-session` or an explicit reset. Once Antigravity has started, a failed `--new-session` never restores the old mapping.

## Invocation

```bash
/path/to/consult_antigravity_cli.sh "user prompt here"
```

Use stdin for detailed prompts and `--cd` only for an explicitly named target directory:

```bash
/path/to/consult_antigravity_cli.sh --cd /absolute/path/to/repo <<'PROMPT'
<question about that repository>
PROMPT
```

When a prompt is supplied as arguments, stdin is ignored. Choose one input form per call.

Explicit controls:

```bash
/path/to/consult_antigravity_cli.sh --new-session "Start a separate review"
/path/to/consult_antigravity_cli.sh --one-shot "Independent check"
/path/to/consult_antigravity_cli.sh --chain architecture "Follow up here"
/path/to/consult_antigravity_cli.sh --permission-mode request-review "Review only"
```

`--output-format json` and `stream-json` are supported. The wrapper internally reads Antigravity's structured `conversation_id`, `status`, and `response`; it resumes with exact `--conversation <id>`. If the CLI creates a different ID despite a successful exit, the wrapper withholds that answer and blocks the mapping. It does not rely on log text to recover IDs. The installed CLI may have a short default print timeout, so the wrapper sets a long, configurable `--print-timeout` and rejects a timeout warning even if the CLI exits successfully.

## Authentication and waiting

If host sandboxing hides Antigravity's login or session files, use the host's authorized normal-local execution path. `--auth-smoke` sends only a neutral authentication prompt from a temporary directory. If that fails, report the actual auth error before sending repository context.

Long responses are normal. Do not impose a short shell timeout, duplicate a slow call, or silently switch the model. Present Antigravity's response and make any disagreement with your own assessment explicit.
