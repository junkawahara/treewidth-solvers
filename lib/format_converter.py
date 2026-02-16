"""Format converter: convert between graph file formats.

Supported formats:
  - pace_gr: PACE .gr format (standard)
  - quickbb_cnf: QuickBB CNF-like format
"""

from pathlib import Path


def read_pace_gr(filepath):
    """Read a PACE .gr file and return (n_vertices, edges)."""
    n = 0
    m = 0
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
        # twalgor-rtw .twc format: "c width <w>"
        if line.startswith("c width "):
            parts = line.split()
            return {"treewidth": int(parts[2])}
    return None
