#!/bin/sh
# gitclip setup — run once on your machine. In Claude Code, prefix with ! to run it as yourself:
#   ! curl -fsSL https://raw.githubusercontent.com/ervinmckeats/gitclip/main/scripts/setup.sh | sh
# Options (pass after "sh -s --"):
#   --hooks     also install gitclip git hooks for every repository (git config --global core.hooksPath)
#   --dry-run   show what would change, change nothing
set -e

HOOKS=0; DRY=0
for a in "$@"; do
  case "$a" in
    --hooks) HOOKS=1 ;;
    --dry-run) DRY=1 ;;
    *) echo "unknown option: $a" >&2; exit 1 ;;
  esac
done

command -v python3 >/dev/null 2>&1 || { echo "gitclip: python3 is required" >&2; exit 1; }

CFG_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
SETTINGS="$CFG_DIR/settings.json"

# 1. Turn off AI attribution in commits and PRs (merges into existing settings, keeps a backup).
GITCLIP_SETTINGS="$SETTINGS" GITCLIP_DRY="$DRY" python3 - <<'PY'
import json, os, shutil, sys, time
path = os.environ["GITCLIP_SETTINGS"]
dry = os.environ["GITCLIP_DRY"] == "1"
data = {}
if os.path.exists(path):
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read().strip()
        data = json.loads(text) if text else {}
    except Exception as e:
        sys.exit(f"gitclip: {path} is not valid JSON ({e}); fix it first, nothing was changed")
if not isinstance(data, dict):
    sys.exit(f"gitclip: {path} is not a JSON object; nothing was changed")
before = json.dumps(data, sort_keys=True)
data.pop("includeCoAuthoredBy", None)
attr = data.get("attribution")
if not isinstance(attr, dict):
    attr = {}
attr["commit"] = ""
attr["pr"] = ""
data["attribution"] = attr
if json.dumps(data, sort_keys=True) == before:
    print(f"gitclip: {path} already has attribution turned off")
    sys.exit(0)
if dry:
    print(f"gitclip (dry run): would write to {path}:")
    print(json.dumps({"attribution": attr}, indent=2))
    sys.exit(0)
os.makedirs(os.path.dirname(path), exist_ok=True)
if os.path.exists(path):
    backup = f"{path}.bak-{time.strftime('%Y%m%d-%H%M%S')}"
    shutil.copy2(path, backup)
    print(f"gitclip: backup saved to {backup}")
tmp = path + ".gitclip-tmp"
with open(tmp, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
    f.write("\n")
os.replace(tmp, path)
print(f"gitclip: AI attribution turned off in {path}")
PY

# 2. Optional: global git hooks (work for any agent and any editor, not only Claude Code).
if [ "$HOOKS" = 1 ]; then
  HOOK_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/gitclip/hooks"
  BASE="https://raw.githubusercontent.com/ervinmckeats/gitclip/main/templates/git-hooks"
  if [ "$DRY" = 1 ]; then
    echo "gitclip (dry run): would install commit-msg, pre-commit, pre-push into $HOOK_DIR and set core.hooksPath"
  else
    mkdir -p "$HOOK_DIR"
    for h in commit-msg pre-commit pre-push; do
      curl -fsSL "$BASE/$h" -o "$HOOK_DIR/$h"
      chmod +x "$HOOK_DIR/$h"
    done
    git config --global core.hooksPath "$HOOK_DIR"
    echo "gitclip: git hooks installed in $HOOK_DIR (undo: git config --global --unset core.hooksPath)"
  fi
fi

echo "gitclip: done. Changes apply to new and running Claude Code sessions on this machine."
