# Wrapper for TreeWidthSolver.jl used by the benchmark runner.
#
# Reads a PACE .gr instance (path given as the first argument), computes the
# exact treewidth, and prints it as "c width <w>", which the runner's parser
# understands. The build step copies this file into the solver directory,
# which is the cwd when the runner invokes it.
#
# The instance is parsed here rather than with the package's graph_from_gr,
# which treats the first line of the file as the "p tw n m" header and every
# later line as an edge. PACE instances may start with "c" comment lines
# (every file in tests/ does, and so do 30 benchmark instances), and may
# contain blank lines; those made graph_from_gr fail.

using TreeWidthSolver
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
            # Self-loops have no bearing on treewidth; SimpleGraph rejects them.
            u != v && add_edge!(g, u, v)
        end
    end
    g === nothing && error("missing 'p' problem line in $(path)")
    return g
end

function main()
    if length(ARGS) < 1
        error("usage: run_wrapper.jl <instance.gr>")
    end
    g = read_pace_gr(ARGS[1])
    tw = Int(round(exact_treewidth(g)))
    println("c width ", tw)
end

main()
