"""Validate tree decompositions against the input graph.

Checks the three conditions of a valid tree decomposition:
1. Every vertex appears in at least one bag.
2. For every edge (u,v), there exists a bag containing both u and v.
3. For every vertex v, the bags containing v form a connected subtree.
"""

from collections import defaultdict, deque
from lib.format_converter import read_pace_gr


def parse_td(text):
    """Parse .td format text into bags and tree edges."""
    bags = {}
    tree_edges = []
    n_bags = 0
    width_plus_one = 0
    n_vertices = 0

    for line in text.strip().split("\n"):
        line = line.strip()
        if not line or line.startswith("c"):
            continue
        if line.startswith("s td"):
            parts = line.split()
            n_bags = int(parts[2])
            width_plus_one = int(parts[3])
            n_vertices = int(parts[4])
        elif line.startswith("b"):
            parts = line.split()
            bag_id = int(parts[1])
            vertices = set(int(x) for x in parts[2:])
            bags[bag_id] = vertices
        else:
            parts = line.split()
            if len(parts) == 2:
                tree_edges.append((int(parts[0]), int(parts[1])))

    return bags, tree_edges, n_bags, width_plus_one, n_vertices


def validate(graph_path, td_text):
    """Validate a tree decomposition.

    Returns (is_valid, treewidth, errors) tuple.
    """
    n, edges = read_pace_gr(graph_path)
    bags, tree_edges, n_bags, width_plus_one, td_n = parse_td(td_text)
    errors = []

    if not bags:
        return False, -1, ["No bags found in decomposition"]

    # Check 1: every vertex appears in at least one bag
    all_bag_vertices = set()
    for vset in bags.values():
        all_bag_vertices.update(vset)
    for v in range(1, n + 1):
        if v not in all_bag_vertices:
            errors.append(f"Vertex {v} not in any bag")

    # Check 2: every edge is covered
    for u, v in edges:
        found = False
        for vset in bags.values():
            if u in vset and v in vset:
                found = True
                break
        if not found:
            errors.append(f"Edge ({u},{v}) not covered by any bag")

    # Check 3: connected subtree property
    adj = defaultdict(set)
    for a, b in tree_edges:
        adj[a].add(b)
        adj[b].add(a)

    vertex_to_bags = defaultdict(set)
    for bag_id, vset in bags.items():
        for v in vset:
            vertex_to_bags[v].add(bag_id)

    for v in all_bag_vertices:
        v_bags = vertex_to_bags[v]
        if len(v_bags) <= 1:
            continue
        start = next(iter(v_bags))
        visited = {start}
        queue = deque([start])
        while queue:
            curr = queue.popleft()
            for nb in adj[curr]:
                if nb not in visited and nb in v_bags:
                    visited.add(nb)
                    queue.append(nb)
        if visited != v_bags:
            errors.append(f"Bags for vertex {v} are not connected")

    treewidth = max(len(vset) for vset in bags.values()) - 1
    is_valid = len(errors) == 0
    return is_valid, treewidth, errors
