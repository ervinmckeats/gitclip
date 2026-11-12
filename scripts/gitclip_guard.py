#!/usr/bin/env python3
"""gitclip guard: a PreToolUse hook that blocks git/GitHub actions breaking the gitclip rules.

Reads the hook JSON on stdin. Exit 0 = no objection, exit 2 = blocked (reason on stderr).
Internal errors fail open (exit 0) so a bug never locks the agent out of the shell.

User-only overrides (an agent cannot set these from inside a session):
  GITCLIP_ALLOW_ACTIONS=1             environment of the Claude Code process: allow GitHub Actions work
  GITCLIP_PROTECTED_BRANCHES=a,b      environment: extra protected branch names (main,master always)
  git config gitclip.allowAiFiles true   per repository: allow committing AI tooling files
"""
import json
import os
import re
import shlex
import subprocess
import sys

TYPES = r"(feat|fix|add|del|docs)"
SUBJECT_RE = re.compile(rf"^{TYPES}: \S")
BRANCH_RE = re.compile(rf"^{TYPES}/[a-z0-9]+(-[a-z0-9]+)*$")
MAX_SUBJECT = 50  # characters after "type: "

AI_WORDS = r"claude|anthropic|copilot|chatgpt|openai|gemini|codex|cursor|windsurf|devin"
AI_TRAILER_RE = re.compile(
    rf"(?im)^\s*co-authored-by:.*({AI_WORDS}|noreply@)|generated (with|by) \S|🤖|claude\.ai/code|^\s*claude-session:"
)
AI_NAME_RE = re.compile(rf"(?i)\b({AI_WORDS})\b")
AI_IDENTITY_RE = re.compile(rf"(?i)({AI_WORDS}|\bbot\b|\[bot\]|ai-agent|noreply@anthropic|noreply@openai)")
AI_FILE_RE = re.compile(
    r"(^|/)(CLAUDE(\.local)?\.md|AGENTS\.md|GEMINI\.md|COPILOT\.md|\.cursorrules|\.windsurfrules|\.clinerules"
    r"|\.aider[^/]*|copilot-instructions\.md)$"
    r"|(^|/)\.(claude|agents|cursor|continue|codex|gemini|claude-plugin)(/|$)"
)
WORKFLOW_RE = re.compile(r"(^|/)\.github/workflows(/|$)")
SEPARATORS = {"&&", "||", ";", "|", "&", "\n", "(", ")"}


class Blocked(Exception):
    pass


def block(reason, hint=""):
    raise Blocked(f"gitclip: BLOCKED - {reason}" + (f"\nHow to fix: {hint}" if hint else ""))


def run_git(cwd, *args):
    try:
        out = subprocess.run(["git", "-C", cwd, *args], capture_output=True, text=True, timeout=10)
        return out.stdout.strip() if out.returncode == 0 else ""
    except Exception:
        return ""


def protected_branches(cwd):
    names = {"main", "master"}
    names.update(b.strip() for b in os.environ.get("GITCLIP_PROTECTED_BRANCHES", "").split(",") if b.strip())
    head = run_git(cwd, "symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD")
    if head.startswith("origin/"):
        names.add(head[len("origin/"):])
    return names


def allow_actions():
    return os.environ.get("GITCLIP_ALLOW_ACTIONS") == "1"


def allow_ai_files(cwd):
    return run_git(cwd, "config", "--get", "gitclip.allowAiFiles").lower() == "true"


# ---------- message checks ----------

def check_message(msg, what="commit message"):
    if not msg or not msg.strip():
        return
    lines = msg.strip("\n").splitlines()
    subject = lines[0].strip()
    if not SUBJECT_RE.match(subject):
        block(f'{what} "{subject}" does not match "type: text" with type feat|fix|add|del|docs',
              'use e.g. "feat: add user profile page" (colon + space, no slash, no scope)')
    rest = subject.split(": ", 1)[1]
    if len(rest) > MAX_SUBJECT:
        block(f"{what} subject is {len(rest)} chars after the prefix (max {MAX_SUBJECT})", "shorten it")
    if subject.endswith("."):
        block(f"{what} subject ends with a period", "remove the trailing period")
    check_no_ai(msg, what)


