#!/usr/bin/env python3
"""Benchmark runner: run treewidth solvers on benchmark instances and collect results."""

import argparse
import datetime
import os
import signal
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from lib.benchmark_registry import (
    list_instances,
    list_installed as list_installed_benchmarks,
)
from lib.format_converter import get_graph_info
from lib.runner import (
    ResultWriter,
    install_signal_handlers,
    install_worker_signal_handlers,
    run_solver,
)
from lib.solver_registry import (
    get_solver,
    is_installed,
    list_installed as list_installed_solvers,
)


def resolve_solvers(names):
    """Resolve solver names, expanding 'all' and filtering to installed."""
    if "all" in names:
        return list_installed_solvers()
    available = []
    for name in names:
        if not is_installed(name):
            print(f"Warning: solver '{name}' is not installed, skipping")
            continue
        available.append(name)
    return available


def resolve_benchmarks(names):
    """Resolve benchmark names, expanding 'all' and filtering to installed."""
    if "all" in names:
        return list_installed_benchmarks()
    from lib.benchmark_registry import is_installed as bench_installed
    available = []
    for name in names:
        if not bench_installed(name):
            print(f"Warning: benchmark '{name}' is not downloaded, skipping")
            continue
        available.append(name)
    return available


def _run_one(args):
    """Wrapper for process pool."""
    (solver_name, instance_path, timeout, bench_name, use_heuristic, debug,
     validate, graph_info) = args
    result = run_solver(
        solver_name, instance_path, timeout, use_heuristic,
        debug=debug, validate=validate, graph_info=graph_info,
    )
    result["benchmark_set"] = bench_name
    return result


def _interrupt_workers(pool):
    """Send SIGINT to every live pool worker so it aborts its running solver.

    Workers install lib.runner's handler at start-up (initializer), which
    terminates the solver's process group and unwinds the task. Uses the
    executor's private process table; there is no public way to list them.
    """
    procs = getattr(pool, "_processes", None) or {}
    for p in list(procs.values()):
        try:
            os.kill(p.pid, signal.SIGINT)
        except (ProcessLookupError, OSError):
            pass


def _error_result(item, exc):
    """Result row for a work item whose worker raised instead of returning."""
    solver_name, instance_path, _, bench_name, use_heuristic, _, _, _ = item
    return {
        "solver": solver_name,
        "mode": "heuristic" if use_heuristic else "exact",
        "benchmark_set": bench_name,
        "instance": Path(instance_path).stem,
        "vertices": None,
        "edges": None,
        "treewidth": None,
        "time_sec": None,
        "status": f"error: {type(exc).__name__}: {str(exc)[:80]}",
        "memory_mb": None,
    }


def summarize(results):
    """One-line status breakdown: ok, timeout, invalid, parse_error, error.

    Each status is counted separately so that, for example, the number of
    decompositions --validate rejected is visible instead of being folded
    into a generic error count. "error: <reason>" rows are grouped as error.
    """
    counts = {"ok": 0, "timeout": 0, "invalid": 0, "parse_error": 0, "error": 0}
    for r in results:
        st = r["status"]
        key = "error" if st.startswith("error") else st
        counts[key] = counts.get(key, 0) + 1
    parts = [f"{n} {name}" for name, n in counts.items() if n or name in ("ok", "timeout")]
    return "Summary: " + ", ".join(parts)


def _print_debug(result):
    """Print diagnostic info for failed solver runs."""
    if result["status"] == "ok":
        return
    dbg = result.get("_debug")
    if not dbg:
        return

    solver = result["solver"]
    instance = result["instance"]
    status = result["status"]

    print(f"\n{'=' * 72}")
    print(f"  DEBUG: {solver} on {instance} [{status}]")
    print(f"{'=' * 72}")
    print(f"  Command: {dbg['command']}")
    print(f"  CWD:     {dbg['cwd']}")
    print(f"  Exit code: {dbg['returncode']}")

    stderr = dbg.get("stderr", "")
    print(f"  --- stderr ({len(stderr)} chars) ---")
    if stderr.strip():
        for line in stderr.strip().splitlines()[:40]:
            print(f"  | {line}")
    else:
        print("  (empty)")

    stdout_raw = dbg.get("stdout_raw", "")
    print(f"  --- stdout ({len(stdout_raw)} chars) ---")
    if stdout_raw.strip():
        for line in stdout_raw.strip().splitlines()[:20]:
            print(f"  | {line}")
    else:
        print("  (empty)")
    print(f"{'=' * 72}")


