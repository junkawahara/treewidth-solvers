"""Validate tree decompositions against the input graph.

Checks the three conditions of a valid tree decomposition:
1. Every vertex appears in at least one bag.
2. For every edge (u,v), there exists a bag containing both u and v.
3. For every vertex v, the bags containing v form a connected subtree.
"""

from collections import defaultdict, deque
from lib.format_converter import read_pace_gr


def parse_td(text):
    """Parse .td format text.

    Returns (bags, tree_edges, n_bags, width_plus_one, n_vertices, problems).
    problems lists structural defects found while parsing -- a bag id given
    twice, a tree edge naming a bag that does not exist -- as human-readable
    strings; validate() reports them as validation errors so the cause is
    named directly instead of showing up only as a bag-count mismatch.

    Raises ValueError (never IndexError) on a header, bag or tree-edge line
    that cannot be parsed: a short "s td" header, a "b" line with no id, or
    non-integer tokens. Other lines are ignored as before.
    """
    bags = {}
    tree_edges = []
    n_bags = 0
    width_plus_one = 0
    n_vertices = 0
    problems = []
    seen_header = False

    for lineno, raw in enumerate(text.strip().split("\n"), 1):
        line = raw.strip()
        if not line or line.startswith("c"):
            continue
        parts = line.split()
        try:
            if line.startswith("s td"):
                if len(parts) < 5:
                    raise ValueError(
                        f"line {lineno}: expected 's td <bags> <width+1> <n>', "
                        f"got {line!r}"
                    )
                if seen_header:
                    problems.append(f"line {lineno}: second 's td' header")
                seen_header = True
                n_bags = int(parts[2])
                width_plus_one = int(parts[3])
                n_vertices = int(parts[4])
            elif parts[0] == "b":
                if len(parts) < 2:
                    raise ValueError(f"line {lineno}: bag line without an id")
                bag_id = int(parts[1])
                vertices = set(int(x) for x in parts[2:])
                if bag_id in bags:
                    problems.append(f"line {lineno}: bag {bag_id} is defined twice")
                bags[bag_id] = vertices
            elif len(parts) == 2:
                tree_edges.append((int(parts[0]), int(parts[1])))
            # Anything else is solver chatter (tamaki-2016 prints
            # "width = 2" progress lines on stdout) and is ignored.
        except ValueError as e:
            if str(e).startswith(f"line {lineno}:"):
                raise
            raise ValueError(f"line {lineno}: non-integer token in {line!r}") from None

    for a, b in tree_edges:
        for x in (a, b):
            if x not in bags:
                problems.append(f"Tree edge ({a},{b}) refers to missing bag {x}")

    return bags, tree_edges, n_bags, width_plus_one, n_vertices, problems


def validate(graph_path, td_text):
    """Validate a tree decomposition.

    Returns (is_valid, treewidth, errors) tuple.
    """
    n, edges = read_pace_gr(graph_path)
    bags, tree_edges, n_bags, width_plus_one, td_n, problems = parse_td(td_text)
    errors = list(problems)

    if not bags:
        return False, -1, errors + ["No bags found in decomposition"]

    # Check 0: the bags must form a tree -- connected and acyclic. Without this
    # a "forest" with too few tree edges, or bags wired into a cycle, would pass
    # validation and a bogus width smaller than the true treewidth be accepted.
    bag_ids = set(bags.keys())
    undirected = set()
    for a, b in tree_edges:
        if a == b:
            continue
        undirected.add((min(a, b), max(a, b)))
    tree_adj = defaultdict(set)
    for a, b in undirected:
        tree_adj[a].add(b)
        tree_adj[b].add(a)
    start = next(iter(bag_ids))
    seen = {start}
    dq = deque([start])
    while dq:
        cur = dq.popleft()
        for nb in tree_adj[cur]:
            if nb in bag_ids and nb not in seen:
                seen.add(nb)
                dq.append(nb)
    if seen != bag_ids:
        errors.append("Decomposition tree is not connected")
    if len(undirected) != len(bag_ids) - 1:
        errors.append(
            f"Decomposition has {len(undirected)} tree edges, "
            f"expected {len(bag_ids) - 1} for a tree"
        )

    # Check 1: every vertex appears in at least one bag
    all_bag_vertices = set()
    for vset in bags.values():
        all_bag_vertices.update(vset)
    for v in range(1, n + 1):
        if v not in all_bag_vertices:
            errors.append(f"Vertex {v} not in any bag")

    # Check 1b: no bag may contain a vertex outside 1..n. Out-of-range vertices
    # are not part of the graph and would inflate the computed bag width.
    for v in sorted(all_bag_vertices):
        if v < 1 or v > n:
            errors.append(f"Bag contains out-of-range vertex {v} (graph has {n})")

    # Index: vertex -> set of bag ids containing it. Shared by checks 2 and 3.
    vertex_to_bags = defaultdict(set)
    for bag_id, vset in bags.items():
        for v in vset:
            vertex_to_bags[v].add(bag_id)

    # Check 2: every edge is covered, i.e. some bag contains both endpoints.
    # Intersect the two endpoints' bag sets instead of scanning every bag per
    # edge: the old scan was O(edges x bags) and took hours on road graphs
    # with hundreds of thousands of edges and bags.
    for u, v in edges:
        bu = vertex_to_bags.get(u)
        bv = vertex_to_bags.get(v)
        if not bu or not bv or bu.isdisjoint(bv):
            errors.append(f"Edge ({u},{v}) not covered by any bag")

    # Check 3: connected subtree property
    adj = defaultdict(set)
    for a, b in tree_edges:
        adj[a].add(b)
        adj[b].add(a)

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

    # Check 4: the "s td" header must agree with the actual decomposition. A
    # mismatch (wrong bag count, wrong declared width, wrong vertex count)
    # signals a malformed or dishonest output, which PACE's td-validate rejects.
    if n_bags != len(bags):
        errors.append(
            f"Header declares {n_bags} bags but {len(bags)} are present"
        )
    if td_n != n:
        errors.append(
            f"Header declares {td_n} vertices but the graph has {n}"
        )
    max_bag = max(len(vset) for vset in bags.values())
    if width_plus_one != max_bag:
        errors.append(
            f"Header declares width+1={width_plus_one} but the largest bag has "
            f"{max_bag} vertices"
        )

    is_valid = len(errors) == 0
    return is_valid, treewidth, errors
