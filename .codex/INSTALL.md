# Installing common-skills for Codex

Enable these skills in Codex via native skill discovery: clone the repository, symlink the `skills/` directory into `~/.agents/skills`, then restart Codex.

## Prerequisites

- Codex
- Git

## Installation

1. Clone this repository into your Codex home directory.

   ```bash
   git clone https://github.com/Creatorrrr/common-skills.git ~/.codex/common-skills
   ```

2. Expose the skills to Codex.

   ```bash
   mkdir -p ~/.agents/skills
   ln -s ~/.codex/common-skills/skills ~/.agents/skills/common-skills
   ```

3. Restart Codex so it re-scans the global skills directory.

## Verify

```bash
ls -la ~/.agents/skills/common-skills
```

You should see a symlink pointing at `~/.codex/common-skills/skills`.

## Usage

After restart, Codex can discover these skills automatically. You can also call them explicitly with the namespace created by the symlink name:

- `common-skills:gpt-5.4-pro-codebase-analysis`
- `common-skills:claude-code-agent-team-analysis`

## Updating

```bash
cd ~/.codex/common-skills && git pull
```

## Uninstalling

```bash
rm ~/.agents/skills/common-skills
rm -rf ~/.codex/common-skills
```
