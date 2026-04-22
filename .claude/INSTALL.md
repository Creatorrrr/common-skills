# Installing common-skills for Claude Code

This repository currently ships skills, not a published Claude marketplace plugin. The simplest global installation is to clone the repository once and link each skill into Claude Code's personal skills directory at `~/.claude/skills`.

## Prerequisites

- Claude Code
- Git

## Installation

1. Clone this repository into your Claude home directory.

   ```bash
   git clone https://github.com/Creatorrrr/common-skills.git ~/.claude/common-skills
   ```

2. Link the skill directories into Claude's global skills directory.

   ```bash
   mkdir -p ~/.claude/skills
   for skill_dir in ~/.claude/common-skills/skills/*; do
     ln -s "$skill_dir" ~/.claude/skills/"$(basename "$skill_dir")"
   done
   ```

3. Restart Claude Code so it reloads the global skills directory.

## Verify

```bash
ls -la ~/.claude/skills
```

You should see entries for:

- `gpt-pro-codebase-analysis`
- `claude-code-agent-team-analysis`

## Usage

After restart, Claude Code can discover the skills automatically when the task matches the skill descriptions. You can also name them directly:

- `gpt-pro-codebase-analysis`
- `claude-code-agent-team-analysis`

## Updating

```bash
cd ~/.claude/common-skills && git pull
```

The linked skills update in place after the pull.

## Uninstalling

```bash
for skill_dir in ~/.claude/common-skills/skills/*; do
  rm -f ~/.claude/skills/"$(basename "$skill_dir")"
done
rm -rf ~/.claude/common-skills
```
