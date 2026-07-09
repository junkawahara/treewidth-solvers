# Wrapper for TreeWidthSolver.jl used by the benchmark runner.
#
# Reads a PACE .gr instance (path given as the first argument), computes the
# exact treewidth, and prints it in a form the runner's parser understands
# ("c width <w>" plus a bare number as a fallback). The build step copies this
# file into the solver directory, which is the cwd when the runner invokes it.

using TreeWidthSolver

function main()
    if length(ARGS) < 1
        error("usage: run_wrapper.jl <instance.gr>")
    end
    g = graph_from_gr(ARGS[1])
    tw = Int(round(exact_treewidth(g)))
    println("c width ", tw)
    println(tw)
end

main()
