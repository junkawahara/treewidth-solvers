"""Solver registry: download, build, and manage treewidth solvers."""

import json
import os
import shutil
import signal
import subprocess
import threading
from pathlib import Path

from lib.clone_check import adopt_or_reject_existing


BASE_DIR = Path(__file__).resolve().parent.parent
SOLVERS_DIR = BASE_DIR / "solvers"
CONFIG_FILE = BASE_DIR / "config" / "solvers.json"

# Marker file written into a solver directory once its build has succeeded, so
# is_installed reports a solver as usable only when its binaries actually exist.
BUILD_MARKER = ".tw_build_complete"
# Marker written once a clone has fully completed, so an interrupted clone
# (partial directory) is detected and retried rather than trusted forever.
DOWNLOAD_MARKER = ".tw_download_complete"


def load_solvers():
    with open(CONFIG_FILE) as f:
        return json.load(f)


def get_solver(name):
    for s in load_solvers():
        if s["name"] == name:
            return s
    raise ValueError(f"Unknown solver: {name}")


def solver_dir(name):
    return SOLVERS_DIR / name


def is_installed(name):
    # A solver counts as installed only if it is in the config and its build
    # finished successfully. Cloning alone creates the directory but leaves
    # no marker, so a solver whose build failed is no longer mistaken for a
    # runnable one; and a stray directory under solvers/ that matches no
    # config entry is not a solver.
    if not any(s["name"] == name for s in load_solvers()):
        return False
    return (solver_dir(name) / BUILD_MARKER).exists()


def check_dependency(lang):
    """Check that every tool needed to build and run this language is present."""
    # Java solvers are compiled with javac (and packaged with jar) at build
    # time, so checking only the java runtime let JRE-only environments pass
    # the check and then fail every build step with "javac: not found".
    checks = {
        "java": [["java", "-version"], ["javac", "-version"]],
        "c": [["gcc", "--version"]],
        "cpp": [["g++", "--version"]],
        "julia": [["julia", "--version"]],
    }
    cmds = checks.get(lang)
    if cmds is None:
        return True
    for cmd in cmds:
        try:
            subprocess.run(cmd, capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
    return True


def download_solver(solver):
    name = solver["name"]
    dest = solver_dir(name)
    if dest.exists():
        if (dest / DOWNLOAD_MARKER).exists():
            print(f"  [{name}] Already downloaded, skipping clone")
            return True
        # No marker: either a clone made before markers existed (keep it), an
        # interrupted clone (safe to redo), or something the user put there
        # by hand (never delete it).
        state = adopt_or_reject_existing(dest, DOWNLOAD_MARKER, name)
        if state == "adopted":
            return True
        if state == "foreign":
            print(
                f"  [{name}] {dest} exists but is not a git clone; "
                f"refusing to delete it. Move it away to re-download."
            )
            return False
        print(f"  [{name}] Removing incomplete download and re-cloning")
        shutil.rmtree(dest, ignore_errors=True)
    print(f"  [{name}] Cloning {solver['repo']} ...")
    try:
        subprocess.run(
            ["git", "clone", "--depth", "1", solver["repo"], str(dest)],
            check=True,
            capture_output=True,
            text=True,
        )
        (dest / DOWNLOAD_MARKER).write_text("ok\n")
        return True
    except subprocess.CalledProcessError as e:
        print(f"  [{name}] Clone failed: {e.stderr.strip()}")
        return False


# Default wall-clock limit for one build step. The old 300 s was routinely
# exceeded by htd's cmake build, tdlib-p17 and Julia's Pkg.instantiate()
# (which precompiles). A solver may override it with "build_timeout".
DEFAULT_BUILD_TIMEOUT = 1800
# Build output (stdout+stderr of every step) is appended here in the solver
# directory, so a long build can be watched with tail -f instead of looking
# hung, and the full log survives for diagnosis when only a tail is printed.
BUILD_LOG = ".tw_build.log"


def _run_build_step(step, dest, log, timeout):
    """Run one shell build step; return (ok, tail_lines, timed_out).

    The step runs in its own process group so that on timeout the whole
    tree is killed: with shell=True alone only the sh would die and a
    "cd build && cmake .. && make -j" would leave make running.
    """
    proc = subprocess.Popen(
        step,
        shell=True,
        cwd=str(dest),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        errors="replace",
        start_new_session=True,
    )
    tail = []
    timed_out = False

    def pump():
        for line in proc.stdout:
            log.write(line)
            log.flush()
            tail.append(line.rstrip("\n"))
            if len(tail) > 40:
                del tail[0]

    reader = threading.Thread(target=pump, daemon=True)
    reader.start()
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        for sig in (signal.SIGTERM, signal.SIGKILL):
            try:
                os.killpg(proc.pid, sig)
            except (ProcessLookupError, OSError):
                break
            try:
                proc.wait(timeout=5)
                break
            except subprocess.TimeoutExpired:
                continue
    reader.join(timeout=5)
    return proc.returncode == 0 and not timed_out, tail, timed_out


def build_solver(solver):
    name = solver["name"]
    dest = solver_dir(name)
    if not dest.exists():
        print(f"  [{name}] Not downloaded yet")
        return False
    timeout = solver.get("build_timeout", DEFAULT_BUILD_TIMEOUT)
    log_path = dest / BUILD_LOG
    print(f"  [{name}] Building ... (output: {log_path})")
    # Drop any marker from a previous successful build so a now-failing build
    # is not still reported as installed.
    (dest / BUILD_MARKER).unlink(missing_ok=True)
    with open(log_path, "w") as log:
        for step in solver.get("build_steps", []):
            print(f"    $ {step}")
            log.write(f"$ {step}\n")
            log.flush()
            ok, tail, timed_out = _run_build_step(step, dest, log, timeout)
            if ok:
                continue
            if timed_out:
                print(f"    Build step timed out after {timeout}s")
            else:
                print(f"    Build step failed")
            if tail:
                print(f"    Last {len(tail)} line(s) of output (full log: {log_path}):")
                for line in tail:
                    print(f"    | {line}")
            else:
                print(f"    (no output)")
            return False
    (dest / BUILD_MARKER).write_text("ok\n")
    print(f"  [{name}] Build successful")
    return True


def setup_solver(solver):
    name = solver["name"]
    lang = solver["language"]
    if not check_dependency(lang):
        print(f"  [{name}] Skipping: {lang} not found")
        return False
    if not download_solver(solver):
        return False
    return build_solver(solver)


def setup_all():
    solvers = load_solvers()
    results = {}
    for solver in solvers:
        name = solver["name"]
        print(f"\n--- Setting up solver: {name} ---")
        results[name] = setup_solver(solver)
    return results


def list_installed():
    return [s["name"] for s in load_solvers() if is_installed(s["name"])]
