"""Solver registry: download, build, and manage treewidth solvers."""

import json
import os
import subprocess
import shutil
from pathlib import Path


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
    # A solver counts as installed only if its build finished successfully.
    # Cloning alone creates the directory but leaves no marker, so a solver
    # whose build failed is no longer mistaken for a runnable one.
    return (solver_dir(name) / BUILD_MARKER).exists()


def check_dependency(lang):
    """Check if the required language runtime/compiler is available."""
    checks = {
        "java": ["java", "-version"],
        "c": ["gcc", "--version"],
        "cpp": ["g++", "--version"],
        "julia": ["julia", "--version"],
    }
    cmd = checks.get(lang)
    if cmd is None:
        return True
    try:
        subprocess.run(cmd, capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def download_solver(solver):
    name = solver["name"]
    dest = solver_dir(name)
    if dest.exists():
        if (dest / DOWNLOAD_MARKER).exists():
            print(f"  [{name}] Already downloaded, skipping clone")
            return True
        # Directory exists without the completion marker: a previous clone was
        # interrupted. Remove the partial tree and clone again from scratch.
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


def build_solver(solver):
    name = solver["name"]
    dest = solver_dir(name)
    if not dest.exists():
        print(f"  [{name}] Not downloaded yet")
        return False
    print(f"  [{name}] Building ...")
    # Drop any marker from a previous successful build so a now-failing build
    # is not still reported as installed.
    (dest / BUILD_MARKER).unlink(missing_ok=True)
    for step in solver.get("build_steps", []):
        print(f"    $ {step}")
        try:
            subprocess.run(
                step,
                shell=True,
                cwd=str(dest),
                check=True,
                capture_output=True,
                text=True,
                timeout=300,
            )
        except subprocess.CalledProcessError as e:
            stderr_lines = (e.stderr or "").strip().splitlines()
            stdout_lines = (e.stdout or "").strip().splitlines()
            print(f"    Build step failed (exit code {e.returncode}):")
            if stderr_lines:
                tail = stderr_lines[-30:]
                if len(stderr_lines) > 30:
                    print(f"    ... ({len(stderr_lines) - 30} lines omitted)")
                for line in tail:
                    print(f"    [stderr] {line}")
            if stdout_lines:
                tail = stdout_lines[-15:]
                if len(stdout_lines) > 15:
                    print(f"    ... ({len(stdout_lines) - 15} lines omitted)")
                for line in tail:
                    print(f"    [stdout] {line}")
            if not stderr_lines and not stdout_lines:
                print(f"    (no output)")
            return False
        except subprocess.TimeoutExpired:
            print(f"    Build step timed out")
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
