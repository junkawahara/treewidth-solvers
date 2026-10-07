"""Helpers for deciding whether an existing clone directory is complete.

The download markers (.tw_download_complete) were introduced after many
installations had already been cloned. Those directories have no marker, so
they must not be mistaken for interrupted clones and deleted. A directory is
treated as a complete clone when git can resolve HEAD in it and no tracked
file is missing from the working tree.
"""

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