def check_no_ai(text, what):
    if AI_TRAILER_RE.search(text or ""):
        block(f"{what} contains AI attribution (Co-Authored-By / Generated with / session link)",
              "remove every AI trailer and footer; the user is the only author")
    m = AI_NAME_RE.search(text or "")
    if m:
        block(f'{what} mentions an AI product or vendor ("{m.group(0)}")', "describe the change without AI names")
    check_private(text, what)


EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+")
SAFE_EMAIL_RE = re.compile(r"(?i)@(users\.noreply\.github\.com|example\.(com|org|net))$")
PRIVATE_RES = [
    (re.compile(r"(?i)(/Users/|/home/|[A-Z]:\\\\?Users\\\\?)[A-Za-z0-9._-]+"), "a local home folder path"),
    (re.compile(r"(?i)\b(claude\.ai/(chat|code|share|project)|chatgpt\.com/(c|share)|chat\.openai\.com|gemini\.google\.com/app)\S*"),
     "a link to an AI chat or session"),
    (re.compile(r"(?<![\w.#/-])\+?\d[\d ()-]{8,}\d(?![\w.-])"), "a phone-like number"),
    (re.compile(r"[Ѐ-ӿ]"), "non-English text (Cyrillic), likely copied from a conversation"),
]


def check_private(text, what):
    """Rule 8: no personal data or conversation content in git text."""
    text = text or ""
    for m in EMAIL_RE.finditer(text):
        if not SAFE_EMAIL_RE.search(m.group(0)):
            block(f'{what} contains an email address ("{m.group(0)}")',
                  "remove personal data; describe the change, not who asked for it")
    for rx, label in PRIVATE_RES:
        m = rx.search(text)
        if m:
            block(f'{what} contains {label} ("{m.group(0)[:40]}")',
                  "remove personal data and conversation content; git text describes the change only")


# ---------- parsing ----------

HEREDOC_RE = re.compile(r"<<-?\s*(['\"]?)(\w+)\1[^\n]*\n(.*?)\n[ \t]*\2[ \t]*(?=\n|$)", re.S)


def strip_heredocs(cmd):
    bodies = []

    def repl(m):
        bodies.append(m.group(3))
        return f"<<HEREDOC{len(bodies) - 1}"

    return HEREDOC_RE.sub(repl, cmd), bodies


def segments(cmd):
    lex = shlex.shlex(cmd, posix=True, punctuation_chars=";&|()\n")
    lex.whitespace = " \t\r"
    lex.whitespace_split = True
    seg, out = [], []
    for tok in lex:
        if tok in SEPARATORS or set(tok) <= set(";&|()\n"):
            if seg:
                out.append(seg)
            seg = []
        else:
            seg.append(tok)
    if seg:
        out.append(seg)
    return out


def resolve_heredoc(value, bodies):
    m = re.search(r"<<HEREDOC(\d+)", value or "")
    return bodies[int(m.group(1))] if m else value


def option_values(args, shorts, longs):
    vals, i = [], 0
    while i < len(args):
        a = args[i]
        if a in shorts or a in longs:
            if i + 1 < len(args):
                vals.append(args[i + 1])
            i += 2
            continue
        for s in shorts:
            if a.startswith(s) and len(a) > len(s) and not a.startswith("--"):
                vals.append(a[len(s):])
        for lo in longs:
            if a.startswith(lo + "="):
                vals.append(a[len(lo) + 1:])
        i += 1
    return vals


def positional(args, takes_value=()):
    out, i = [], 0
    while i < len(args):
        a = args[i]
        if a in takes_value:
            i += 2
            continue
        if not a.startswith("-"):
            out.append(a)
        i += 1
    return out


# ---------- git subcommands ----------

