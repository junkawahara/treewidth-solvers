"""Benchmark runner: execute solvers on benchmark instances."""

import csv
import os
import shlex
import shutil
import signal
import subprocess
import tempfile
import threading
import time
from pathlib import Path

from lib.format_converter import (
    get_graph_info,
    pace_gr_to_quickbb_cnf,
    parse_td_output,
)
from lib.solver_registry import get_solver, solver_dir


def _kill_group(proc, sig):
    """Signal the whole process group led by proc; ignore it if already gone.

    Wrapping killpg in a try guards against the race where the process exits
    between the timeout firing and the signal being sent.
    """
    try:
        os.killpg(os.getpgid(proc.pid), sig)
    except (ProcessLookupError, OSError):
        pass


def _group_rss_kb(pgid):
    """Sum the resident set size (kB) of every process in process group pgid.

    Linux-only (reads /proc); returns 0 on any other platform or on error.
    """
    total = 0
    try:
        entries = os.listdir("/proc")
    except OSError:
        return 0
    for entry in entries:
        if not entry.isdigit():
            continue
        try:
            with open(f"/proc/{entry}/stat") as f:
                data = f.read()
            # Fields after the ")" of comm are: state ppid pgrp ...
            after = data[data.rfind(")") + 2:].split()
            if int(after[2]) != pgid:
                continue
            with open(f"/proc/{entry}/status") as f:
                for line in f:
                    if line.startswith("VmRSS:"):
                        total += int(line.split()[1])
                        break
        except (OSError, ValueError, IndexError):
            continue
    return total


def _sample_peak_rss(pgid, stop_event, holder):
    """Poll the process group's RSS until stopped, storing the peak (kB)."""
    peak = 0
    while not stop_event.is_set():
        peak = max(peak, _group_rss_kb(pgid))
        stop_event.wait(0.1)
    peak = max(peak, _group_rss_kb(pgid))
    holder[0] = peak


def _run_with_timeout(cmd, cwd, stdin_path, timeout):
    """Run cmd in its own process group; return (stdout, stderr, timed_out, rc, peak_mb).

    The child is started as a session/group leader (os.setsid) so that on
    timeout the entire group -- including grandchildren such as the JVM that
    solver wrapper scripts spawn -- is terminated with SIGTERM then SIGKILL,
    rather than leaving orphaned processes competing for CPU and memory. A
    background thread samples the group's peak resident memory while it runs.
    """
    fin = open(stdin_path) if stdin_path else None
    try:
        proc = subprocess.Popen(
            cmd,
            shell=True,
            cwd=cwd,
            stdin=fin if fin is not None else subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            preexec_fn=os.setsid,
        )
    finally:
        if fin is not None:
            fin.close()

    # os.setsid makes the child the leader of a new group whose id == its pid.
    stop_event = threading.Event()
    holder = [0]
    sampler = threading.Thread(
        target=_sample_peak_rss, args=(proc.pid, stop_event, holder), daemon=True
    )
    sampler.start()

    timed_out = False
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        _kill_group(proc, signal.SIGTERM)
        try:
            stdout, stderr = proc.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            _kill_group(proc, signal.SIGKILL)
            try:
                stdout, stderr = proc.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                stdout, stderr = "", ""
    finally:
        stop_event.set()
        sampler.join(timeout=1)

    peak_mb = round(holder[0] / 1024.0, 1) if holder[0] else None
    return stdout, stderr, timed_out, proc.returncode, peak_mb


def _read_file_output(work_dir, iname, td_path, stdout):
    """For file-mode solvers, prefer a decomposition written to the work dir."""
    if os.path.exists(td_path) and os.path.getsize(td_path) > 0:
        with open(td_path) as f:
            return f.read()
    for ext in (".twc", ".td"):
        alt = os.path.join(work_dir, iname + ext)
        if os.path.exists(alt) and os.path.getsize(alt) > 0:
            with open(alt) as f:
                return f.read()
    return stdout


def _first_int_line(text):
    """Return the first line that is a bare integer, or None."""
    for line in text.strip().split("\n"):
        line = line.strip()
        if line.isdigit():
            return int(line)
    return None


