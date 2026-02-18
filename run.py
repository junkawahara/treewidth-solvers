#!/usr/bin/env python3
"""Benchmark runner: run treewidth solvers on benchmark instances and collect results."""

import argparse
import datetime
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from lib.benchmark_registry import (
    list_instances,
    list_installed as list_installed_benchmarks,
    load_benchmarks,
)
from lib.runner import run_solver, write_csv
from lib.solver_registry import (
    get_solver,
    is_installed,
    list_installed as list_installed_solvers,
    load_solvers,
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
    solver_name, instance_path, timeout, bench_name, use_heuristic = args
    result = run_solver(solver_name, instance_path, timeout, use_heuristic)
    result["benchmark_set"] = bench_name
    return result


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

    if not solvers:
        print("Error: no installed solvers found")
        sys.exit(1)
    if not benchmarks:
        print("Error: no installed benchmarks found")
        sys.exit(1)

    # Build work items
    work = []
    for bench_name in benchmarks:
        instances = list_instances(bench_name)
        if args.max_instances:
            instances = instances[: args.max_instances]
        for solver_name in solvers:
            for inst in instances:
                work.append(
                    (solver_name, inst, args.timeout, bench_name, args.heuristic)
                )

    total = len(work)
    print(f"Running {len(solvers)} solver(s) x {len(benchmarks)} benchmark(s)")
    print(f"Total jobs: {total}, timeout: {args.timeout}s, parallelism: {args.jobs}")
    print()

    # Run benchmarks
    results = []
    done = 0

    if args.jobs == 1:
        for item in work:
            solver_name, inst, _, bench_name, _ = item
            inst_name = Path(inst).stem
            done += 1
            print(
                f"[{done}/{total}] {solver_name} on {bench_name}/{inst_name} ...",
                end="",
                flush=True,
            )
            r = _run_one(item)
            results.append(r)
            tw = r["treewidth"] if r["treewidth"] is not None else "-"
            print(f" tw={tw} t={r['time_sec']}s [{r['status']}]")
    else:
        with ProcessPoolExecutor(max_workers=args.jobs) as pool:
            futures = {pool.submit(_run_one, item): item for item in work}
            for future in as_completed(futures):
                item = futures[future]
                solver_name, inst, _, bench_name, _ = item
                inst_name = Path(inst).stem
                done += 1
                r = future.result()
                results.append(r)
                tw = r["treewidth"] if r["treewidth"] is not None else "-"
                print(
                    f"[{done}/{total}] {solver_name} on {bench_name}/{inst_name}"
                    f" tw={tw} t={r['time_sec']}s [{r['status']}]",
                    flush=True,
                )

    # Write results
    if args.output:
        output_path = args.output
    else:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
        output_path = f"results/{timestamp}.csv"

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    write_csv(results, output_path)
    print(f"\nResults written to: {output_path}")

    # Summary
    ok_count = sum(1 for r in results if r["status"] == "ok")
    timeout_count = sum(1 for r in results if r["status"] == "timeout")
    error_count = total - ok_count - timeout_count
    print(f"Summary: {ok_count} ok, {timeout_count} timeout, {error_count} error")


if __name__ == "__main__":
    main()
