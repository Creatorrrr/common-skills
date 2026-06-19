---
name: consulting-antigravity-cli
description: Use when a non-Antigravity agent wants to consult the local Antigravity CLI for a second opinion, cross-agent dialogue, code review, design feedback, or "ask Antigravity" request. Triggers include phrases like "antigravity한테 물어봐", "antigravity 의견", "Antigravity와 cross-check", "ask antigravity", "consult antigravity", "agy한테 물어봐", or any request to invoke `agy -p`. If invoked from inside Antigravity CLI, warn that Antigravity cannot recursively call itself and stop.
---

# Consulting Antigravity CLI

This skill lets Codex, Claude Code, legacy Gemini CLI, or another non-Antigravity agent invoke the local `agy` CLI as a subprocess, collect Antigravity's opinion, and compare it with the calling agent's own reasoning.

Antigravity CLI sessions must not use this skill to invoke `agy -p`. If the current agent is Antigravity CLI and this skill is triggered, respond with a warning and stop.

## Core principles

1. The user's explicit instructions override these defaults.
2. If the current agent is Antigravity CLI, say: `Antigravity cannot use consulting-antigravity-cli because it would recursively call Antigravity. I will not run agy -p from inside Antigravity CLI.` Then stop.
3. Run Antigravity non-interactively with `agy -p` so the subprocess returns.
4. If the user does not specify a model, use the Antigravity CLI default by omitting `--model`. Pass explicit model names exactly as the user provides them.
5. Default to Antigravity's no-confirmation mode: `--dangerously-skip-permissions`. This auto-approves tool calls so Antigravity can inspect repositories directly in non-interactive consultations.
6. Do not pass token, budget, output-token, or thinking-budget caps.
7. Long waits are normal for large repositories or high-reasoning model runs. Do not impose short shell timeouts or retry just because output is slow.
8. Pass the user's prompt faithfully. Preserve constraints, paths, language, and requested output shape.
9. Present Antigravity's response before synthesizing agreement or disagreement.
10. Unless the user explicitly says otherwise, Antigravity operates on the same repository at the same working directory as the calling agent.
11. If the calling harness runs shell commands in a host sandbox that hides normal auth/session files, use that harness's approved normal-local execution path for real Antigravity CLI calls after user approval.

## Resolve the bundled script

Prefer the bundled wrapper because it encodes the defaults above and avoids retyping CLI flags.

Resolve the script path in this order:

1. Start from the directory that contains this `SKILL.md`.
2. Use `scripts/consult_antigravity_cli.sh` relative to that directory.
3. If the active workspace does not contain this skill, look in the installed skill location such as `~/.claude/skills/consulting-antigravity-cli/`, the linked `common-skills/skills/consulting-antigravity-cli/`, or the agent's global skill install path.

Do not assume `scripts/consult_antigravity_cli.sh` is project-local unless the user has vendored this skill into that project.

## Defaults

| Option | Default | How it is passed |
| --- | --- | --- |
| Model | Antigravity CLI default | no `--model` argument |
| Permission mode | no confirmation | `--dangerously-skip-permissions` |
| Print mode | non-interactive | `-p` |
| Output format | Antigravity CLI default | no `--output-format` argument |
| Workspace trust | Antigravity trusted-workspace settings | no headless trust-bypass flag |
| Working directory | caller's current `cwd` | inherited unless `--cd` is explicitly used |
| Extra directories | none | no include-directory flag is passed |
| Sandbox | Antigravity CLI default | no `--sandbox` unless the user asks |
| Budget/token caps | none | do not pass any cap flags |

If the user explicitly names another model, working directory, sandbox setting, or permission posture, use that value and keep the remaining defaults.

Antigravity CLI does not expose the old Gemini CLI `--skip-trust` behavior as a documented headless trust bypass. If Antigravity rejects a workspace as untrusted, have the user trust the folder through Antigravity's interactive flow or configured trusted-workspace settings. Do not silently edit Antigravity settings files.

Model handling accepted by the wrapper:

- `default` or `cli-default` -> omit `--model` and let Antigravity CLI choose
- any other value -> pass through exactly as `--model <value>`

## Canonical invocation

For a short prompt:

```bash
/path/to/consult_antigravity_cli.sh "user prompt here"
```

For a detailed or shell-sensitive prompt, pass it through stdin:

```bash
/path/to/consult_antigravity_cli.sh <<'PROMPT'
<user prompt verbatim>
PROMPT
```

For a repo-specific question, set the working directory:

```bash
/path/to/consult_antigravity_cli.sh --cd /absolute/path/to/repo <<'PROMPT'
<question about this repository>
PROMPT
```

For an explicit model override:

```bash
/path/to/consult_antigravity_cli.sh --model "Gemini 3.5 Flash (High)" "user prompt here"
```

For an explicit lower-permission request, use the user's requested posture:

