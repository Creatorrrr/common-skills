---
name: consulting-gemini-cli
description: Use when a non-Gemini agent wants to consult the local Gemini CLI for a second opinion, cross-agent dialogue, code review, design feedback, or "ask Gemini" request. Triggers include phrases like "gemini한테 물어봐", "gemini 의견", "Gemini와 cross-check", "ask gemini", "consult gemini", or any request to invoke `gemini -p`. If invoked from inside Gemini CLI, warn that Gemini cannot recursively call itself and stop.
---

# Consulting Gemini CLI

This skill lets Codex, Claude Code, Antigravity, or another non-Gemini agent invoke the local `gemini` CLI as a subprocess, collect Gemini's opinion, and compare it with the calling agent's own reasoning.

Gemini CLI sessions must not use this skill to invoke `gemini -p`. If the current agent is Gemini CLI and this skill is triggered, respond with a warning and stop.

## Core principles

1. The user's explicit instructions override these defaults.
2. If the current agent is Gemini CLI, say: `Gemini cannot use consulting-gemini-cli because it would recursively call Gemini. I will not run gemini -p from inside Gemini CLI.` Then stop.
3. Run Gemini non-interactively with `gemini -p` / `gemini --prompt` so the subprocess returns.
4. If the user does not specify a model, use `pro`.
5. Use YOLO approval mode by default: `--approval-mode=yolo`. This auto-approves Gemini CLI tool calls so it can inspect repositories directly in non-interactive consultations.
6. Do not pass token, budget, output-token, or thinking-budget caps.
7. Long waits are normal for large repositories or Pro-model reasoning. Do not impose short shell timeouts or retry just because output is slow.
8. Pass the user's prompt faithfully. Preserve constraints, paths, language, and requested output shape.
9. Present Gemini's response before synthesizing agreement or disagreement.
10. Unless the user explicitly says otherwise, Gemini operates on the same repository at the same working directory as the calling agent.
11. If the calling harness runs shell commands in a host sandbox, run real Gemini CLI calls through that harness's explicit unsandboxed/escalated execution path after user approval. Sandboxed calls can hide CLI auth state, browser integration, or normal home-directory session files.

## Resolve the bundled script

Prefer the bundled wrapper because it encodes the defaults above and avoids retyping CLI flags.

Resolve the script path in this order:

1. Start from the directory that contains this `SKILL.md`.
2. Use `scripts/consult_gemini_cli.sh` relative to that directory.
3. If the active workspace does not contain this skill, look in the installed skill location such as `~/.claude/skills/consulting-gemini-cli/`, the linked `common-skills/skills/consulting-gemini-cli/`, or the agent's global skill install path.

Do not assume `scripts/consult_gemini_cli.sh` is project-local unless the user has vendored this skill into that project.

## Defaults

| Option | Default | How it is passed |
| --- | --- | --- |
| Model | `pro` | `--model pro` |
| Approval mode | `yolo` | `--approval-mode=yolo` |
| Print mode | non-interactive | `-p` / `--prompt` |
| Output format | `text` | `--output-format text` |
| Workspace trust | current session only | `--skip-trust` |
| Working directory | caller's current `cwd` | inherited unless `--cd` is explicitly used |
| Extra directories | none | do not pass `--include-directories` unless the user names extra paths |
| Sandbox | Gemini CLI default | do not pass `--sandbox` unless the user asks |
| Budget/token caps | none | do not pass any cap flags |

If the user explicitly names another model, approval mode, working directory, output format, sandbox setting, or extra include directory, use that value and keep the remaining defaults.

## Canonical invocation

For a short prompt:

```bash
/path/to/consult_gemini_cli.sh "user prompt here"
```

For a detailed or shell-sensitive prompt, pass it through stdin:

```bash
/path/to/consult_gemini_cli.sh <<'PROMPT'
<user prompt verbatim>
PROMPT
```

For a repo-specific question, set the working directory:

```bash
/path/to/consult_gemini_cli.sh --cd /absolute/path/to/repo <<'PROMPT'
<question about this repository>
PROMPT
```

For an explicit model override:

```bash
/path/to/consult_gemini_cli.sh --model flash "user prompt here"
```

For an explicit lower-permission request, use the user's requested approval mode:

```bash
/path/to/consult_gemini_cli.sh --approval-mode plan <<'PROMPT'
<user explicitly requested read-only planning>
PROMPT
```

Use `--approval-mode plan`, `default`, or `auto_edit` only when the user explicitly asks for a lower-permission posture than the default.

## Browser authentication flow

Gemini CLI may require browser authentication before the first real `gemini -p` call can complete. If the command prints an auth prompt such as `Opening authentication page in your browser. Do you want to continue? [Y/n]:`, do not leave a non-interactive subprocess hanging.

Rules:

1. Make the risk explicit: this opens a browser login/consent flow for the local Gemini CLI, and a real Gemini request goes to an external Google service.
2. If the current user request already asks to consult Gemini, verify Gemini, authenticate Gemini, or open the Gemini auth page, do not ask a second "open the browser?" confirmation. State that auth smoke is starting and proceed.
3. Only ask before opening the browser when Gemini auth is incidental and the user has not asked for a real Gemini CLI call in the current turn.
4. For authentication, avoid sending repository context. Run the bundled wrapper's auth smoke mode from a neutral temp directory:

```bash
/path/to/consult_gemini_cli.sh --auth-smoke
```

The wrapper uses this minimal prompt:

```text
Reply exactly with: gemini-auth-ok
```