def check_identity(cwd, configs):
    name = configs.get("user.name") or run_git(cwd, "config", "user.name")
    email = configs.get("user.email") or run_git(cwd, "config", "user.email")
    if not name or not email:
        block("git user.name / user.email are not set", "ask the user for their name and email, then set them with git config in this repository")
    if AI_IDENTITY_RE.search(name) or AI_IDENTITY_RE.search(email):
        block(f'git identity "{name} <{email}>" looks like an AI or bot',
              "ask the user for their own name and email and set them with git config in this repository")
    for var in ("GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL", "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL"):
        if AI_IDENTITY_RE.search(os.environ.get(var, "")):
            block(f"{var} is set to an AI identity", "unset it; commits must be authored by the user")


def git_commit(args, cwd, configs, bodies):
    if "--no-verify" in args or "-n" in args:
        block("commit with --no-verify skips the repository's checks", "commit without --no-verify")
    for author in option_values(args, (), ("--author",)):
        if AI_IDENTITY_RE.search(author):
            block(f'commit --author "{author}" is an AI identity', "commits must be authored by the user")
    check_identity(cwd, configs)
    branch = run_git(cwd, "rev-parse", "--abbrev-ref", "HEAD")
    if branch and branch in protected_branches(cwd):
        block(f'committing directly on protected branch "{branch}"',
              "create a branch first: git switch -c <feat|fix|add|del|docs>/<short-description>")
    msgs = [resolve_heredoc(v, bodies) for v in option_values(args, ("-m",), ("--message",))]
    for f in option_values(args, ("-F",), ("--file",)):
        if f == "-":
            msgs.extend(bodies)
            continue
        path = f if os.path.isabs(f) else os.path.join(cwd, f)
        try:
            with open(path, encoding="utf-8") as fh:
                msgs.append(fh.read())
        except Exception:
            pass
    if msgs:
        check_message("\n\n".join(m for m in msgs if m))
    staged = run_git(cwd, "diff", "--cached", "--name-only").splitlines()
    if "-a" in args or "--all" in args or any(re.match(r"^-[a-zA-Z]*a", a) for a in args if not a.startswith("--")):
        staged += run_git(cwd, "diff", "--name-only").splitlines()
    check_ai_files(staged, cwd, "staged for commit")


def check_ai_files(paths, cwd, where):
    if allow_ai_files(cwd):
        return
    bad = sorted({p for p in paths if AI_FILE_RE.search(p)})
    if bad:
        block(f"AI agent files {where}: {', '.join(bad)}",
              "unstage them (git restore --staged <file>) and add them to .git/info/exclude; never commit AI agent files")


def git_add(args, cwd):
    explicit = [a for a in positional(args) if a not in (".", "-A")]
    check_ai_files([os.path.normpath(a) for a in explicit], cwd, "being added")


def check_branch_name(name, cwd, action):
    if name in protected_branches(cwd):
        return
    if not BRANCH_RE.match(name):
        block(f'{action} branch "{name}" does not match type/short-description',
              "use e.g. feat/user-profile, fix/login-crash, add/lint-config, del/legacy-api, docs/setup-guide")


def git_branch_create(sub, args, cwd):
    if sub in ("checkout", "switch"):
        flags = ("-b", "-B") if sub == "checkout" else ("-c", "-C", "--create", "--force-create")
        for v in option_values(args, flags, ()):
            check_branch_name(v, cwd, "creating")
    elif sub == "branch":
        if any(a in ("-d", "-D", "--delete") for a in args):
            for b in positional(args):
                if b in protected_branches(cwd):
                    block(f'deleting protected branch "{b}"', "never delete the default branch")
            return
        if any(a in ("-m", "-M", "--move", "-c", "-C", "--copy") for a in args):
            pos = positional(args)
            if pos:
                check_branch_name(pos[-1], cwd, "renaming to")
            return
        if any(a.startswith("-") and a not in ("-f", "--force", "-t", "--track", "--no-track") for a in args):
            return  # listing / querying
        pos = positional(args)
        if pos:
            check_branch_name(pos[0], cwd, "creating")
    elif sub == "worktree" and args[:1] == ["add"]:
        for v in option_values(args[1:], ("-b", "-B"), ()):
            check_branch_name(v, cwd, "creating")


