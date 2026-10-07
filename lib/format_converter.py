"""Format converter: convert between graph file formats.

Supported formats:
  - pace_gr: PACE .gr format (standard)
  - quickbb_cnf: QuickBB CNF-like format
"""

from pathlib import Path


def _scan_pace_gr(filepath, on_edge=None):
    """Stream through a PACE .gr file; return (n_vertices, n_edges).

    Calls on_edge(u, v) for every edge line when given. Nothing is retained
    otherwise, so counting a multi-hundred-megabyte road graph needs no more
    memory than one line.

    Raises ValueError if the file has no problem line or if the number of edge
    lines does not match the count declared on the "p" line -- a truncated or
    malformed instance should be reported, not silently accepted.
    """
    n = 0
    m = None
    count = 0
    with open(filepath) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("c"):
                continue
            if line.startswith("p"):
                parts = line.split()
                n = int(parts[2])
                m = int(parts[3])
            else:
                parts = line.split()
                u, v = int(parts[0]), int(parts[1])
                count += 1
                if on_edge is not None:
                    on_edge(u, v)
    if m is None:
        raise ValueError(f"{filepath}: missing 'p' problem line")
    if count != m:
        raise ValueError(
            f"{filepath}: declared {m} edges but found {count}"
        )
    return n, count


def read_pace_gr(filepath):
    """Read a PACE .gr file and return (n_vertices, edges).

    Use get_graph_info when only the counts are needed; this materialises
    every edge in memory. Raises ValueError as described in _scan_pace_gr.
    """
    edges = []
    n, _ = _scan_pace_gr(filepath, lambda u, v: edges.append((u, v)))
    return n, edges


def write_pace_gr(filepath, n, edges):
    """Write a graph in PACE .gr format."""
    with open(filepath, "w") as f:
        f.write(f"p tw {n} {len(edges)}\n")
        for u, v in edges:
            f.write(f"{u} {v}\n")


def pace_gr_to_quickbb_cnf(input_path, output_path):
    """Convert PACE .gr to QuickBB CNF format.

    QuickBB CNF format:
      p cnf <n_vertices> <n_edges>
      <u> <v> 0

    Self-loops are dropped and parallel edges (u v / v u, or repeated lines)
    are written once. Neither affects treewidth, but quickbb's reader turns
    "u u 0" into a self-loop in its adjacency matrix and adds a parallel edge
    twice, which corrupts its degree bookkeeping. PACE instances do contain
    both (tens of thousands in the transit graphs).
    """
    unique = set()

    def collect(u, v):
        if u != v:
            unique.add((min(u, v), max(u, v)))

    n, _ = _scan_pace_gr(input_path, collect)
    edges = sorted(unique)
    with open(output_path, "w") as f:
        f.write(f"p cnf {n} {len(edges)}\n")
        for u, v in edges:
            f.write(f"{u} {v} 0\n")
    return output_path


def get_graph_info(filepath):
    """Get basic graph statistics from a .gr file without storing its edges."""
    n, m = _scan_pace_gr(filepath)
    return {"vertices": n, "edges": m}


def parse_quickbb_stat(text):
    """Parse a quickbb --statfile line and report whether the bound is proven.

    quickbb writes one space-separated row per run:
      <n> <m> <lb> <bound> <time> <nodes_visited> <nodes_pruned> <optimal>
    where <optimal> is 1 if the branch-and-bound finished and 0 if it stopped
    at its --time limit, in which case <bound> is only an upper bound. The
    "Treewidth=" line on stdout is printed in both cases, so this file is the
    only way to tell a proven treewidth from a timed-out bound.

    Returns {"bound": int, "optimal": bool} for the last complete row, or
    None if no such row exists.
    """
    parsed = None
    for line in text.strip().splitlines():
        parts = line.split()
        if len(parts) < 8:
            continue
        try:
            parsed = {"bound": int(parts[3]), "optimal": parts[7] == "1"}
        except ValueError:
            continue
    return parsed


def parse_td_output(text):
    """Parse tree decomposition output (.td format) and extract treewidth.

    Returns dict with 'treewidth', 'n_bags', 'n_vertices' or None on failure.
    """
    for line in text.strip().split("\n"):
        line = line.strip()
        if line.startswith("s td"):
            parts = line.split()
            n_bags = int(parts[2])
            width_plus_one = int(parts[3])
            n_vertices = int(parts[4])
            return {
                "treewidth": width_plus_one - 1,
                "n_bags": n_bags,
                "n_vertices": n_vertices,
            }
        # "c width <w>" (twalgor-rtw) or "c width = <w>" (tamaki-2016)
        if line.startswith("c width"):
            nums = [x for x in line.split() if x.isdigit()]
            if nums:
                return {"treewidth": int(nums[0])}
        # "Treewidth= <w>" (quickbb)
        if line.startswith("Treewidth="):
            nums = [x for x in line.split() if x.isdigit()]
            if nums:
                return {"treewidth": int(nums[0])}
    return None
