# gitclip

**Use this skill when you want AI coding agents to follow strict git rules: commits only under your name, no AI co-author trailers, `feat/fix/add/del/docs` naming, PR-only changes to `main`, and no surprise CI runs.**

gitclip is an [Agent Skill](https://agentskills.io) and a Claude Code plugin. The skill tells the agent the rules; the plugin's hooks, optional git hooks, and GitHub rulesets **block** commands that break them, so you no longer have to check every commit by hand.

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![Agent Skills](https://img.shields.io/badge/agent--skills-compatible-green)
![Claude Code plugin](https://img.shields.io/badge/claude%20code-plugin-orange)

## Quick install

**Claude Code (plugin with enforcement hooks — recommended)**

```bash
/plugin marketplace add ervinmckeats/gitclip
/plugin install gitclip@gitclip
```

Then turn off the tool's own attribution trailer. Run this in **Terminal on your own computer** (not in a cloud session — there the setting is lost when the session ends, and the script refuses to run):

```bash
curl -fsSL https://raw.githubusercontent.com/ervinmckeats/gitclip/main/scripts/setup.sh | sh
```

**Any agent that supports Agent Skills (Codex, Cursor, Gemini CLI, OpenCode, …)**

```bash
npx skills add ervinmckeats/gitclip --skill gitclip
```

**Claude apps (web, desktop, mobile)**

Zip the `skills/gitclip` folder (the zip must contain the `gitclip/` folder with `SKILL.md` inside) and upload it in **Settings → Customize → Skills**. To make it load every time, add this line to your personal instructions or project instructions:

> Before any project or git work, load the gitclip skill and follow it strictly.

**Manual**

```bash
git clone https://github.com/ervinmckeats/gitclip
cp -r gitclip/skills/gitclip ~/.claude/skills/
```

## The rules

| # | Rule | In short |
|---|---|---|
| 1 | Authorship | Every commit is authored and committed by you. No `Co-Authored-By: <AI>`, no "Generated with", no session links, no AI names in git text. |
| 2 | Naming | Branches: `type/short-description`. Commits and PR titles: `type: text`. Types: `feat`, `fix`, `add`, `del`, `docs` — nothing else. |
| 3 | Language | English, imperative, ≤ 50 characters after the prefix, no trailing period. |
| 4 | Pull requests | Never push to `main`. Features and key changes stay as open PRs for you to merge; `fix/` and `docs/` PRs may be merged by the agent, only after a PR check (title, description, commits, files). |
| 5 | CI | No GitHub Actions created, edited, or triggered unless you ask in the conversation. |
| 6 | AI files | `CLAUDE.md`, `AGENTS.md`, `.claude/`, `.cursor/` and similar are never committed. |
| 7 | Artifacts | Everything the agent produces for a project (docs, designs, images, data) is committed to the repo, not left in the AI tool's cloud. |
| 8 | Privacy | No personal data or chat content in commits, branches, or PRs: no emails, phone numbers, home paths, chat links, people's names, or quotes from the conversation. |

Full text: [`skills/gitclip/SKILL.md`](skills/gitclip/SKILL.md). Examples: [`references/examples.md`](skills/gitclip/references/examples.md).

### Examples

```text
✅ feat/user-profile        ✅ feat: add user profile page
✅ fix/login-crash          ✅ fix: handle empty cart
✅ docs/setup-guide         ✅ docs: update install steps
❌ feature/UserProfile      ❌ Fixed the bug.
❌ claude/fix-login         ❌ chore: bump deps
❌ patch-1                  ❌ feat: add page + Co-Authored-By: <AI>
```

## Enforcement layers

| Layer | Blocks | Works in cloud sessions |
|---|---|---|
| Skill | everything, by instruction | yes, when loaded |
| Plugin hooks (`SessionStart` + `PreToolUse`) | bad names, AI trailers/identity, pushes to `main`, force push, `--no-verify`, merging PRs other than `fix/`/`docs/` or ones that fail the PR check, Actions, AI files | no (local Claude Code) |
| `attribution` setting via `setup.sh` | the tool's own trailer and PR footer | no (local Claude Code) |
| git hooks ([`templates/git-hooks`](templates/git-hooks)) | bad names, AI trailers/identity, commits on `main`, AI files | wherever installed |
| GitHub rulesets ([`templates/github-rulesets`](templates/github-rulesets)) | pushes to `main`, force push, bad branch names and messages, AI trailers, AI emails | **yes** |

Details and user-only overrides: [`references/enforcement.md`](skills/gitclip/references/enforcement.md).

```bash
sh scripts/install-git-hooks.sh --global   # git hooks for every repository
bash tests/test_guard.sh                   # run the hook test suite
```

## FAQ

**How do I stop Claude Code from adding `Co-Authored-By: Claude` to commits?**
Run the setup script above, or add `"attribution": {"commit": "", "pr": ""}` to `~/.claude/settings.json`. `includeCoAuthoredBy` is deprecated. gitclip's hooks also reject any commit that still carries an AI trailer.

**My agent ignores the skill. Why?**
Skills load when the agent decides they match the task. Install the plugin (its `SessionStart` hook injects the rules every session and its `PreToolUse` hook blocks violations), add the activation line to your instructions, and add the GitHub rulesets for anything the hooks cannot reach.

**Does it work in cloud sessions?**
Local settings and hooks do not reach cloud sessions. The skill and the GitHub rulesets do.

**Why not `chore`, `refactor`, `test`?**
Five types keep history scannable. Map them: tests, config, and dependencies → `add`; removals → `del`; behavior changes → `feat` or `fix`.

**Can I use different rules?**
Fork the repo and edit `SKILL.md`, the regexes in `scripts/gitclip_guard.py`, and the git hook templates.

## Compatibility

| Platform | Skill | Hooks |
|---|---|---|
| Claude Code (CLI, IDE, desktop) | ✅ | ✅ plugin |
| Claude apps (web, desktop, mobile) | ✅ upload | — |
| Codex, Cursor, Gemini CLI, OpenCode, other Agent Skills tools | ✅ `npx skills` | git hooks only |

Requires `python3` for the plugin hooks and `git` 2.20+.

## Contributing

Issues and pull requests are welcome. Follow the rules of this repo itself: `type/short-description` branches, `type: text` commits, run `bash tests/test_guard.sh` before opening a PR.

## License

[MIT](LICENSE)