def unpushed_range(cwd, branch):
    if run_git(cwd, "rev-parse", "--verify", "--quiet", "@{u}"):
        return "@{u}..HEAD"
    for base in ("origin/HEAD", "origin/main", "origin/master"):
        if run_git(cwd, "rev-parse", "--verify", "--quiet", base):
            return f"{base}..HEAD"
    return ""


def git_push(args, cwd):
    if "--no-verify" in args:
        block("push with --no-verify skips the repository's checks", "push without --no-verify")
    prot = protected_branches(cwd)
    force = any(a in ("--force", "-f") or a.startswith("--force-with-lease") or a == "--force-if-includes"
                or (re.match(r"^-[a-zA-Z]*f", a) and not a.startswith("--")) for a in args)
    deleting = "--delete" in args or "-d" in args
    pos = positional(args, takes_value=("-o", "--push-option", "--repo"))
    refspecs = pos[1:] if pos else []
    branch = run_git(cwd, "rev-parse", "--abbrev-ref", "HEAD")
    targets = []
    for spec in refspecs:
        if spec.startswith("+"):
            force = True
            spec = spec[1:]
        dst = spec.split(":", 1)[1] if ":" in spec else spec
        if dst == "HEAD":
            dst = branch
        targets.append(dst.replace("refs/heads/", ""))
    if not refspecs and branch:
        targets.append(branch)
    for t in targets:
        if t in prot:
            block(f'pushing {"(delete) " if deleting else ""}to protected branch "{t}"',
                  "push a type/short-description branch and open a pull request instead")
        if t and not deleting and not t.startswith("refs/tags/"):
            check_branch_name(t, cwd, "pushing")
    if force:
        block("force push", "do not rewrite pushed history; ask the user first")
    rng = unpushed_range(cwd, branch)
    if rng:
        idents = run_git(cwd, "log", "--format=%an <%ae>|%cn <%ce>", rng).splitlines()
        for ident in idents:
            if AI_IDENTITY_RE.search(ident):
                block(f"unpushed commit authored/committed as {ident}",
                      "rewrite the unpushed commits with the user's identity (git commit --amend --reset-author / git rebase -i)")
        bodies = run_git(cwd, "log", "--format=%B%n----", rng)
        if AI_TRAILER_RE.search(bodies):
            block("unpushed commits contain AI attribution trailers", "remove them with git commit --amend / git rebase -i before pushing")
        for subj in run_git(cwd, "log", "--format=%s", rng).splitlines():
            if subj.startswith(("Merge ", "Revert ")):
                continue
            check_message(subj, "unpushed commit message")


def git_config(args, cwd):
    joined = " ".join(args)
    if "gitclip." in joined:
        block("agents may not change gitclip settings", "only the user changes gitclip.* settings")
    if "--global" in args or "--system" in args:
        if re.search(r"\buser\.(name|email)\b", joined) and len(positional(args)) >= 2:
            block("changing the global git identity", "set the identity per repository, after asking the user")
    pos = positional(args, takes_value=("--file", "-f"))
    if len(pos) >= 2 and pos[0] in ("user.name", "user.email") and AI_IDENTITY_RE.search(pos[1]):
        block(f'setting {pos[0]} to an AI identity "{pos[1]}"', "use the user's own name and email")


