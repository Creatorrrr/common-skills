# common-skills for Gemini CLI

This extension provides two repository-analysis skill documents.

When a user asks for a deep codebase review, read the relevant skill file first and follow it:

- `skills/gpt-5.4-pro-codebase-analysis/SKILL.md`
  - Use for a second-opinion repository analysis with GPT-5.4 Pro.
  - This path supports two explicit execution modes: `responses_api` and `chatgpt_web_assisted`.
  - Require the user to choose one mode explicitly before execution.

- `skills/claude-code-agent-team-analysis/SKILL.md`
  - Use for a local read-only repository analysis using Claude Code CLI agent teams.
  - Use it for architecture reviews, test-gap analysis, performance review, workflow validation, and missing implementation checks.

General rules:

- Ground conclusions in concrete repository evidence.
- Distinguish confirmed findings from inference and unknowns.
- Do not silently switch execution modes after a failure.
- Prefer the skill file's workflow over ad-hoc analysis when the task matches it.
