#!/usr/bin/env bash
# Fetch github --prune, then for each worktree print one line.
# Clean and behind: fast-forward to github/<branch>.
# Clean and ahead (including a branch github does not have yet): push and
# set upstream to github/<branch>. A normal push only; never a force-push.
# Dirty or diverged: print the line and leave the worktree alone.
# --dry-run fetches and prints the same lines. It does not pull or push.
set -euo pipefail

dry_run=0
for arg in "$@"; do
  case "$arg" in
    --dry-run) dry_run=1 ;;
    *)
      echo "unknown arg: $arg" >&2
      exit 2
      ;;
  esac
done

if ! git rev-parse --show-toplevel >/dev/null 2>&1; then
  echo "not a git repository" >&2
  exit 1
fi
cd "$(git rev-parse --show-toplevel)"

if ! git remote get-url github >/dev/null 2>&1; then
  echo "github remote is not configured" >&2
  exit 1
fi

fetch_err="$(mktemp)"
if ! git fetch github --prune >"$fetch_err" 2>&1; then
  echo "fetch github failed" >&2
  rm -f "$fetch_err"
  exit 1
fi
rm -f "$fetch_err"

export GIT_TERMINAL_PROMPT=0
export GIT_MERGE_AUTOEDIT=no

path=""
head=""
kind=""
branch=""

finish_worktree() {
  if [[ -z "$path" ]]; then
    return
  fi
  if [[ "$kind" != "branch" || -z "$branch" ]]; then
    local label="detached"
    if [[ -n "$head" ]]; then
      label="detached ${head:0:7}"
    fi
    echo "(${label}): left untouched"
    path=""
    head=""
    kind=""
    branch=""
    return
  fi

  local dirty=""
  dirty="$(git -C "$path" status --porcelain)"
  local remote_ref="github/${branch}"
  local relation="ahead"
  if git rev-parse --verify --quiet "$remote_ref" >/dev/null 2>&1; then
    local remote
    remote="$(git rev-parse "$remote_ref")"
    if [[ "$head" == "$remote" ]]; then
      relation="same"
    elif git merge-base --is-ancestor "$head" "$remote" 2>/dev/null; then
      relation="behind"
    elif git merge-base --is-ancestor "$remote" "$head" 2>/dev/null; then
      relation="ahead"
    else
      relation="diverged"
    fi
  fi

  if [[ -n "$dirty" ]]; then
    echo "${branch}: dirty, left untouched"
  elif [[ "$relation" == "same" ]]; then
    echo "${branch}: up to date"
  elif [[ "$relation" == "diverged" ]]; then
    echo "${branch}: diverged, left untouched"
  elif [[ "$relation" == "behind" ]]; then
    if [[ "$dry_run" -eq 1 ]]; then
      echo "${branch}: behind, would fast-forward"
    elif git -C "$path" merge --ff-only --quiet -- "$remote_ref" >/dev/null 2>&1; then
      echo "${branch}: behind, fast-forwarded"
    else
      echo "${branch}: behind, fast-forward failed, left untouched"
    fi
  elif [[ "$dry_run" -eq 1 ]]; then
    echo "${branch}: ahead, would push"
  elif git -C "$path" push --quiet -u github -- "$branch" >/dev/null 2>&1; then
    echo "${branch}: ahead, pushed"
  else
    echo "${branch}: ahead, push refused, left untouched"
  fi

  path=""
  head=""
  kind=""
  branch=""
}

while IFS= read -r line || [[ -n "$line" ]]; do
  case "$line" in
    worktree\ *)
      finish_worktree
      path="${line#worktree }"
      head=""
      kind=""
      branch=""
      ;;
    HEAD\ *)
      head="${line#HEAD }"
      ;;
    branch\ *)
      kind="branch"
      branch="${line#branch refs/heads/}"
      ;;
    detached)
      kind="detached"
      ;;
    "")
      finish_worktree
      ;;
  esac
done < <(git worktree list --porcelain)
finish_worktree
