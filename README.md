# Isawa - Treewidth Solver Benchmark Suite

[日本語版 / Japanese](README_ja.md)

A toolkit for benchmarking multiple publicly available treewidth solvers through a unified interface.

## Prerequisites

Required:
- Python 3.8+
- Git

Per-solver dependencies:
- **Java solvers** (twalgor-tw, twalgor-rtw, tamaki-2017, tamaki-2016, jdrasil): JDK 8+
- **C++ solvers** (tdlib-p17, flowcutter-17, htd, minfill-mrs, minfillbg-mrs): GCC 4.8+, CMake (htd only), Boost (tdlib-p17 only), autotools (tdlib-p17 only)
- **QuickBB**: GCC, autotools (autoconf, automake)
- **TreeWidthSolver.jl**: Julia 1.6+

## Quick Start

```bash
# 1. List available solvers and benchmarks
python setup.py --list

# 2. Set up everything (download + build)
python setup.py --all

# 3. Set up specific solvers only
python setup.py --solver flowcutter-17 --solver tamaki-2017

# 4. Download benchmarks only
python setup.py --benchmarks-only

# 5. Run benchmarks
python run.py --solver all --benchmark pace2017-instances --timeout 300

# 6. Run with a specific solver
python run.py --solver flowcutter-17 --benchmark pace2017-instances --timeout 60

# 7. Parallel execution
python run.py --solver all --benchmark all --timeout 300 --jobs 4

# 8. Quick test (max 5 instances per benchmark set)
python run.py --solver all --benchmark all --timeout 60 --max-instances 5
```

## Solvers

### Exact Solvers

| Name | Author(s) | Language | Description |
|------|-----------|----------|-------------|
| twalgor-tw | Hisao Tamaki | Java | Heuristic computation of exact treewidth (2022) |
| twalgor-rtw | Hisao Tamaki | Java | Contraction-recursive algorithm (2023) |
| tamaki-2017 | Tamaki et al. | Java | PACE 2017 exact track winner |
| tamaki-2016 | Hisao Tamaki | C | PACE 2016 exact track winner |
| tdlib-p17 | Larisch, Salfelder | C++ | TDLIB PACE 2017 submission |
| jdrasil | Bannach et al. | Java | Modular treewidth solver framework |
| quickbb | Gogate, Dechter | C++ | Branch-and-bound exact solver |
| treewidth-solver-jl | ArrogantGao | Julia | Bouchitte-Todinca algorithm (Julia) |

### Heuristic Solvers

| Name | Author(s) | Language | Description |
|------|-----------|----------|-------------|
| flowcutter-17 | Ben Strasser | C++ | Nested dissection via max-flow (PACE 2016/2017) |
| htd | Abseher et al. | C++ | Hypertree/tree decomposition library (TU Wien) |
| minfill-mrs | Jegou et al. | C++ | Min-fill heuristic with restarts |
| minfillbg-mrs | Jegou et al. | C++ | Min-fill with bipartite graph improvements |

**Note**: tamaki-2017, tdlib-p17, and jdrasil support both exact and heuristic modes.

## Benchmarks

| Name | Source | Description |
|------|--------|-------------|
| pace2017-instances | PACE 2017 | Official competition instances |
| pace2017-bonus | PACE 2017 | Extra challenging bonus instances |
| pace2016-testbed | PACE 2016 | 2016 testbed (instances + tools) |
| named-graphs | Lukas Larisch | Named graph collection (Petersen, Hoffman, etc.) |
| control-flow-graphs | Lukas Larisch | Control flow graphs from compiled programs |
| uai2014-graphs | PACE / UAI 2014 | Graphs from probabilistic inference competition |
| transit-graphs | Johannes Fichte | Transit/transportation networks |
| road-graphs | Ben Strasser | Road networks |

## Output Format

Results are written as CSV files to the `results/` directory:

```
solver,benchmark_set,instance,vertices,edges,treewidth,time_sec,status,memory_mb
flowcutter-17,pace2017-instances,ex001,100,250,12,0.523,ok,
tamaki-2017,pace2017-instances,ex001,100,250,12,1.234,ok,
```

## PACE .gr Format

Standard input format for graphs:

```
c comment (optional)
p tw <num_vertices> <num_edges>
<u> <v>
```

Vertices are 1-indexed.

## License

This repository does not redistribute any solver or benchmark source code. All external code is downloaded at setup time via `git clone`. Each solver and benchmark set is subject to its own license:

### Solver Licenses

| Solver | License | Repository |
|--------|---------|------------|
| twalgor-tw | GPL-3.0 | [twalgor/tw](https://github.com/twalgor/tw) |
| twalgor-rtw | GPL-3.0 | [twalgor/RTW](https://github.com/twalgor/RTW) |
| tamaki-2017 | MIT | [TCS-Meiji/PACE2017-TrackA](https://github.com/TCS-Meiji/PACE2017-TrackA) |
| tamaki-2016 | MIT | [TCS-Meiji/treewidth-exact](https://github.com/TCS-Meiji/treewidth-exact) |
| tdlib-p17 | Not specified | [freetdi/p17](https://github.com/freetdi/p17) |
| jdrasil | MIT | [maxbannach/Jdrasil](https://github.com/maxbannach/Jdrasil) |
| quickbb | GPL-2.0 | [dechterlab/quickbb](https://github.com/dechterlab/quickbb) |
| treewidth-solver-jl | MIT | [ArrogantGao/TreeWidthSolver.jl](https://github.com/ArrogantGao/TreeWidthSolver.jl) |
| flowcutter-17 | BSD-2-Clause | [kit-algo/flow-cutter-pace17](https://github.com/kit-algo/flow-cutter-pace17) |
| htd | GPL-3.0 | [mabseher/htd](https://github.com/mabseher/htd) |
| minfill-mrs | GPL-3.0 | [td-mrs/minfill_mrs](https://github.com/td-mrs/minfill_mrs) |
| minfillbg-mrs | GPL-3.0 | [td-mrs/minfillbg_mrs](https://github.com/td-mrs/minfillbg_mrs) |

### Benchmark Licenses

| Benchmark | License | Repository |
|-----------|---------|------------|
| pace2017-instances | CC | [PACE-challenge/Treewidth-PACE-2017-instances](https://github.com/PACE-challenge/Treewidth-PACE-2017-instances) |
| pace2017-bonus | CC | [PACE-challenge/Treewidth-PACE-2017-bonus-instances](https://github.com/PACE-challenge/Treewidth-PACE-2017-bonus-instances) |
| pace2016-testbed | GPL-3.0 | [holgerdell/PACE-treewidth-testbed](https://github.com/holgerdell/PACE-treewidth-testbed) |
| named-graphs | Not specified | [freetdi/named-graphs](https://github.com/freetdi/named-graphs) |
| control-flow-graphs | CC | [freetdi/CFGs](https://github.com/freetdi/CFGs) |
| uai2014-graphs | CC | [PACE-challenge/UAI-2014-competition-graphs](https://github.com/PACE-challenge/UAI-2014-competition-graphs) |
| transit-graphs | Not specified | [daajoe/transit_graphs](https://github.com/daajoe/transit_graphs) |
| road-graphs | Public Domain / ODbL | [ben-strasser/road-graphs-pace16](https://github.com/ben-strasser/road-graphs-pace16) |

## References

- [PACE Challenge](https://pacechallenge.org/)
- [PACE Treewidth Collection](https://github.com/PACE-challenge/Treewidth)
- [td-validate (validation tool)](https://github.com/holgerdell/td-validate)
