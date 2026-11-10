"""sync.sh classifies every worktree and only updates clean branches.

The fixture remote is a local bare repo named github, so the test does not
push anywhere else. --dry-run must not move a branch.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SYNC = ROOT / "scripts" / "sync.sh"


def git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "git",
            "-c",
            "user.name=Sync Test",
            "-c",
            "user.email=sync-test@example.com",
            "-c",
            "init.defaultBranch=main",
            "-c",
            "commit.gpgsign=false",
            *args,
        ],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )


def rev(cwd: Path) -> str:
    return git(cwd, "rev-parse", "HEAD").stdout.strip()


def commit_file(cwd: Path, name: str, text: str, message: str) -> None:
    path = cwd / name
    path.write_text(text, encoding="utf-8")
    git(cwd, "add", name)
    git(cwd, "commit", "-m", message)


def run_sync(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(SYNC), *args],
        cwd=repo,
        capture_output=True,
        text=True,
    )


def lines_by_branch(output: str) -> dict[str, str]:
    found: dict[str, str] = {}
    for line in output.splitlines():
        if line.startswith("("):
            found[line] = line
            continue
        branch, _, _rest = line.partition(": ")
        found[branch] = line
    return found


def test_sync_scripts_do_not_force_or_delete() -> None:
    for name in ("sync.sh", "sync.ps1"):
        text = (ROOT / "scripts" / name).read_text(encoding="utf-8")
        for forbidden in (
            "--force",
            "push -f",
            "--force-with-lease",
            "reset --hard",
            "branch -D",
            "branch -d",
            "push --delete",
            "remote prune",
        ):
            assert forbidden not in text


def test_sync_refuses_a_missing_github_remote(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    git(tmp_path, "init", "-b", "main", str(repo))
    commit_file(repo, "README", "base\n", "base")
    result = run_sync(repo, "--dry-run")
    assert result.returncode == 1
    assert "github remote is not configured" in result.stderr
    assert result.stdout == ""


def test_sync_dry_run_then_updates_only_clean_branches(tmp_path: Path) -> None:
    bare = tmp_path / "hub.git"
    repo = tmp_path / "repo"
    other = tmp_path / "other"
    git(tmp_path, "init", "--bare", "-b", "main", str(bare))
    git(tmp_path, "init", "-b", "main", str(repo))
    git(repo, "remote", "add", "github", str(bare))
    commit_file(repo, "README", "base\n", "base")
    git(repo, "push", "-u", "github", "main")

    git(repo, "branch", "ahead-branch", "main")
    ahead = tmp_path / "ahead"
    git(repo, "worktree", "add", str(ahead), "ahead-branch")
    commit_file(ahead, "extra.txt", "ahead\n", "ahead")

    git(repo, "branch", "behind-branch", "main")
    git(repo, "push", "-u", "github", "behind-branch")
    behind = tmp_path / "behind"
    git(repo, "worktree", "add", str(behind), "behind-branch")

    git(repo, "branch", "dirty-branch", "main")
    git(repo, "push", "-u", "github", "dirty-branch")
    dirty = tmp_path / "dirty"
    git(repo, "worktree", "add", str(dirty), "dirty-branch")

    git(repo, "branch", "diverged-branch", "main")
    git(repo, "push", "-u", "github", "diverged-branch")
    diverged = tmp_path / "diverged"
    git(repo, "worktree", "add", str(diverged), "diverged-branch")
    commit_file(diverged, "local.txt", "local\n", "local diverge")

    detached = tmp_path / "detached"
    git(repo, "worktree", "add", "--detach", str(detached), "main")

    git(tmp_path, "clone", str(bare), str(other))
    git(other, "checkout", "behind-branch")
    commit_file(other, "remote-only.txt", "remote\n", "remote advance")
    git(other, "push", "origin", "behind-branch")
    git(other, "checkout", "dirty-branch")
    commit_file(other, "dirty-remote.txt", "remote\n", "dirty remote advance")
    git(other, "push", "origin", "dirty-branch")
    git(other, "checkout", "diverged-branch")
    commit_file(other, "remote.txt", "remote\n", "remote diverge")
    git(other, "push", "origin", "diverged-branch")

    (dirty / "notes.txt").write_text("uncommitted\n", encoding="utf-8")

    before = {
        "main": rev(repo),
        "ahead": rev(ahead),
        "behind": rev(behind),
        "dirty": rev(dirty),
        "diverged": rev(diverged),
        "detached": rev(detached),
    }
    ahead_on_remote = subprocess.run(
        ["git", "--git-dir", str(bare), "rev-parse", "--verify", "--quiet", "refs/heads/ahead-branch"],
        capture_output=True,
        text=True,
    )
    assert ahead_on_remote.returncode != 0

    dry = run_sync(repo, "--dry-run")
    assert dry.returncode == 0, dry.stderr
    reported = lines_by_branch(dry.stdout)
    assert reported["main"] == "main: up to date"
    assert reported["ahead-branch"] == "ahead-branch: ahead, would push"
    assert reported["behind-branch"] == "behind-branch: behind, would fast-forward"
    assert reported["dirty-branch"] == "dirty-branch: dirty, left untouched"
    assert reported["diverged-branch"] == "diverged-branch: diverged, left untouched"
    assert any(line.startswith("(detached ") and line.endswith(": left untouched") for line in reported)
    assert len(dry.stdout.splitlines()) == 6
    assert rev(repo) == before["main"]
    assert rev(ahead) == before["ahead"]
    assert rev(behind) == before["behind"]
    assert rev(dirty) == before["dirty"]
    assert rev(diverged) == before["diverged"]
    assert (dirty / "notes.txt").read_text(encoding="utf-8") == "uncommitted\n"
    still_absent = subprocess.run(
        ["git", "--git-dir", str(bare), "rev-parse", "--verify", "--quiet", "refs/heads/ahead-branch"],
        capture_output=True,
        text=True,
    )
    assert still_absent.returncode != 0

    live = run_sync(repo)
    assert live.returncode == 0, live.stderr
    done = lines_by_branch(live.stdout)
    assert done["main"] == "main: up to date"
    assert done["ahead-branch"] == "ahead-branch: ahead, pushed"
    assert done["behind-branch"] == "behind-branch: behind, fast-forwarded"
    assert done["dirty-branch"] == "dirty-branch: dirty, left untouched"
    assert done["diverged-branch"] == "diverged-branch: diverged, left untouched"
    assert len(live.stdout.splitlines()) == 6

    assert rev(ahead) == before["ahead"]
    assert (
        subprocess.run(
            ["git", "--git-dir", str(bare), "rev-parse", "refs/heads/ahead-branch"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        == before["ahead"]
    )
    assert git(ahead, "rev-parse", "--abbrev-ref", "@{upstream}").stdout.strip() == "github/ahead-branch"
    assert rev(behind) == git(other, "rev-parse", "behind-branch").stdout.strip()
    assert rev(behind) != before["behind"]
    assert rev(dirty) == before["dirty"]
    assert (dirty / "notes.txt").read_text(encoding="utf-8") == "uncommitted\n"
    assert rev(diverged) == before["diverged"]
    remote_diverged = subprocess.run(
        ["git", "--git-dir", str(bare), "rev-parse", "refs/heads/diverged-branch"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert remote_diverged != before["diverged"]
    assert rev(repo) == before["main"]
    assert rev(detached) == before["detached"]
