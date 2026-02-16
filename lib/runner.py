"""Benchmark runner: execute solvers on benchmark instances."""

import csv
import os
import signal
import subprocess
import tempfile
import time
from pathlib import Path

from lib.format_converter import (
    get_graph_info,
    pace_gr_to_quickbb_cnf,
    parse_td_output,
)
from lib.solver_registry import get_solver, solver_dir


def _build_run_command(solver, input_path, timeout):
    """Build the actual shell command to run a solver."""
    sdir = solver_dir(solver["name"])
    mode = solver.get("run_mode", "stdin_stdout")
    cmd_template = solver["run_command"]

    # Determine which command template to use
    if solver["type"] == "heuristic" and "run_command_heuristic" in solver:
        cmd_template = solver["run_command_heuristic"]

    # Handle format conversion
    converted_input = input_path
    if solver.get("input_format") == "quickbb_cnf":
        converted = tempfile.NamedTemporaryFile(suffix=".cnf", delete=False)
        converted.close()
        pace_gr_to_quickbb_cnf(input_path, converted.name)
        converted_input = converted.name

    # Substitute placeholders
    input_dir = str(Path(input_path).parent)
    instance_name = Path(input_path).stem

    td_output = tempfile.NamedTemporaryFile(suffix=".td", delete=False)
    td_output.close()

    cmd = cmd_template.format(
        input=converted_input,
        input_dir=input_dir,
        instance_name=instance_name,
        output_td=td_output.name,
        output_dir=tempfile.gettempdir(),
        timeout=timeout,
    )

    return cmd, mode, sdir, td_output.name, converted_input


def run_solver(solver_name, input_path, timeout=300, use_heuristic=False):
    """Run a solver on a single instance.

    Returns dict with keys:
      solver, instance, vertices, edges, treewidth, time_sec, status, memory_mb
    """
    solver = get_solver(solver_name)
    info = get_graph_info(input_path)
    instance_name = Path(input_path).stem

    result = {
        "solver": solver_name,
        "instance": instance_name,
        "vertices": info["vertices"],
        "edges": info["edges"],
        "treewidth": None,
        "time_sec": None,
        "status": "error",
        "memory_mb": None,
    }

    # Select command template
    cmd_template = solver["run_command"]
    if use_heuristic and "run_command_heuristic" in solver:
        cmd_template = solver["run_command_heuristic"]

    mode = solver.get("run_mode", "stdin_stdout")
    sdir = solver_dir(solver_name)

    # Handle format conversion
    converted_input = input_path
    cleanup_files = []
    if solver.get("input_format") == "quickbb_cnf":
        tmp = tempfile.NamedTemporaryFile(suffix=".cnf", delete=False)
        tmp.close()
        pace_gr_to_quickbb_cnf(input_path, tmp.name)
        converted_input = tmp.name
        cleanup_files.append(tmp.name)

    td_file = tempfile.NamedTemporaryFile(suffix=".td", delete=False)
    td_file.close()
    cleanup_files.append(td_file.name)

    input_dir = str(Path(input_path).resolve().parent)
    iname = Path(input_path).stem
    converted_input = str(Path(converted_input).resolve())

    cmd = cmd_template.format(
        input=converted_input,
        input_dir=input_dir,
        instance_name=iname,
        output_td=td_file.name,
        output_dir=tempfile.gettempdir(),
        timeout=timeout,
    )

    try:
        start_time = time.monotonic()

        if mode == "stdin_stdout":
            with open(input_path) as fin:
                proc = subprocess.run(
                    cmd,
                    shell=True,
                    cwd=str(sdir),
                    stdin=fin,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )
            stdout = proc.stdout

        elif mode == "stdin_stdout_signal":
            # Heuristic solver: run for `timeout` seconds, then send SIGTERM
            with open(input_path) as fin:
                proc = subprocess.Popen(
                    cmd,
                    shell=True,
                    cwd=str(sdir),
                    stdin=fin,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    preexec_fn=os.setsid,
                )
            try:
                stdout, stderr = proc.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                try:
                    stdout, stderr = proc.communicate(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                    stdout, stderr = proc.communicate(timeout=5)

        elif mode == "file":
            proc = subprocess.run(
                cmd,
                shell=True,
                cwd=str(sdir),
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            stdout = proc.stdout
            # Try reading output from file
            if os.path.exists(td_file.name) and os.path.getsize(td_file.name) > 0:
                with open(td_file.name) as f:
                    stdout = f.read()
            # Also check for solver-specific output files (e.g. twalgor-rtw .twc)
            for ext in [".twc", ".td"]:
                alt = os.path.join(tempfile.gettempdir(), iname + ext)
                if os.path.exists(alt) and os.path.getsize(alt) > 0:
                    with open(alt) as f:
                        stdout = f.read()
                    cleanup_files.append(alt)
                    break

        else:
            with open(input_path) as fin:
                proc = subprocess.run(
                    cmd,
                    shell=True,
                    cwd=str(sdir),
                    stdin=fin,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )
            stdout = proc.stdout

        elapsed = time.monotonic() - start_time
        result["time_sec"] = round(elapsed, 3)

        # Parse treewidth from output
        td_info = parse_td_output(stdout)
        if td_info:
            result["treewidth"] = td_info["treewidth"]
            result["status"] = "ok"
        else:
            # Try parsing just a number from stdout (some solvers output just the width)
            for line in stdout.strip().split("\n"):
                line = line.strip()
                if line.isdigit():
                    result["treewidth"] = int(line)
                    result["status"] = "ok"
                    break
            else:
                result["status"] = "parse_error"

    except subprocess.TimeoutExpired:
        result["time_sec"] = timeout
        result["status"] = "timeout"
    except Exception as e:
        result["status"] = f"error: {str(e)[:100]}"
    finally:
        for f in cleanup_files:
            try:
                os.unlink(f)
            except OSError:
                pass

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