def run_solver(solver_name, input_path, timeout=300, use_heuristic=False, debug=False):
    """Run a solver on a single instance.

    Returns dict with keys:
      solver, instance, vertices, edges, treewidth, time_sec, status, memory_mb
    When debug=True, also includes _debug dict with command, cwd, returncode,
    stderr, and stdout_raw.
    """
    solver = get_solver(solver_name)
    instance_name = Path(input_path).stem

    result = {
        "solver": solver_name,
        "instance": instance_name,
        "vertices": None,
        "edges": None,
        "treewidth": None,
        "time_sec": None,
        "status": "error",
        "memory_mb": None,
    }

    # Parse graph info defensively: a single malformed instance must not abort
    # the whole benchmark run (the exception used to propagate out of the
    # process pool and discard every result collected so far).
    try:
        info = get_graph_info(input_path)
        result["vertices"] = info["vertices"]
        result["edges"] = info["edges"]
    except Exception as e:
        result["status"] = f"error: {str(e)[:100]}"
        return result

    # Select command template
    cmd_template = solver["run_command"]
    if use_heuristic and "run_command_heuristic" in solver:
        cmd_template = solver["run_command_heuristic"]

    mode = solver.get("run_mode", "stdin_stdout")
    sdir = solver_dir(solver_name)

    _debug = {
        "command": "",
        "cwd": str(sdir),
        "returncode": None,
        "stderr": "",
        "stdout_raw": "",
    } if debug else None

    # Per-run private working directory: converted inputs and solver output
    # files live here so concurrent runs and stale files from earlier runs can
    # never read or clobber one another. Cleaned up unconditionally below.
    work_dir = tempfile.mkdtemp(prefix="tw_run_")
    try:
        input_dir = str(Path(input_path).resolve().parent)
        iname = instance_name

        converted_input = str(Path(input_path).resolve())
        if solver.get("input_format") == "quickbb_cnf":
            cnf_path = os.path.join(work_dir, iname + ".cnf")
            pace_gr_to_quickbb_cnf(input_path, cnf_path)
            converted_input = cnf_path

        td_path = os.path.join(work_dir, iname + ".td")
        # Internal solver time limits (e.g. quickbb --time) must expire before
        # the outer wall-clock timeout, or the solver is killed before it can
        # print the bound it already found.
        timeout_soft = max(1, timeout - 10)

        def q(value):
            return shlex.quote(str(value))

        cmd = cmd_template.format(
            input=q(converted_input),
            input_dir=q(input_dir),
            instance_name=q(iname),
            output_td=q(td_path),
            output_dir=q(work_dir),
            timeout=timeout,
            timeout_soft=timeout_soft,
        )
        if _debug is not None:
            _debug["command"] = cmd

        try:
            # stdin gets the converted input (not the original) so a stdin-mode
            # solver with a format conversion still receives the converted data.
            stdin_path = None if mode == "file" else converted_input
            start_time = time.monotonic()
            stdout, stderr_text, timed_out, returncode, peak_mb = _run_with_timeout(
                cmd, str(sdir), stdin_path, timeout
            )
            elapsed = time.monotonic() - start_time

            # Signal-protocol heuristics emit their best decomposition on
            # SIGTERM, so a timeout there is expected and its flushed output is
            # a valid result; for any other mode a timeout means "no answer".
            signal_timeout = timed_out and mode == "stdin_stdout_signal"
            result["time_sec"] = timeout if timed_out else round(elapsed, 3)
            result["memory_mb"] = peak_mb

            if _debug is not None:
                _debug["returncode"] = returncode
                _debug["stderr"] = stderr_text
                _debug["stdout_raw"] = stdout[:2000]

            if timed_out and not signal_timeout:
                result["status"] = "timeout"
            else:
                if mode == "file":
                    stdout = _read_file_output(work_dir, iname, td_path, stdout)
                td_info = parse_td_output(stdout)
                if td_info:
                    result["treewidth"] = td_info["treewidth"]
                    result["status"] = "ok"
                else:
                    num = _first_int_line(stdout)
                    if num is not None:
                        result["treewidth"] = num
                        result["status"] = "ok"
                    elif signal_timeout:
                        result["status"] = "timeout"
                    else:
                        result["status"] = "parse_error"
        except Exception as e:
            result["status"] = f"error: {str(e)[:100]}"
            if _debug is not None:
                import traceback
                _debug["stderr"] = traceback.format_exc()
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)

    if _debug is not None:
        result["_debug"] = _debug

    return result


def write_csv(results, output_path):
    """Write benchmark results to CSV."""
    if not results:
        return
    fieldnames = [
        "solver",
        "benchmark_set",
        "instance",
        "vertices",
        "edges",
        "treewidth",
        "time_sec",
        "status",
        "memory_mb",
    ]
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in results:
            writer.writerow({k: r.get(k) for k in fieldnames})
