"""Format converter: convert between graph file formats.

Supported formats:
  - pace_gr: PACE .gr format (standard)
  - quickbb_cnf: QuickBB CNF-like format
"""

from pathlib import Path


def read_pace_gr(filepath):
    """Read a PACE .gr file and return (n_vertices, edges).

    Raises ValueError if the file has no problem line or if the number of edge
    lines does not match the count declared on the "p" line -- a truncated or
    malformed instance should be reported, not silently accepted.
    """
    n = 0
    m = None
    edges = []
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
                edges.append((u, v))
    if m is None:
        raise ValueError(f"{filepath}: missing 'p' problem line")
    if len(edges) != m:
        raise ValueError(
            f"{filepath}: declared {m} edges but found {len(edges)}"
        )
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
    """
    n, edges = read_pace_gr(input_path)
    with open(output_path, "w") as f:
        f.write(f"p cnf {n} {len(edges)}\n")
        for u, v in edges:
            f.write(f"{u} {v} 0\n")
    return output_path


def get_graph_info(filepath):
    """Get basic graph statistics from a .gr file."""
    n, edges = read_pace_gr(filepath)
    return {"vertices": n, "edges": len(edges)}


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
