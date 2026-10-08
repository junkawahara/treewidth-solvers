// Wrapper for LibTW used by the benchmark runner.
//
// Usage: java -cp bin LibtwRunner <instance.gr> [dp|quickbb|greedy]
//
// Reads a PACE .gr instance, builds a LibTW graph and prints the width found
// as "c width <w>", which the runner's parser understands. LibTW itself has
// no PACE reader (only DIMACS .dgf) and no .td writer, so the instance is
// parsed here. Modes:
//   dp       exact: Bodlaender et al. dynamic programming over vertex
//            subsets, seeded with the greedy fill-in upper bound (default)
//   quickbb  exact: LibTW's Java port of QuickBB branch and bound
//   greedy   heuristic: greedy fill-in upper bound only
// The build step copies this file into the solver directory, which is the
// cwd when the runner invokes it.

import java.io.BufferedReader;
import java.io.FileReader;
import java.io.IOException;
import java.util.ArrayList;

import nl.uu.cs.treewidth.algorithm.GreedyFillIn;
import nl.uu.cs.treewidth.algorithm.QuickBB;
import nl.uu.cs.treewidth.algorithm.TreewidthDP;
import nl.uu.cs.treewidth.input.GraphInput.InputData;
import nl.uu.cs.treewidth.ngraph.ListGraph;
import nl.uu.cs.treewidth.ngraph.ListVertex;
import nl.uu.cs.treewidth.ngraph.NGraph;
import nl.uu.cs.treewidth.ngraph.NVertex;

public class LibtwRunner {
    static NGraph<InputData> readPaceGr(String path) throws IOException {
        NGraph<InputData> g = new ListGraph<InputData>();
        ArrayList<NVertex<InputData>> vs = new ArrayList<NVertex<InputData>>();
        try (BufferedReader in = new BufferedReader(new FileReader(path))) {
            String line;
            while ((line = in.readLine()) != null) {
                line = line.trim();
                if (line.isEmpty() || line.startsWith("c")) continue;
                String[] parts = line.split("\\s+");
                if (parts[0].equals("p")) {
                    int n = Integer.parseInt(parts[2]);
                    for (int i = 0; i < n; i++) {
                        NVertex<InputData> v = new ListVertex<InputData>(
                            new InputData(i, Integer.toString(i + 1)));
                        vs.add(v);
                        g.addVertex(v);
                    }
                } else {
                    if (vs.isEmpty()) throw new IOException("edge line before the 'p' line");
                    int u = Integer.parseInt(parts[0]) - 1;
                    int v = Integer.parseInt(parts[1]) - 1;
                    // Self-loops have no bearing on treewidth; ensureEdge skips duplicates.
                    if (u != v) g.ensureEdge(vs.get(u), vs.get(v));
                }
            }
        }
        if (vs.isEmpty()) throw new IOException("missing 'p' problem line");
        return g;
    }

    public static void main(String[] args) throws IOException {
        if (args.length < 1) {
            System.err.println("usage: LibtwRunner <instance.gr> [dp|quickbb|greedy]");
            System.exit(2);
        }
        String mode = args.length >= 2 ? args[1] : "dp";
        NGraph<InputData> g = readPaceGr(args[0]);
        int width;
        if (mode.equals("greedy")) {
            GreedyFillIn<InputData> ub = new GreedyFillIn<InputData>();
            ub.setInput(g);
            ub.run();
            width = ub.getUpperBound();
        } else if (mode.equals("quickbb")) {
            QuickBB<InputData> qbb = new QuickBB<InputData>();
            qbb.setInput(g);
            qbb.run();
            width = qbb.getUpperBound();
        } else {
            TreewidthDP<InputData> dp = new TreewidthDP<InputData>(new GreedyFillIn<InputData>());
            dp.setInput(g);
            dp.run();
            width = dp.getTreewidth();
        }
        System.out.println("c width " + width);
    }
}
