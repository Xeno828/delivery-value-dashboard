#!/bin/bash
# Set up delivery-value-dashboard on this Mac and push it to a remote.
#
# Preserves the existing commit history. Does not run `git init` — the zip is
# already a repository, and re-initialising it would discard the history.
#
#   chmod +x setup-on-mac.sh && ./setup-on-mac.sh
#
set -euo pipefail

ZIP="${ZIP:-$HOME/Downloads/delivery-value-dashboard.zip}"
DEST="${DEST:-$HOME/Developer}"
NAME="delivery-value-dashboard"
REPO="$DEST/$NAME"

say() { printf '\n\033[1m%s\033[0m\n' "$1"; }
die() { printf '\n\033[31m%s\033[0m\n' "$1" >&2; exit 1; }

# ---------------------------------------------------------------- 1. unpack
# Two ways this gets run: on the loose script next to the downloaded zip, or
# from inside a repo that is already unpacked (scripts/setup-on-mac.sh). In the
# second case there is nothing to unzip and the checks below still apply.
HERE="$(cd "$(dirname "$0")/.." 2>/dev/null && pwd || true)"

if [ -n "$HERE" ] && [ -d "$HERE/.git" ] && [ -f "$HERE/build.py" ]; then
  REPO="$HERE"
  say "Already unpacked at $REPO — skipping the unzip"
  cd "$REPO"
else
  [ -f "$ZIP" ] || die "No zip at $ZIP
Download it from the conversation first, or run with:  ZIP=/path/to/file.zip ./setup-on-mac.sh"

  if [ -e "$REPO" ]; then
    die "$REPO already exists.
Nothing has been touched. Move or rename it, or run with:  DEST=~/some/other/dir ./setup-on-mac.sh"
  fi

  say "Unpacking to $REPO"
  mkdir -p "$DEST"
  unzip -q "$ZIP" -d "$DEST"
  [ -d "$REPO/.git" ] || die "Unpacked, but $REPO/.git is missing — the history did not survive the download."
  cd "$REPO"
fi

# ------------------------------------------------------- 2. verify it works
say "Verifying the repository"
git status --short >/dev/null || die "Not a valid git repository."
echo "  commits:"
git log --oneline | sed 's/^/    /'

if [ -n "$(git status --porcelain)" ]; then
  echo "  note: working tree is not clean —"
  git status --short | sed 's/^/    /'
fi

say "Running the test suites (this takes a minute)"
if command -v python3 >/dev/null 2>&1; then
  python3 build.py --check || die "Build check failed."
  python3 tests/test_agent.py 2>&1 | tail -1
  echo "  (browser suites need Playwright: pip3 install playwright && playwright install chromium)"
else
  echo "  python3 not found — skipping. Install it to run 'make test'."
fi

# ----------------------------------------------------- 3. claim the commits
CURRENT="$(git log -1 --format='%an <%ae>')"
say "The commits are currently authored by: $CURRENT"
printf 'Re-author them as you? [y/N] '
read -r ANSWER
if [ "$ANSWER" = "y" ] || [ "$ANSWER" = "Y" ]; then
  printf '  Your name:  '; read -r GIT_NAME
  printf '  Your email: '; read -r GIT_EMAIL
  # Rewrites every commit, not just the last one.
  git -c user.name="$GIT_NAME" -c user.email="$GIT_EMAIL" \
      filter-branch -f --env-filter "
        export GIT_AUTHOR_NAME='$GIT_NAME'
        export GIT_AUTHOR_EMAIL='$GIT_EMAIL'
        export GIT_COMMITTER_NAME='$GIT_NAME'
        export GIT_COMMITTER_EMAIL='$GIT_EMAIL'
      " -- --all >/dev/null 2>&1
  git config user.name "$GIT_NAME"
  git config user.email "$GIT_EMAIL"
  # filter-branch leaves the pre-rewrite refs behind; drop them so the repo
  # you push is exactly what you see in the log.
  git for-each-ref --format='%(refname)' refs/original \
    | xargs -n 1 git update-ref -d 2>/dev/null || true
  git reflog expire --expire=now --all 2>/dev/null || true
  git gc --prune=now -q 2>/dev/null || true
  echo "  done — now authored by $(git log -1 --format='%an <%ae>')"
fi

# -------------------------------------------------------------- 4. push it
say "Pushing"
if git remote get-url origin >/dev/null 2>&1; then
  echo "  origin already set: $(git remote get-url origin)"
  git push -u origin main
elif command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
  printf '  Create a private GitHub repo and push? [Y/n] '
  read -r ANSWER
  if [ "$ANSWER" != "n" ] && [ "$ANSWER" != "N" ]; then
    gh repo create "$NAME" --private --source=. --push
  fi
else
  cat <<EOF
  The gh CLI is not installed or not authenticated, so the remote has to be
  created by hand. Create an EMPTY repository in your host's web UI —
  no README, no .gitignore, no licence, or the first push is rejected as a
  non-fast-forward — then:

      cd "$REPO"
      git remote add origin <your-remote-url>
      git push -u origin main
EOF
fi

# ------------------------------------------------------------------ 5. done
say "Ready"
cat <<EOF
  $REPO

  make build     assemble dist/delivery-value-dashboard.html
  make test      all four suites: browser, agent, accessibility, security
  make intake ASK=data/asks/INTAKE-2026-014.json

  Two things worth checking before this repo sees real data:
    - .env and data/dashboard-data.json are git-ignored on purpose. The
      second holds real issue titles. Confirm they survive any .gitignore
      edits you make.
    - The Pages workflow is off by default and publishes the demo dataset.
      Do not enable it on a repo holding real issue data unless your plan
      supports private Pages.
EOF
