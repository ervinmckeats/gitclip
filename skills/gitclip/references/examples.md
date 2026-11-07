# gitclip — worked examples

## Starting work on a feature

```bash
git config user.name; git config user.email     # the user, not an AI
git switch main && git pull --ff-only
git switch -c feat/user-profile
# ... edit ...
git add src/profile/ tests/profile/
git diff --cached --name-only                    # no CLAUDE.md, .claude/, etc.
git commit -m "feat: add user profile page"
git push -u origin feat/user-profile
gh pr create --title "feat: add user profile page" --body "- add profile page with avatar and bio
- add route /profile
- verify: open /profile while signed in"
# do NOT merge — the user reviews
```

## Fixing a bug (auto-merge allowed)

```bash
git switch -c fix/empty-cart-crash
git commit -m "fix: handle empty cart on checkout"
git push -u origin fix/empty-cart-crash
gh pr create --title "fix: handle empty cart on checkout" --body "- guard against empty cart in checkout total"
gh pr merge --squash --auto        # only for fix PRs, once checks pass
```

## Commit messages

| Bad | Why | Good |
|---|---|---|
| `Fixed the login bug.` | no type, past tense, period | `fix: prevent login loop on expired token` |
| `fix/ login loop` | slash belongs to branches only | `fix: prevent login loop` |
| `feat(auth): add sso` | no scopes | `feat: add sso sign-in` |
| `chore: bump deps` | `chore` is not a type | `add: bump dependencies` |
| `refactor: split utils` | `refactor` is not a type | `feat: split utils into modules` |
| `feat: добавить профиль` | not English | `feat: add profile page` |
| `feat: add a completely new and very detailed onboarding flow for users` | too long | `feat: add onboarding flow` |

Bad trailers (never add any of these):

```text
Co-Authored-By: <any AI or AI vendor>
Generated with <any AI tool>
🤖 ...
<link to an AI session>
```

## Branch names

| Bad | Good |
|---|---|
| `feature/UserProfile` | `feat/user-profile` |
| `claude/fix-login` | `fix/login-loop` |
| `patch-1` | `fix/typo-in-header` |
| `remove-old-api` | `del/legacy-api` |
| `readme` | `docs/install-steps` |

## Staged AI files

```bash
$ git diff --cached --name-only
src/app.ts
CLAUDE.md            # ← must not be committed
.claude/settings.json
$ git restore --staged CLAUDE.md .claude/
$ echo "CLAUDE.md" >> .git/info/exclude && echo ".claude/" >> .git/info/exclude
```

## Mirroring an artifact

You produced a landing-page mockup as a published artifact:

```bash
git switch -c add/landing-mockup
mkdir -p design && cp landing.html design/landing.html
git add design/landing.html
git commit -m "add: landing page mockup"
```

## When you must stop and ask

- `git config user.email` returns an AI vendor address.
- The task seems to need a CI run.
- You cannot tell whether a change is a fix or a key change (default: key change).
- The project's repository is unknown, so artifacts cannot be mirrored.
- Fixing a rule violation would require rewriting already-pushed history.