```bash
/path/to/consult_antigravity_cli.sh --permission-mode request-review <<'PROMPT'
<user explicitly requested approval prompts>
PROMPT
```

Use `--permission-mode request-review`, `strict`, or `sandbox` only when the user explicitly asks for a lower-permission posture than the default. The wrapper omits `--dangerously-skip-permissions` for these modes. `--permission-mode sandbox` also passes `--sandbox`.

## File, image, and media analysis

Antigravity CLI can reference local workspace files from prompts, but this wrapper does not automatically forward chat attachments from the calling chat UI. The wrapper sends text to `agy -p`; Antigravity only receives local file content when the prompt uses Antigravity file-context syntax and the file is readable from the consultation workspace.

Rules for file, image, audio, video, and PDF analysis:

1. Resolve the real local filesystem path first. Do not assume a chat attachment, Markdown image, or plain path string is available to the Antigravity subprocess.
2. Use `@path` syntax in the prompt for every file Antigravity must inspect. A plain path such as `/tmp/image.png` is only text; `@image.png` is file context when Antigravity can resolve it.
3. Prefer `--cd` to a directory that contains the file, then reference the file with a relative `@` path:

```bash
/path/to/consult_antigravity_cli.sh --cd /absolute/path/to/images <<'PROMPT'
Analyze this image: @image.png
PROMPT
```

4. Escape spaces and shell-sensitive characters inside the `@` path. For example:

```text
Analyze this image: @generated\ image\ 1.png
```

5. Do not rely on unsupported include-directory flags. If Antigravity cannot see a file outside the workspace, move the consultation working directory to the correct folder or ask the user to configure/trust that workspace explicitly.
6. Do not rely on `@directory/` to include media. For visual or document analysis, name each file directly: `@a.png @b.jpg @brief.pdf`.
7. If Antigravity says it cannot see or analyze the file, inspect the invocation before blaming the model: check that the prompt used `@`, the file existed, spaces were escaped, the path was inside Antigravity's workspace, and the file was not ignored by `.gitignore` or `.antigravityignore`.
8. If Antigravity rejects the file directory as untrusted, surface the error. Do not silently retry with a broader workspace or edit trusted-workspace settings.

For a quick visual smoke, ask Antigravity to prove it received the image:

```bash
/path/to/consult_antigravity_cli.sh --cd /absolute/path/to/images <<'PROMPT'
Look at @image.png. Start your answer with VISUAL_OK if you can see it, or VISUAL_NOT_AVAILABLE if you cannot. Then summarize the visible subject in one sentence.
PROMPT
```

## Authentication and trust flow

Antigravity CLI may require interactive Google authentication, terms acceptance, model setup, or workspace trust before a real `agy -p` call can complete. If the command opens an interactive login or trust flow, do not leave a non-interactive subprocess hanging.

Rules:

1. Make the risk explicit: this opens a local Antigravity login/consent flow, and a real Antigravity request goes to an external Google service.
2. If the current user request already asks to consult Antigravity, verify Antigravity, authenticate Antigravity, or open the Antigravity auth page, do not ask a second confirmation. State that auth smoke is starting and proceed.
3. Only ask before opening the browser when Antigravity auth is incidental and the user has not asked for a real Antigravity CLI call in the current turn.
4. For authentication smoke checks, avoid sending repository context. Run the bundled wrapper's auth smoke mode from a neutral temp directory:

```bash
/path/to/consult_antigravity_cli.sh --auth-smoke
```

The wrapper uses this minimal prompt:

```text
Reply exactly with: antigravity-auth-ok
```

5. If the host supports an interactive TTY and Antigravity prompts for login, terms, or folder trust, let the user complete that flow.
6. If the host cannot provide a TTY or cannot open a browser, give the user the manual command instead:

```bash
cd /private/tmp
agy
```

Then have the user complete login/setup interactively before rerunning the real consultation.

Never start browser authentication from the repository directory with the real consultation prompt just to solve auth. Authenticate first with the neutral smoke prompt or an interactive `agy` session, then run the real consultation separately.

## Host sandbox and session recovery

Some harnesses run shell commands in a sandbox even when the target CLI itself is not sandboxed. This can make Antigravity CLI look logged out or disconnected because it cannot read its normal credentials, use browser auth, or access session files.

Treat these as auth/session symptoms:

- `session revoked`
- `session expired`
- `logged out`
- `authentication required`
- `not signed in`
- repeated browser-auth prompts
- auth works in a normal terminal but fails from the agent harness

Rules:

1. If the current user request asks to consult Antigravity, verify Antigravity, authenticate Antigravity, or run Antigravity analysis, that request is permission to use the host's approved normal-local execution path for the Antigravity CLI subprocess. Do not ask a second natural-language confirmation, but do use the host tool's approval mechanism when it requires one.
2. Use the same intended working directory rules as usual: `--auth-smoke` runs from `/private/tmp`; the real consultation runs from the caller's current `cwd` unless the user named another path.
3. If a sandboxed attempt fails with an auth/session symptom, stop that run. Do not keep retrying inside the sandbox.
4. Run one normal-local `--auth-smoke` first. If it succeeds, retry the original Antigravity consultation once through that same normal-local path.
5. If the normal-local retry still says the session is revoked/expired/logged out/not signed in, stop and surface the exact error. The user likely needs to complete Antigravity CLI login or account recovery outside the agent flow.
6. Outside the host sandbox does not change Antigravity CLI's own permission mode. Keep the wrapper default `--dangerously-skip-permissions` unless the user explicitly asked for another mode.

## Waiting policy

Antigravity CLI default or high-reasoning model runs can take many minutes on large or cross-cutting questions. Treat that as normal.

- Set a generous shell timeout. Use at least `3600000` ms when the host tool requires a timeout value.
- If the process is still running and there is no hard error, continue waiting.
- Do not launch duplicate Antigravity consultations to speed up a slow run.
- Only treat the call as failed if `agy` exits non-zero, reports authentication/quota failure, or the user cancels.

## Permission policy

Default to direct repository inspection:

```bash
--dangerously-skip-permissions
```

This mode auto-approves tool calls, including shell commands. This is deliberately less restrictive than request-review mode so non-interactive consultations can read repositories directly without stopping on tool approvals. Override only when the user explicitly asks for a different posture:

- `--permission-mode request-review` - omit the dangerous skip flag and rely on Antigravity's configured approval prompts.
- `--permission-mode strict` - omit the dangerous skip flag and rely on Antigravity's strict configuration when available.
- `--permission-mode sandbox` - pass `--sandbox` and omit the dangerous skip flag.
- `--permission-mode always-proceed` or `--dangerously-skip-permissions` - auto-approve tool calls.

Do not use Gemini CLI's deprecated `--approval-mode` examples in new instructions. The wrapper accepts `--approval-mode yolo` as a compatibility alias for `--dangerously-skip-permissions`, but examples should use Antigravity terms.

## How to use Antigravity's response

Default behavior:

1. Run your own initial analysis enough to know what you are asking Antigravity.
2. Invoke Antigravity with the user's prompt and any necessary repo paths.
3. Show Antigravity's response or a faithful summary, depending on the user's request.
4. Compare Antigravity's answer with your own assessment.
5. If there is disagreement, state the disagreement and the evidence needed to resolve it.

Do not claim consensus unless both agents reached the same conclusion for compatible reasons.

## Common mistakes

| Mistake | Why it is wrong |
| --- | --- |
| Running `agy -p` from Antigravity CLI | Recursive. Warn and stop instead. |
| Omitting `-p` | Can start an interactive TUI session that never returns. |
| Adding token, thinking, or budget caps | Can truncate or weaken the consultation. |
| Using a short timeout | High-reasoning runs may be killed before they finish. |
| Lowering the model because the run is slow | Changes the requested consultation quality without user approval. |
| Assuming `--dangerously-skip-permissions` is read-only | It auto-approves tool calls, including shell commands. Use `--permission-mode request-review` or `sandbox` explicitly for lower-permission consultations. |
| Adding unsupported include-directory flags proactively | Expands or misrepresents Antigravity's read scope beyond what the user asked for. |
| Assuming chat file attachments are forwarded automatically | The wrapper only sends text to `agy -p`; use local `@path` file context. |
| Passing a file path without `@` | Antigravity receives a path string, not the file content. |
| Using `@directory/` and expecting media inside it to be analyzed | Binary assets may be skipped unless each file is explicitly named. |
| Forgetting to escape spaces in `@` paths | The file-context parser may stop at unescaped whitespace. |
| Opening browser auth with the real repo prompt | Sends more context than needed for login. Use `--auth-smoke` or an interactive `agy` setup first. |
| Retrying session errors inside the host sandbox | Repeats the same broken auth environment. Use normal-local auth smoke, then retry once. |
| Hiding Antigravity disagreement | The user asked for cross-agent judgment, not artificial consensus. |

## Notes for the calling agent

- This skill is one-shot per request. If the user asks for an ongoing back-and-forth, run `agy -p ...` once per turn and keep the conversation transcript on the caller side.
- If `agy` is not on the current process PATH, the wrapper checks `CONSULT_ANTIGRAVITY_BIN`, `CONSULT_AGY_BIN`, then `command -v agy`/`antigravity`, then those commands through the user's login shell when `SHELL` is executable. Surface the final error if none are executable.
- The wrapper treats inherited Antigravity environment variables as weak signals when a known non-Antigravity caller is present; deliberate recursion blocks should use `CONSULT_ANTIGRAVITY_CLI_FROM_ANTIGRAVITY=1`.
- The default scope is the caller's current repository at its current path. Treat any other repo or path as opt-in: the user must name it explicitly before you `cd`.
- If you are Antigravity CLI, you reached this file by mistake. Stop following it and answer using your own reasoning.