def check_git(tokens, cwd, bodies):
    i, configs = 1, {}
    while i < len(tokens) and tokens[i].startswith("-"):
        if tokens[i] == "-C" and i + 1 < len(tokens):
            nxt = tokens[i + 1]
            cwd = nxt if os.path.isabs(nxt) else os.path.join(cwd, nxt)
            i += 2
        elif tokens[i] == "-c" and i + 1 < len(tokens):
            k, _, v = tokens[i + 1].partition("=")
            configs[k.lower()] = v
            if k.lower() in ("user.name", "user.email") and AI_IDENTITY_RE.search(v):
                block(f'git -c {k}="{v}" is an AI identity', "commits must be authored by the user")
            i += 2
        else:
            i += 1
    if i >= len(tokens):
        return
    sub, args = tokens[i], tokens[i + 1:]
    if sub == "commit":
        git_commit(args, cwd, configs, bodies)
    elif sub == "add":
        git_add(args, cwd)
    elif sub in ("checkout", "switch", "branch", "worktree"):
        git_branch_create(sub, args, cwd)
    elif sub == "push":
        git_push(args, cwd)
    elif sub == "config":
        git_config(args, cwd)
    elif sub == "tag":
        for m in option_values(args, ("-m",), ("--message",)):
            check_no_ai(resolve_heredoc(m, bodies), "tag message")


def check_gh(tokens, cwd, bodies):
    args = tokens[1:]
    if not args:
        return
    group, rest = args[0], args[1:]
    action = rest[0] if rest else ""
    if group == "workflow" and action in ("run", "enable") or group == "run" and action in ("rerun",):
        if not allow_actions():
            block(f"gh {group} {action} triggers GitHub Actions", "only run Actions when the user explicitly asks in this conversation")
    if group == "api":
        joined = " ".join(rest)
        if re.search(r"/(dispatches|actions/workflows/[^ ]+/dispatches|actions/runs/\d+/(rerun|rerun-failed-jobs))", joined) and not allow_actions():
            block("gh api call triggers GitHub Actions", "only run Actions when the user explicitly asks")
    if group == "pr" and action in ("create", "edit"):
        for t in option_values(rest[1:], ("-t",), ("--title",)):
            check_message(resolve_heredoc(t, bodies), "PR title")
        for b in option_values(rest[1:], ("-b",), ("--body",)):
            body = resolve_heredoc(b, bodies)
            if AI_TRAILER_RE.search(body):
                block("PR body contains AI attribution", "remove the footer; the user is the only author")
            check_private(body, "PR body")
        for f in option_values(rest[1:], ("-F",), ("--body-file",)):
            path = f if os.path.isabs(f) else os.path.join(cwd, f)
            try:
                with open(path, encoding="utf-8") as fh:
                    check_no_ai(fh.read(), "PR body")
            except OSError:
                pass
    if group == "pr" and action == "merge":
        target = positional(rest[1:], takes_value=("-t", "--subject", "-b", "--body", "-F", "--body-file", "-R", "--repo", "--match-head-commit", "-A", "--author-email"))
        repo = option_values(rest[1:], ("-R",), ("--repo",))
        ref = target[0] if target else ""
        check_pr_before_merge(ref, repo[0] if repo else "", cwd)
    if group == "release" and action in ("create", "edit"):
        for n in option_values(rest[1:], ("-n",), ("--notes",)):
            check_no_ai(resolve_heredoc(n, bodies), "release notes")


MERGEABLE_PREFIXES = ("fix/", "docs/")
DOC_FILE_RE = re.compile(r"(?i)(\.(md|mdx|markdown|txt|rst|adoc)$|(^|/)(docs?|documentation)/|(^|/)(LICENSE|NOTICE|AUTHORS)(\.[a-z]+)?$)")


