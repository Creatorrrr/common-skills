# common-skills for Gemini CLI

This extension provides repository-analysis skill documents plus Codex CLI consultation guidance.

When a user asks for a deep codebase review, read the relevant skill file first and follow it:

- `skills/gpt-pro-codebase-analysis/SKILL.md`
  - Use for a second-opinion repository analysis through a GPT Pro workflow.
  - This path supports two explicit execution modes: `responses_api` and `chatgpt_web_assisted`.
  - Require the user to choose one mode explicitly before execution.

- `skills/claude-code-agent-team-analysis/SKILL.md`
  - Use for a local read-only repository analysis using Claude Code CLI agent teams.
  - Use it for architecture reviews, test-gap analysis, performance review, workflow validation, and missing implementation checks.

- `skills/consulting-codex-cli/SKILL.md`
  - Use when Gemini CLI, Claude Code, Antigravity, or another non-Codex agent should ask the local Codex CLI for a second opinion or back-and-forth consultation.
  - If this skill is invoked inside Codex, it must warn that Codex cannot recursively call itself and stop without running `codex exec`.

General rules:

- Ground conclusions in concrete repository evidence.
- Distinguish confirmed findings from inference and unknowns.
- Do not silently switch execution modes after a failure.
- Prefer the skill file's workflow over ad-hoc analysis when the task matches it.
- Do not let Codex invoke `codex exec` recursively.