5. If the host supports an interactive TTY and Gemini prints the browser-auth prompt, answer `Y` so the authentication page opens for the user. The user completes login/consent in the browser.
6. If the host cannot provide a TTY or cannot open a browser, give the user the manual command instead:

```bash
cd /private/tmp
gemini -p "Reply exactly with: gemini-auth-ok" --model pro --approval-mode=yolo --output-format text --skip-trust
```

7. After auth smoke succeeds, rerun the original consultation prompt from the intended working directory.

Never start browser authentication from the repository directory with the real consultation prompt just to solve auth. Authenticate first with the neutral smoke prompt, then run the real consultation separately.

## Host sandbox and session recovery

Some harnesses run shell commands in a sandbox even when the target CLI itself is not sandboxed. This can make Gemini CLI look logged out or disconnected because it cannot read its normal credentials, use browser auth, or access session files.

Treat these as auth/session symptoms:

- `session revoked`
- `session expired`
- `logged out`
- `authentication required`
- repeated browser-auth prompts
- auth works in a normal terminal but fails from the agent harness

Rules:

1. If the current user request asks to consult Gemini, verify Gemini, authenticate Gemini, or run Gemini analysis, that request is permission to use the host's explicit unsandboxed/escalated execution path for the Gemini CLI subprocess. Do not ask a second natural-language confirmation, but do use the host tool's approval mechanism when it requires one.
2. In Codex, run the wrapper with `sandbox_permissions="require_escalated"` for both `--auth-smoke` and the real consultation. The justification should say that Gemini CLI needs normal local auth/browser/session access.
3. Use the same intended working directory rules as usual: `--auth-smoke` runs from `/private/tmp`; the real consultation runs from the caller's current `cwd` unless the user named another path.
4. If a sandboxed attempt fails with an auth/session symptom, stop that run. Do not keep retrying inside the sandbox.
5. Run one outside-sandbox `--auth-smoke` first. If it succeeds, retry the original Gemini consultation once outside the host sandbox.
6. If the outside-sandbox retry still says the session is revoked/expired/logged out, stop and surface the exact error. The user likely needs to complete Gemini CLI login or account recovery outside the agent flow.
7. Outside the host sandbox does not change Gemini CLI's own approval mode. Keep the wrapper default `yolo` unless the user explicitly asked for another mode.

## Waiting policy

`pro` can take many minutes on large or cross-cutting questions. Treat that as normal.

- Set a generous shell timeout. Use at least `3600000` ms when the host tool requires a timeout value.
- If the process is still running and there is no hard error, continue waiting.
- Do not launch duplicate Gemini consultations to speed up a slow run.
- Only treat the call as failed if `gemini` exits non-zero, reports authentication or quota failure, or the user cancels.

## Permission policy

Default to direct repository inspection:

```bash
--approval-mode=yolo
```

YOLO mode auto-approves Gemini CLI tool calls, including shell commands. This is deliberately less restrictive than plan mode so non-interactive consultations can read repositories directly without stopping on shell approval. Override only when the user explicitly asks for a different posture:

- `--approval-mode=plan` - read-only planning mode; can block shell-based repository inspection in non-interactive runs.
- `--approval-mode=default` - Gemini prompts for tool approvals; in non-interactive runs, approval prompts can become denials.
- `--approval-mode=auto_edit` - Gemini may auto-approve edit tools while prompting for other tools.
- `--approval-mode=yolo` - Gemini auto-approves all tool calls. This is this skill's default.

Do not use deprecated `--yolo`; use `--approval-mode=yolo`.

## How to use Gemini's response

Default behavior:

1. Run your own initial analysis enough to know what you are asking Gemini.
2. Invoke Gemini with the user's prompt and any necessary repo paths.
3. Show Gemini's response or a faithful summary, depending on the user's request.
4. Compare Gemini's answer with your own assessment.
5. If there is disagreement, state the disagreement and the evidence needed to resolve it.

Do not claim consensus unless both agents reached the same conclusion for compatible reasons.

## Common mistakes

| Mistake | Why it is wrong |
| --- | --- |
| Running `gemini -p` from Gemini CLI | Recursive. Warn and stop instead. |
| Omitting `-p` / `--prompt` | Can start an interactive session that never returns. |
| Adding token, thinking, or budget caps | Can truncate or weaken the consultation. |
| Using a short timeout | Pro-model runs may be killed before they finish. |
| Lowering the model because the run is slow | Changes the requested consultation quality without user approval. |
| Assuming `yolo` is read-only | It auto-approves tool calls, including shell commands. Use `--approval-mode plan` explicitly for read-only-only consultations. |
| Adding `--include-directories` proactively | Expands Gemini's read scope beyond what the user asked for. |
| Opening browser auth with the real repo prompt | Sends more context than needed for login. Use `--auth-smoke` first. |
| Retrying session errors inside the host sandbox | Repeats the same broken auth environment. Use approved outside-sandbox auth smoke, then retry once. |
| Hiding Gemini disagreement | The user asked for cross-agent judgment, not artificial consensus. |

## Notes for the calling agent

- This skill is one-shot per request. If the user asks for an ongoing back-and-forth, run `gemini -p ...` once per turn and keep the conversation transcript on the caller side.
- If `gemini` is not on PATH, surface the error to the user rather than guessing an install location.
- The default scope is the caller's current repository at its current path. Treat any other repo or path as opt-in: the user must name it explicitly before you `cd` or pass `--include-directories`.
- If you are Gemini CLI, you reached this file by mistake. Stop following it and answer using your own reasoning.