def main():
    parser = argparse.ArgumentParser(
        description="Run treewidth solvers on benchmark instances."
    )
    parser.add_argument(
        "--solver",
        action="append",
        default=[],
        help="Solver to run (can be repeated, or 'all')",
    )
    parser.add_argument(
        "--benchmark",
        action="append",
        default=[],
        help="Benchmark set to use (can be repeated, or 'all')",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=300,
        help="Timeout per instance in seconds (default: 300)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output CSV file path (default: results/YYYY-MM-DD_HHMMSS.csv)",
    )
    parser.add_argument(
        "--jobs", "-j", type=int, default=1, help="Number of parallel jobs (default: 1)"
    )
    parser.add_argument(
        "--heuristic",
        action="store_true",
        help="Use heuristic mode for solvers that support both",
    )
    parser.add_argument(
        "--max-instances",
        type=int,
        default=None,
        help="Max instances per benchmark set (for quick testing)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Print diagnostic info (command, stderr, stdout) for failed runs",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate emitted tree decompositions; mark invalid ones as 'invalid'",
    )
    parser.add_argument(
        "--list", action="store_true", help="List installed solvers and benchmarks"
    )
    args = parser.parse_args()

    if args.list:
        print("=== Installed Solvers ===")
        for name in list_installed_solvers():
            s = get_solver(name)
            print(f"  {name:25s} [{s['type']:10s}]")
        print()
        print("=== Installed Benchmarks ===")
        for name in list_installed_benchmarks():
            instances = list_instances(name)
            print(f"  {name:25s} ({len(instances)} instances)")
        return

    if not args.solver or not args.benchmark:
        parser.print_help()
        print("\nError: --solver and --benchmark are required")
        sys.exit(1)

    solvers = resolve_solvers(args.solver)
    benchmarks = resolve_benchmarks(args.benchmark)

    if args.heuristic:
        for name in solvers:
            s = get_solver(name)
            if s.get("type") == "exact" and "run_command_heuristic" not in s:
                print(
                    f"Warning: solver '{name}' has no heuristic mode; "
                    f"its exact command will run (mode column says 'exact')"
                )

    if not solvers:
        print("Error: no installed solvers found")
        sys.exit(1)
    if not benchmarks:
        print("Error: no installed benchmarks found")
        sys.exit(1)

    # Build work items. Each instance file is scanned once here for its
    # vertex/edge counts and the result shared by every solver run on it;
    # reading a 500 MB road graph per (solver, instance) pair was both slow
    # and memory-hungry. A malformed file is remembered as the exception so
    # every run on it reports the error without re-reading it.
    work = []
    graph_infos = {}
    for bench_name in benchmarks:
        instances = list_instances(bench_name)
        if args.max_instances is not None:
            instances = instances[: args.max_instances]
        for inst in instances:
            if inst not in graph_infos:
                try:
                    graph_infos[inst] = get_graph_info(inst)
                except Exception as e:
                    graph_infos[inst] = e
        for solver_name in solvers:
            for inst in instances:
                work.append(
                    (
                        solver_name, inst, args.timeout, bench_name,
                        args.heuristic, args.debug, args.validate,
                        graph_infos[inst],
                    )
                )

    total = len(work)
    print(f"Running {len(solvers)} solver(s) x {len(benchmarks)} benchmark(s)")
    print(f"Total jobs: {total}, timeout: {args.timeout}s, parallelism: {args.jobs}")
    print()

    if total == 0:
        print("No instances were run; no results file written.")
        return

    if args.output:
        output_path = args.output
    else:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
        output_path = f"results/{timestamp}.csv"

    # Ctrl-C and SIGTERM both stop the running solver(s) before unwinding;
    # the solvers live in their own sessions and would otherwise outlive us.
    install_signal_handlers()

    # Results are appended to the CSV as each job finishes, so an interrupted
    # or crashed run still leaves every completed result on disk.
    results = []
    interrupted = False
    with ResultWriter(output_path) as writer:
        print(f"Writing results to: {output_path}\n")

        def record(item, r):
            solver_name, inst, _, bench_name, _, _, _, _ = item
            inst_name = Path(inst).stem
            results.append(r)
            writer.write(r)
            tw = r["treewidth"] if r["treewidth"] is not None else "-"
            t = r["time_sec"] if r["time_sec"] is not None else "-"
            print(
                f"[{len(results)}/{total}] {solver_name}[{r.get('mode', '?')}]"
                f" on {bench_name}/{inst_name}"
                f" tw={tw} t={t}s [{r['status']}]",
                flush=True,
            )
            if args.debug:
                _print_debug(r)

        try:
            if args.jobs == 1:
                for item in work:
                    record(item, _run_one(item))
            else:
                with ProcessPoolExecutor(
                    max_workers=args.jobs, initializer=install_worker_signal_handlers
                ) as pool:
                    futures = {pool.submit(_run_one, item): item for item in work}
                    try:
                        for future in as_completed(futures):
                            item = futures[future]
                            try:
                                r = future.result()
                            except Exception as e:
                                # One crashed worker must not abort the run or
                                # discard the other results; log it as a row.
                                r = _error_result(item, e)
                            record(item, r)
                    except KeyboardInterrupt:
                        for f in futures:
                            f.cancel()
                        # Workers run solvers in their own sessions, so a
                        # signal sent only to this process would leave those
                        # solvers running. Tell each worker to stop its solver.
                        _interrupt_workers(pool)
                        pool.shutdown(wait=False)
                        raise
        except KeyboardInterrupt:
            interrupted = True

    if interrupted:
        print(
            f"\nInterrupted: {len(results)} of {total} result(s) were written to "
            f"{output_path}"
        )
    else:
        print(f"\nResults written to: {output_path}")

    print(summarize(results))
    if interrupted:
        sys.exit(130)


if __name__ == "__main__":
    main()
