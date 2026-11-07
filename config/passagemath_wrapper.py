# Wrapper for passagemath (SageMath's graph library) used by the benchmark runner.
#
# Usage: venv/bin/python -I passagemath_wrapper.py <instance.gr>
#
# Reads a PACE .gr instance, computes an optimal tree decomposition with
# Sage's own exact algorithm, Graph.treewidth(algorithm="sage",
# certificate=True), and prints it in PACE .td format.
#
# The "sage" algorithm decides "treewidth <= k" for increasing k by a
# dynamic programme over pairs (cut of at most k+1 vertices, connected
# component of the rest). It is chosen explicitly: the default would switch
# to tdlib when passagemath-tdlib is installed, which is the treedec code
# the suite already runs as tdlib-p17 and treedec.
#
# The instance is parsed here so that comment lines, blank lines,
# self-loops and parallel edges are tolerated, and so that isolated
# vertices named only by the "p tw n m" header are kept. Sage already
# joins the decompositions of the components into one tree; if a future
# version returns a forest, its components are chained here.

import sys


def read_pace_gr(path):
    n = None
    edges = set()
    with open(path) as f:
        for raw in f:
            parts = raw.split()
            if not parts or parts[0].startswith("c"):
                continue
            if parts[0] == "p":
                n = int(parts[2])
                continue
            if n is None:
                raise ValueError(f"edge line before the 'p' line in {path}")
            u, v = int(parts[0]), int(parts[1])
            if u != v:
                edges.add((min(u, v), max(u, v)))
    if n is None:
        raise ValueError(f"missing 'p' problem line in {path}")
    return n, sorted(edges)


def main():
    if len(sys.argv) != 2:
        print("usage: passagemath_wrapper.py <instance.gr>", file=sys.stderr)
        sys.exit(2)
    n, edges = read_pace_gr(sys.argv[1])

    from sage.all__sagemath_graphs import Graph

    if n == 0:
        print("s td 0 0 0")
        return

    g = Graph([list(range(1, n + 1)), edges], format="vertices_and_edges")
    t = g.treewidth(algorithm="sage", certificate=True)

    nodes = list(t.vertices(sort=False))
    index = {node: i + 1 for i, node in enumerate(nodes)}
    bags = [sorted(int(v) for v in node) for node in nodes]
    tree_edges = [(index[a], index[b]) for a, b, _ in t.edges(sort=False)]
    if not t.is_connected():
        reps = [index[c[0]] for c in t.connected_components(sort=False)]
        tree_edges += list(zip(reps, reps[1:]))

    out = sys.stdout
    max_bag = max(len(b) for b in bags)
    out.write(f"s td {len(bags)} {max_bag} {n}\n")
    for i, bag in enumerate(bags, 1):
        out.write("b " + " ".join([str(i)] + [str(v) for v in bag]) + "\n")
    for a, b in tree_edges:
        out.write(f"{a} {b}\n")
    out.flush()


if __name__ == "__main__":
    main()
