#!/usr/bin/env python3
"""gitclip SessionStart hook: puts the gitclip rules summary into the session context."""
import json

SUMMARY = (
    "gitclip is active in this session. Git rules that apply to every git and GitHub action: "
    "commits are authored and committed only as the human user, with no AI names, Co-Authored-By trailers, "
    "'Generated with' footers or session links anywhere in git text; "
    "branches and forks are named type/short-description and commit messages and PR titles are 'type: text', "
    "where type is one of feat, fix, add, del, docs; all git text is short, imperative English; "
    "nothing is pushed directly to the default branch, feature and key-change PRs stay open for the user to merge, "
    "only fix/ and docs/ PRs may be merged by the agent, and only after checking the live PR title, description, commits and files; GitHub Actions are not created, edited or triggered unless the user asks "
    "in this conversation; AI agent files such as CLAUDE.md, AGENTS.md and .claude/ are never committed; "
    "every artifact produced for a project is also committed to its repository; git text never contains personal data or content from the conversation (no emails, phone numbers, home paths, chat links, names or quotes). "
    "The full rules are in the gitclip skill, which is loaded before the first git action. "
    "A PreToolUse hook blocks commands that break these rules."
)

print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": SUMMARY}}))
