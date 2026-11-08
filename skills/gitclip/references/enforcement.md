# gitclip — enforcement layers

A skill is guidance: an agent can still forget it. gitclip adds layers that **block** violations instead of hoping the agent remembers. Use as many as fit your setup.

| Layer | Where it runs | What it stops | Covers cloud sessions? |
|---|---|---|---|
| Skill (`SKILL.md`) | the agent's context | everything, by instruction | yes, when loaded |
| Claude Code plugin hooks | the user's machine, Claude Code | wrong names, AI trailers/identity, pushes to main, force pushes, `--no-verify`, merging PRs other than `fix/`/`docs/`, or ones whose live title, description, commits or files fail the PR check, Actions runs and workflow edits, AI files | no |
| `attribution` setting | the user's machine, Claude Code | the tool's own Co-Authored-By trailer and PR footer | no |
| git hooks (`commit-msg`, `pre-commit`, `pre-push`) | any machine with the hooks installed | names, AI trailers/identity, commits on main, AI files, pushes to main | only if installed there |
| GitHub rulesets | GitHub, server side | pushes to the default branch, force pushes, branch deletion, bad branch names, bad commit messages, AI trailers, AI author emails | **yes** — nothing bypasses them |

## 1. Claude Code plugin (hooks)

Installed with the plugin:

- **SessionStart** — injects a short summary of the rules at every session start, resume, `/clear`, and compaction, so the rules survive long sessions.
- **PreToolUse** on `Bash`, `Write`, `Edit`, `MultiEdit`, `NotebookEdit` — `scripts/gitclip_guard.py` parses the command and exits with code 2 (blocked, reason shown to the agent) when a rule is broken. Internal errors fail open, so a bug never locks the shell.

User-only overrides (the guard refuses commands where the agent tries to set them):

| Override | Effect |
|---|---|
| `GITCLIP_ALLOW_ACTIONS=1` in the environment Claude Code starts with | allow GitHub Actions work for that run |
| `GITCLIP_PROTECTED_BRANCHES=develop,release` | protect more branches (default: `main`, `master`, and `origin/HEAD`) |
| `git config gitclip.allowAiFiles true` (per repository, run by the user) | allow AI tooling files, e.g. in a repository that publishes a skill |

## 2. Attribution setting

```bash
curl -fsSL https://raw.githubusercontent.com/ervinmckeats/gitclip/main/scripts/setup.sh | sh   # in Terminal on your own computer, not in a cloud session
```

or add this to `~/.claude/settings.json` by hand:

```json
{ "attribution": { "commit": "", "pr": "" } }
```

`includeCoAuthoredBy` is deprecated; use `attribution`.

## 3. git hooks (any tool)

```bash
sh scripts/install-git-hooks.sh            # current repository
sh scripts/install-git-hooks.sh --global   # all repositories (core.hooksPath)
```

## 4. GitHub rulesets (server side)

Import the JSON files from `templates/github-rulesets/` in **Settings → Rules → Rulesets → New ruleset → Import a ruleset**:

| File | Rules |
|---|---|
| `protect-default-branch.json` | no deletion, no force push, changes only through PRs, squash merge |
| `branch-names.json` | branch names must match `^(feat\|fix\|add\|del\|docs)/[a-z0-9-]+$` |
| `commit-messages.json` | subject must be `type: text`, ≤ 50 chars after the prefix |
| `no-ai-attribution.json` | rejects AI co-author trailers/footers and AI author emails |

Notes:

- Rulesets are available for public repositories on GitHub Free and for private repositories on GitHub Pro, Team, and Enterprise Cloud. Metadata rules (commit message, author email, branch name patterns) may not be available on every plan; GitHub shows what your plan supports when you import.
- Rulesets use RE2 regular expressions (no lookaheads). Start new rulesets in **Evaluate** mode to see what they would block, then switch to **Active**.
- With squash merge, the PR title becomes the commit message on the default branch, so write PR titles as `type: text`.
