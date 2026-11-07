#!/usr/bin/env bash
# Smoke tests for scripts/gitclip_guard.py. Run: bash tests/test_guard.sh
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
GUARD="$ROOT/scripts/gitclip_guard.py"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

git -C "$TMP" init -q -b main
git -C "$TMP" config user.name "Jane Doe"
git -C "$TMP" config user.email "jane@example.com"
git -C "$TMP" commit -q --allow-empty -m "add: initial commit"
git -C "$TMP" switch -q -c feat/user-profile

pass=0; fail=0
run() { # expected(0|2) tool command
  local expect="$1" tool="$2" cmd="$3" input code
  if [ "$tool" = Bash ]; then
    input=$(jq -n --arg c "$cmd" --arg d "$TMP" '{tool_name:"Bash",tool_input:{command:$c},cwd:$d}')
  else
    input=$(jq -n --arg p "$cmd" --arg d "$TMP" '{tool_name:"Write",tool_input:{file_path:$p},cwd:$d}')
  fi
  echo "$input" | python3 "$GUARD" 2>/dev/null; code=$?
  if [ "$code" = "$expect" ]; then pass=$((pass+1)); else fail=$((fail+1)); echo "FAIL (want $expect got $code): $cmd"; fi
}

# allowed
run 0 Bash 'git status'
run 0 Bash 'git commit -m "feat: add user profile page"'
run 0 Bash 'git switch -c fix/login-crash'
run 0 Bash 'git checkout -b docs/setup-guide'
run 0 Bash 'npm test && git log --oneline'
run 0 Write "$TMP/src/app.ts"

# naming
run 2 Bash 'git commit -m "Fixed the bug."'
run 2 Bash 'git commit -m "fix/ handle empty cart"'
run 2 Bash 'git commit -m "chore: bump deps"'
run 2 Bash 'git commit -m "feat(auth): add sso"'
run 2 Bash 'git commit -m "feat: add a completely new and very detailed onboarding flow"'
run 2 Bash 'git switch -c feature/UserProfile'
run 2 Bash 'git checkout -b claude/fix-login'

# attribution
run 2 Bash "git commit -m \"feat: add page\" -m \"Co-Authored-By: Claude <noreply@anthropic.com>\""
run 2 Bash "$(printf 'git commit -F - <<EOF\nfeat: add page\n\nGenerated with Claude Code\nEOF')"
run 2 Bash 'git -c user.email=noreply@anthropic.com commit -m "feat: add page"'
run 2 Bash 'git commit --author="Claude <noreply@anthropic.com>" -m "feat: add page"'
run 2 Bash 'git config user.name "Claude"'
run 2 Bash 'gh pr create --title "feat: add page" --body "🤖 Generated with Claude Code"'

# PR / branch protection
run 2 Bash 'git push origin main'
run 2 Bash 'git push --force origin feat/user-profile'
run 2 Bash 'git commit --no-verify -m "feat: add page"'
run 2 Bash 'gh pr merge feat/user-profile --squash'
run 0 Bash 'gh pr merge fix/login-crash --squash --auto'

# actions
run 2 Bash 'gh workflow run build.yml'
run 2 Bash 'gh run rerun 123'
run 2 Write "$TMP/.github/workflows/build.yml"

# AI files
touch "$TMP/CLAUDE.md" && git -C "$TMP" add CLAUDE.md
run 2 Bash 'git commit -m "add: notes"'
git -C "$TMP" restore --staged CLAUDE.md
run 2 Bash 'git add CLAUDE.md .claude/settings.json'

# overrides cannot be set by the agent
run 2 Bash 'export GITCLIP_ALLOW_ACTIONS=1 && gh workflow run build.yml'
run 2 Bash 'git config gitclip.allowAiFiles true'

# commit on main
git -C "$TMP" switch -q main
run 2 Bash 'git commit -m "feat: add page"'

echo "passed: $pass, failed: $fail"
[ "$fail" -eq 0 ]
