# Installing common-skills for Antigravity

Enable these skills in Antigravity via native skill discovery: clone the repository, symlink the `skills/` directory into `~/.gemini/antigravity/skills`, then restart Antigravity.

## Prerequisites

- Antigravity
- Git

## Installation

1. Clone this repository into your Antigravity home directory.

   ```bash
   git clone https://github.com/Creatorrrr/common-skills.git ~/.gemini/antigravity/common-skills
   ```

2. Expose the skills to Antigravity.

   ```bash
   mkdir -p ~/.gemini/antigravity/skills
   ln -s ~/.gemini/antigravity/common-skills/skills ~/.gemini/antigravity/skills/common-skills
   ```

3. Restart Antigravity so it re-scans the global skills directory.

## Verify

```bash
ls -la ~/.gemini/antigravity/skills/common-skills
```

You should see a symlink pointing at `~/.gemini/antigravity/common-skills/skills`.

## Usage

After restart, Antigravity can discover these skills automatically. You can also call them explicitly with the namespace created by the symlink name:

- `common-skills:gpt-pro-codebase-analysis`
- `common-skills:claude-code-agent-team-analysis`

## Updating

```bash
cd ~/.gemini/antigravity/common-skills && git pull
```

## Uninstalling

```bash
rm ~/.gemini/antigravity/skills/common-skills
rm -rf ~/.gemini/antigravity/common-skills
```
