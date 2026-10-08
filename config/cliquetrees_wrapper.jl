# Wrapper for CliqueTrees.jl used by the benchmark runner.
#
# Usage: julia --project=. cliquetrees_wrapper.jl <instance.gr> [exact|heuristic]
#
# Reads a PACE .gr instance, computes a clique tree (= tree decomposition)
# and prints it in PACE .td format. "exact" (default) runs the positive-
# instance-driven Bouchitte-Todinca algorithm wrapped in the package's safe
# preprocessing (SafeRules(SafeSeparators(PIDBT()))); "heuristic" runs the
# package's default minimum-fill ordering (MF()).
#
# The instance is parsed here, not with CliqueTrees.readgr, which assumes
# the first non-comment line is the header and tolerates neither blank lines
# nor self-loops. The clique tree may be a forest when the graph is
# disconnected; its roots are chained so the output is a single tree, as the
# .td format requires.

using CliqueTrees
using Graphs

function read_pace_gr(path::AbstractString)
    n = -1
    g = nothing
    for raw in eachline(path)
        line = strip(raw)
        if isempty(line) || startswith(line, "c")
            continue
        end
        parts = split(line)
        if parts[1] == "p"
            n = parse(Int, parts[3])
            g = SimpleGraph(n)
        else
            g === nothing && error("edge line before the 'p' line in $(path)")
            u = parse(Int, parts[1])
            v = parse(Int, parts[2])
            u != v && add_edge!(g, u, v)
        end
    end
    g === nothing && error("missing 'p' problem line in $(path)")
    return g
end

function main()
    length(ARGS) >= 1 || error("usage: cliquetrees_wrapper.jl <instance.gr> [exact|heuristic]")
    mode = length(ARGS) >= 2 ? ARGS[2] : "exact"
    g = read_pace_gr(ARGS[1])
    alg = mode == "heuristic" ? MF() : SafeRules(SafeSeparators(PIDBT()))
    perm, tree = cliquetree(g; alg = alg)
    nbags = length(tree)
    if nbags == 0
        println("s td 1 1 ", nv(g))
        println("b 1")
        return
    end
    io = IOBuffer()
    println(io, "s td ", nbags, " ", treewidth(tree) + 1, " ", nv(g))
    for i in 1:nbags
        print(io, "b ", i)
        for v in perm[tree[i]]
            print(io, " ", v)
        end
        println(io)
    end
    prev_root = 0
    for i in 1:nbags
        p = CliqueTrees.AbstractTrees.parentindex(tree, i)
        if p === nothing
            prev_root != 0 && println(io, prev_root, " ", i)
            prev_root = i
        else
            println(io, p, " ", i)
        end
    end
    print(String(take!(io)))
end

main()
