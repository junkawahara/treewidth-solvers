"""Helpers for cloning solver/benchmark repositories at a pinned commit and
for deciding whether an existing clone directory is complete.

The download markers (.tw_download_complete) were introduced after many
installations had already been cloned. Those directories have no marker, so
they must not be mistaken for interrupted clones and deleted. A directory is
treated as a complete clone when git can resolve HEAD in it and no tracked
file is missing from the working tree.
"""

import shutil
import subprocess
from pathlib import Path


def _git(dest, *args):
    return subprocess.run(
        ["git", "-C", str(dest), *args],
        capture_output=True,
        text=True,
    )


def has_git_dir(dest):
    """True if dest looks like a git repository (clone started or finished)."""
    return (Path(dest) / ".git").exists()


def is_complete_clone(dest):
    """True if dest is a git clone whose checkout finished.

    An interrupted `git clone` either has no resolvable HEAD yet (fetch was
    interrupted) or lacks tracked files in the working tree (checkout was
    interrupted). Both cases return False. Local modifications and untracked
    files (build products, decompressed instances) are fine.
    """
    dest = Path(dest)
    if not has_git_dir(dest):
        return False
    try:
        head = _git(dest, "rev-parse", "--verify", "HEAD")
        if head.returncode != 0:
            return False
        deleted = _git(dest, "ls-files", "--deleted")
        if deleted.returncode != 0:
            return False
        return deleted.stdout.strip() == ""
    except (OSError, subprocess.SubprocessError):
        return False


def adopt_or_reject_existing(dest, marker_name, label):
    """Decide what to do with an existing directory that has no marker.

    Returns one of:
      "adopted"   -- complete clone; the marker has been written, use it as-is
      "incomplete" -- a git clone that was interrupted; safe to remove and redo
      "foreign"   -- not a git clone at all (user-placed content); never remove
    """
    dest = Path(dest)
    if is_complete_clone(dest):
        (dest / marker_name).write_text("ok\n")
        print(f"  [{label}] Existing clone found without marker; adopting it")
        return "adopted"
    if has_git_dir(dest):
        return "incomplete"
    return "foreign"


def _run_checked(args, cwd=None):
    r = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    if r.returncode != 0:
        raise subprocess.CalledProcessError(r.returncode, args, r.stdout, r.stderr)
    return r


def clone_pinned(repo, commit, dest):
    """Shallow-clone repo into dest at exactly `commit` (a full sha).

    Without a pin, `git clone --depth 1` takes whatever the upstream default
    branch points at today, so two installations are not reproducible and
    the sed/patch build steps written against one revision silently stop
    matching when upstream changes. Fetching the sha directly (init + fetch
    --depth 1 <sha> + checkout FETCH_HEAD) downloads only that commit, which
    GitHub permits for any reachable commit. commit=None falls back to the
    unpinned clone.

    On failure the partially created directory is removed and
    subprocess.CalledProcessError is raised with git's stderr.
    """
    dest = Path(dest)
    try:
        if not commit:
            _run_checked(["git", "clone", "--depth", "1", repo, str(dest)])
            return
        _run_checked(["git", "init", "-q", str(dest)])
        _run_checked(["git", "remote", "add", "origin", repo], cwd=dest)
        _run_checked(["git", "fetch", "-q", "--depth", "1", "origin", commit], cwd=dest)
        _run_checked(
            ["git", "-c", "advice.detachedHead=false", "checkout", "-q", "FETCH_HEAD"],
            cwd=dest,
        )
    except subprocess.CalledProcessError:
        shutil.rmtree(dest, ignore_errors=True)
        raise


def head_commit(dest):
    """Full sha of HEAD in dest, or None if it cannot be resolved."""
    r = _git(dest, "rev-parse", "--verify", "HEAD")
    return r.stdout.strip() if r.returncode == 0 else None


def warn_if_not_pinned(dest, commit, label):
    """Note when an existing checkout is not at the configured commit.

    The checkout is left alone -- it may carry local changes or an already
    finished build -- but the discrepancy should be visible, since the
    build steps were written against the pinned revision.
    """
    if not commit:
        return
    head = head_commit(dest)
    if head and head != commit:
        print(
            f"  [{label}] Note: checkout is at {head[:12]}, config pins "
            f"{commit[:12]}; remove the directory to re-clone at the pinned commit"
        )
