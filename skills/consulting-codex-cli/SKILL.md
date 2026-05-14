---
name: consulting-codex-cli
description: Use this skill when the user wants an agent to consult the local Codex CLI for a second opinion, cross-agent dialogue, code review, design feedback, or "ask Codex" request. Triggers include phrases like "codex한테 물어봐", "codex 의견", "Codex와 의견 주고받기", "ask codex", "consult codex", "cross-check with codex", or any request to invoke `codex exec`. If this skill is invoked from inside Codex, warn that Codex cannot recursively call itself and stop without running `codex exec`.
---

# Consulting Codex CLI

This skill lets Claude Code, Gemini CLI, Antigravity, or another agent invoke the local `codex` CLI as a subprocess, collect Codex's opinion, and compare it with the calling agent's own reasoning.

Codex sessions must not use this skill to invoke `codex exec`. If the current agent is Codex and this skill is triggered, respond with a warning and stop.

## Core principles

1. The user's explicit instructions override these defaults.
2. If the current agent is Codex, say: `Codex cannot use consulting-codex-cli because it would recursively call Codex. I will not run codex exec from inside Codex.` Then stop.
3. Run Codex non-interactively with `codex exec` so the subprocess returns.
4. If the user does not specify a model, use the current latest frontier default model: `gpt-5.5`.
5. If the user does not specify reasoning effort, use `xhigh`.
6. Do not pass token, budget, reasoning-token, or output caps.
7. Use Codex's automatic permission judgment path by default: `approval_policy=on-request` with `workspace-write` sandboxing.
8. Long waits are expected. Do not impose short shell timeouts or retry just because output is slow.
9. Pass the user's prompt faithfully. Preserve constraints, paths, language, and requested output shape.
10. Present Codex's response before synthesizing agreement or disagreement.

## Resolve the bundled script

Prefer the bundled wrapper because it encodes the defaults above and avoids retyping fragile CLI flags.

The wrapper also refuses to run inside a Codex shell by checking Codex environment markers. Resolve the script path in this order:

1. Start from the directory that contains this `SKILL.md`.
2. Use `scripts/consult_codex_cli.sh` relative to that directory.
3. If the active workspace does not contain this skill, look in the installed skill location such as `~/.claude/skills/consulting-codex-cli/`, the linked `common-skills/skills/consulting-codex-cli/`, or the agent's global skill install path.

Do not assume `scripts/consult_codex_cli.sh` is project-local unless the user has vendored this skill into that project.

## Defaults

| Option | Default | How it is passed |
| --- | --- | --- |
| Model | `gpt-5.5` | `-m gpt-5.5` |
| Reasoning effort | `xhigh` | `-c model_reasoning_effort="xhigh"` |
| Approval policy | `on-request` | `-c approval_policy="on-request"` |
| Sandbox | `workspace-write` | `--full-auto -s workspace-write` |
| Print mode | non-interactive | `codex exec` |
| Budget/token caps | none | do not pass any cap flags |

If the user explicitly names another model, effort, working directory, output mode, or permission posture, use that value and keep the remaining defaults.

## Canonical invocation

For a short prompt:

```bash
/path/to/consult_codex_cli.sh "user prompt here"
```

For a detailed or shell-sensitive prompt, pass it through stdin:

```bash
/path/to/consult_codex_cli.sh <<'PROMPT'
<user prompt verbatim>
PROMPT
```

For a repo-specific question, set the working directory:

```bash
/path/to/consult_codex_cli.sh --cd /absolute/path/to/repo <<'PROMPT'
<question about this repository>
PROMPT
```

For an explicit model override:

```bash
/path/to/consult_codex_cli.sh --model gpt-5.4 --effort high "user prompt here"
```

## Waiting policy

`gpt-5.5` with `xhigh` can take many minutes. Treat that as normal.

- Set a generous shell timeout. Use at least `3600000` ms when the host tool requires a timeout value.
- If the process is still running and there is no hard error, continue waiting.
- Do not launch duplicate Codex consultations to speed up a slow run.
- Only treat the call as failed if `codex` exits non-zero, reports authentication or quota failure, or the user cancels.

## Permission policy

Default to automatic judgment:

```bash
--full-auto -s workspace-write -c 'approval_policy="on-request"'
```

This lets Codex decide when it needs approval while keeping it sandboxed to the workspace by default.

Override only when the user explicitly asks for a different posture. Do not use `--dangerously-bypass-approvals-and-sandbox` unless the user explicitly requests it and acknowledges the risk.

## How to use Codex's response

Default behavior:

1. Run your own initial analysis enough to know what you are asking Codex.
2. Invoke Codex with the user's prompt and any necessary repo paths.
3. Show Codex's response or a faithful summary, depending on the user's request.
4. Compare Codex's answer with your own assessment.
5. If there is disagreement, state the disagreement and the evidence needed to resolve it.

Do not claim consensus unless both agents reached the same conclusion for compatible reasons.

## Common mistakes

| Mistake | Why it is wrong |
| --- | --- |
| Running `codex exec` from Codex | Recursive. Warn and stop instead. |
| Omitting `codex exec` | Can start an interactive session that never returns. |
| Adding token or budget caps | Violates the no-budget-limit requirement and can truncate the consultation. |
| Using a short timeout | `xhigh` runs may be killed before they finish. |
| Lowering the model or effort because the run is slow | Changes the requested consultation quality without user approval. |
| Hiding Codex disagreement | The user asked for cross-agent judgment, not artificial consensus. |
