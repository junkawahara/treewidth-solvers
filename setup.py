#!/usr/bin/env python3
"""Setup script: download and build treewidth solvers and benchmark instances."""

import argparse
import sys

from lib.solver_registry import load_solvers, setup_solver, setup_all as setup_all_solvers
from lib.benchmark_registry import (
    load_benchmarks,
    download_benchmark,
    setup_all as setup_all_benchmarks,
)


def main():
    parser = argparse.ArgumentParser(
        description="Download and build treewidth solvers and benchmark instances."
    )
    parser.add_argument(
        "--all", action="store_true", help="Set up all solvers and benchmarks"
    )
    parser.add_argument(
        "--solver",
        action="append",
        default=[],
        help="Set up a specific solver (can be repeated)",
    )
    parser.add_argument(
        "--benchmark",
        action="append",
        default=[],
        help="Download a specific benchmark set (can be repeated)",
    )
    parser.add_argument(
        "--solvers-only", action="store_true", help="Set up all solvers only"
    )
    parser.add_argument(
        "--benchmarks-only", action="store_true", help="Download all benchmarks only"
    )
    parser.add_argument(
        "--list", action="store_true", help="List available solvers and benchmarks"
    )
    args = parser.parse_args()

    if args.list:
        print("=== Available Solvers ===")
        for s in load_solvers():
            print(f"  {s['name']:25s} [{s['type']:10s}] {s['language']:6s}  {s['description']}")
        print()
        print("=== Available Benchmarks ===")
        for b in load_benchmarks():
            print(f"  {b['name']:25s} {b['description']}")
        return

    if not (args.all or args.solver or args.benchmark or args.solvers_only or args.benchmarks_only):
        parser.print_help()
        sys.exit(1)

    solver_results = {}
    bench_results = {}

    # Setup solvers
    if args.all or args.solvers_only:
        print("=" * 60)
        print("Setting up ALL solvers")
        print("=" * 60)
        solver_results = setup_all_solvers()
    elif args.solver:
        solvers = load_solvers()
        solver_map = {s["name"]: s for s in solvers}
        for name in args.solver:
            if name not in solver_map:
                print(f"Unknown solver: {name}")
                continue
            print(f"\n--- Setting up solver: {name} ---")
            solver_results[name] = setup_solver(solver_map[name])

    # Setup benchmarks
    if args.all or args.benchmarks_only:
        print("\n" + "=" * 60)
        print("Downloading ALL benchmarks")
        print("=" * 60)
        bench_results = setup_all_benchmarks()
    elif args.benchmark:
        benchmarks = load_benchmarks()
        bench_map = {b["name"]: b for b in benchmarks}
        for name in args.benchmark:
            if name not in bench_map:
                print(f"Unknown benchmark: {name}")
                continue
            print(f"\n--- Downloading benchmark: {name} ---")
            bench_results[name] = download_benchmark(bench_map[name])

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    if solver_results:
        print("\nSolvers:")
        for name, ok in solver_results.items():
            status = "OK" if ok else "FAILED"
            print(f"  {name:25s} {status}")
    if bench_results:
        print("\nBenchmarks:")
        for name, ok in bench_results.items():
            status = "OK" if ok else "FAILED"
            print(f"  {name:25s} {status}")


if __name__ == "__main__":
    main()
