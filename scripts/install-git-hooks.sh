#!/bin/sh
# Install the gitclip git hooks.
#   sh install-git-hooks.sh            -> current repository (.git/hooks)
#   sh install-git-hooks.sh --global   -> every repository on this machine (core.hooksPath)
set -e
SRC="$(cd "$(dirname "$0")/../templates/git-hooks" && pwd)"

if [ "$1" = "--global" ]; then
  DEST="${XDG_CONFIG_HOME:-$HOME/.config}/gitclip/hooks"
  mkdir -p "$DEST"
  cp "$SRC"/commit-msg "$SRC"/pre-commit "$SRC"/pre-push "$DEST"/
  chmod +x "$DEST"/*
  git config --global core.hooksPath "$DEST"
  echo "gitclip hooks installed globally in $DEST (core.hooksPath)."
  echo "Note: this replaces per-repository .git/hooks. Undo with: git config --global --unset core.hooksPath"
else
  DEST="$(git rev-parse --git-path hooks)"
  mkdir -p "$DEST"
  for h in commit-msg pre-commit pre-push; do
    if [ -e "$DEST/$h" ] && ! grep -q gitclip "$DEST/$h"; then
      echo "skip $h: an existing hook is in place ($DEST/$h)"; continue
    fi
    cp "$SRC/$h" "$DEST/$h" && chmod +x "$DEST/$h" && echo "installed $DEST/$h"
  done
fi