def check_pr_before_merge(ref, repo, cwd):
    """Agents may merge only fix/ and docs/ PRs, and only after the PR passes a full check."""
    cmd = ["gh", "pr", "view"] + ([ref] if ref else []) + (["--repo", repo] if repo else []) + [
        "--json", "headRefName,title,body,state,isDraft,mergeable,commits,files"]
    try:
        out = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=30)
        pr = json.loads(out.stdout) if out.returncode == 0 else None
    except Exception:
        pr = None
    if not pr:
        block("could not read the PR to check it before merging",
              "merging needs a successful PR check; leave the PR for the user")
    head = pr.get("headRefName", "")
    if not head.startswith(MERGEABLE_PREFIXES):
        block(f'merging PR "{head}" - agents may merge only fix/ and docs/ branches',
              "leave feature and key-change PRs open for the user to review and merge")
    if pr.get("isDraft") or pr.get("state") != "OPEN":
        block("PR is a draft or not open", "leave it for the user")
    if pr.get("mergeable") == "CONFLICTING":
        block("PR has merge conflicts", "resolve them first")
    check_message(pr.get("title", ""), "PR title")
    if not pr.get("title", "").startswith(head.split("/", 1)[0] + ": "):
        block(f'PR title type does not match branch "{head}"', "use the same type in the title and the branch name")
    check_no_ai(pr.get("body", ""), "PR description")
    for c in pr.get("commits", []):
        for a in c.get("authors", []):
            ident = f"{a.get('name', '')} <{a.get('email', '')}>"
            if AI_IDENTITY_RE.search(ident):
                block(f"PR commit authored by {ident}", "commits must be authored by the user")
        head_line = c.get("messageHeadline", "")
        if not head_line.startswith(("Merge ", "Revert ")):
            check_message(head_line, "PR commit message")
        check_no_ai(c.get("messageBody", ""), "PR commit message")
    files = [f.get("path", "") for f in pr.get("files", [])]
    check_ai_files(files, cwd, "in the PR")
    if WORKFLOW_RE.search("\n".join(files)):
        block("PR changes GitHub Actions workflows", "leave it for the user")
    if head.startswith("docs/"):
        other = [p for p in files if not DOC_FILE_RE.search(p)]
        if other:
            block(f"docs/ PR changes non-documentation files: {', '.join(other[:5])}",
                  "a docs/ PR may only touch documentation; leave it for the user")


def check_bash(cmd, cwd):
    if re.search(r"GITCLIP_ALLOW|gitclip\.allow", cmd):
        block("agents may not change gitclip overrides", "only the user sets GITCLIP_* / gitclip.* overrides")
    if re.search(r"(^|[\s;&|])(git|gh)\b", cmd) and AI_TRAILER_RE.search(cmd) and re.search(r"\b(commit|tag|pr|release)\b", cmd):
        block("command adds AI attribution to git or GitHub text", "remove every Co-Authored-By / Generated with / session-link line")
    stripped, bodies = strip_heredocs(cmd)
    try:
        segs = segments(stripped)
    except ValueError:
        return  # unparseable quoting: the regex check above still ran
    for seg in segs:
        while seg and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", seg[0]):
            name, _, val = seg[0].partition("=")
            if name.startswith("GIT_") and ("AUTHOR" in name or "COMMITTER" in name) and AI_IDENTITY_RE.search(val):
                block(f"{name} is set to an AI identity", "commits must be authored by the user")
            seg = seg[1:]
        if seg and seg[0] in ("sudo", "command", "env", "time", "nohup"):
            seg = seg[1:]
        if not seg:
            continue
        exe = os.path.basename(seg[0])
        if exe == "git":
            check_git(seg, cwd, bodies)
        elif exe == "gh":
            check_gh(seg, cwd, bodies)
        elif exe == "cd" and len(seg) > 1:
            cwd = seg[1] if os.path.isabs(seg[1]) else os.path.join(cwd, seg[1])


def check_file_tool(tool_input):
    path = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
    if WORKFLOW_RE.search(path.replace("\\", "/")) and not allow_actions():
        block(f"editing GitHub Actions workflow {path}", "only touch workflows when the user explicitly asks in this conversation")


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0
    tool = data.get("tool_name", "")
    tin = data.get("tool_input") or {}
    cwd = data.get("cwd") or os.getcwd()
    try:
        if tool == "Bash":
            check_bash(tin.get("command", ""), cwd)
        elif tool in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
            check_file_tool(tin)
    except Blocked as e:
        print(str(e), file=sys.stderr)
        return 2
    except Exception:
        return 0  # fail open on internal errors
    return 0


if __name__ == "__main__":
    sys.exit(main())
