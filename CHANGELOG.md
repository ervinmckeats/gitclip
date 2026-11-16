# Changelog

## 1.3.0

- feat: rule 9, release tags vX.Y.Z on merged commits
- fix: guard no longer treats tag pushes as branch pushes
- fix: git push --tags no longer counts as a push to main

## 1.2.0

- feat: rule 8, no personal data or chat content in git text
- feat: guard blocks emails, phone numbers, home paths, chat links and non-English text in commits and PRs

## 1.1.0

- feat: allow agents to merge docs/ PRs after a PR check
- feat: check live PR title, description, commits and files before any merge

## 1.0.0

- add: gitclip skill with 7 rules, examples, and enforcement guide
- add: Claude Code plugin with SessionStart and PreToolUse hooks
- add: setup script that turns off AI attribution in Claude Code settings
- add: git hook templates and installer
- add: GitHub ruleset templates
- add: guard test suite
