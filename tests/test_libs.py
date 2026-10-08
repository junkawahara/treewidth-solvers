"""Unit tests for the pure-Python library helpers.

Run with pytest (``pytest tests/``) or directly (``python tests/test_libs.py``).
These exercise the parsing/conversion/validation code against the small
reference graphs in this directory, whose treewidths are known:
k4 = 3, cycle5 = 2, path4 = 1.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.format_converter import (  # noqa: E402
    get_graph_info,
    pace_gr_to_quickbb_cnf,
    parse_quickbb_stat,
    parse_td_output,
    read_pace_gr,
)
import lib.runner as runner  # noqa: E402
from lib.runner import CSV_FIELDS, ResultWriter, write_csv  # noqa: E402
from lib.validator import validate  # noqa: E402
from lib.clone_check import (  # noqa: E402
    adopt_or_reject_existing,
    is_complete_clone,
)

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))


def _gr(name):
    return os.path.join(TESTS_DIR, name)


def _assert_raises(exc_type, fn, *args, **kwargs):
    """pytest.raises substitute that also works under the plain runner.

    Unlike a bare try/except it fails on the wrong exception type (an
    IndexError escaping a parser that promises ValueError) as well as on no
    exception at all.
    """
    try:
        fn(*args, **kwargs)
    except exc_type:
        return
    except Exception as e:  # noqa: BLE001
        raise AssertionError(
            f"expected {exc_type.__name__}, got {type(e).__name__}: {e}"
        )
    raise AssertionError(f"expected {exc_type.__name__}, nothing was raised")


def test_read_pace_gr_counts():
    assert get_graph_info(_gr("k4.gr")) == {"vertices": 4, "edges": 6}
    assert get_graph_info(_gr("cycle5.gr")) == {"vertices": 5, "edges": 5}
    assert get_graph_info(_gr("path4.gr")) == {"vertices": 4, "edges": 3}


def test_get_graph_info_streams_without_storing_edges(tmp_path):
    """Counting must not materialise the edge list (road graphs are huge)."""
    import tracemalloc

    gr = tmp_path / "big.gr"
    m = 200_000
    with open(gr, "w") as f:
        f.write(f"p tw {m + 1} {m}\n")
        f.writelines(f"{i} {i + 1}\n" for i in range(1, m + 1))
    tracemalloc.start()
    info = get_graph_info(str(gr))
    _cur, peak_info = tracemalloc.get_traced_memory()
    tracemalloc.reset_peak()
    n, edges = read_pace_gr(str(gr))
    _cur, peak_read = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    assert info == {"vertices": m + 1, "edges": m} and (n, len(edges)) == (m + 1, m)
    # The full read holds ~m tuples; the count must stay far below that.
    assert peak_info < peak_read / 10, (peak_info, peak_read)


def test_get_graph_info_rejects_malformed_files(tmp_path):
    bad = tmp_path / "bad.gr"
    bad.write_text("p tw 4 6\n1 2\n2 3\n")
    _assert_raises(ValueError, get_graph_info, str(bad))
    nop = tmp_path / "nop.gr"
    nop.write_text("c only a comment\n")
    _assert_raises(ValueError, get_graph_info, str(nop))


def test_run_solver_uses_precomputed_graph_info(tmp_path):
    """A read error recorded up front is reported without re-reading the file."""
    missing = str(tmp_path / "does-not-exist.gr")
    r = runner.run_solver(
        "flowcutter-17", missing, timeout=1,
        graph_info=ValueError("declared 6 edges but found 2"),
    )
    assert r["status"] == "error: declared 6 edges but found 2"
    assert r["vertices"] is None and r["treewidth"] is None
    assert "_debug" not in r
    # With --debug the reason is available for _print_debug to show.
    r = runner.run_solver(
        "flowcutter-17", missing, timeout=1, debug=True,
        graph_info=ValueError("declared 6 edges but found 2"),
    )
    assert "declared 6 edges" in r["_debug"]["stderr"]
    assert r["_debug"]["command"] == ""
    r = runner.run_solver("flowcutter-17", missing, timeout=1, debug=True)
    assert r["status"].startswith("error: [Errno 2]")
    assert "does-not-exist.gr" in r["_debug"]["stderr"]


def test_read_pace_gr_rejects_edge_count_mismatch(tmp_path):
    bad = tmp_path / "bad.gr"
    bad.write_text("p tw 4 6\n1 2\n2 3\n")  # declares 6 edges, lists 2
    _assert_raises(ValueError, read_pace_gr, str(bad))


def test_read_pace_gr_reports_malformed_lines_as_value_error(tmp_path):
    """Every malformed input is a ValueError naming the line, not an IndexError."""
    cases = {
        "p tw\n": "expected 'p tw",            # p line with no counts
        "p td 4 3\n1 2\n2 3\n3 4\n": "expected 'p tw",  # wrong keyword
        "p tw 4 3\n1 2\np tw 4 3\n2 3\n3 4\n": "second 'p' line",
        "1 2\np tw 2 1\n": "before the 'p' line",
        "p tw 4 3\n1\n2 3\n3 4\n": "expected '<u> <v>'",
        "p tw 4 3\n1 2 3\n2 3\n3 4\n": "expected '<u> <v>'",
        "p tw 4 3\n1 x\n2 3\n3 4\n": "non-integer vertex",
        "p tw 4 3\n1 2\n2 3\n3 5\n": "outside 1..4",
        "p tw 4 3\n0 2\n2 3\n3 4\n": "outside 1..4",
        "p tw x 3\n": "non-integer counts",
    }
    for text, msg in cases.items():
        f = tmp_path / "bad.gr"
        f.write_text(text)
        try:
            read_pace_gr(str(f))
        except ValueError as e:
            assert msg in str(e), (text, str(e))
        else:
            raise AssertionError(f"accepted malformed input {text!r}")
    good = tmp_path / "good.gr"
    good.write_text("c comment\n\np tw 3 2\n1 2\n\n2 3\n")
    assert read_pace_gr(str(good)) == (3, [(1, 2), (2, 3)])


def test_quickbb_cnf_conversion(tmp_path):
    out = tmp_path / "k4.cnf"
    pace_gr_to_quickbb_cnf(_gr("k4.gr"), str(out))
    lines = out.read_text().strip().splitlines()
    assert lines[0] == "p cnf 4 6"
    assert lines[1].endswith(" 0")
    assert len(lines) == 7  # header + 6 edges


def test_quickbb_cnf_conversion_drops_self_loops_and_parallel_edges(tmp_path):
    gr = tmp_path / "multi.gr"
    # 3 vertices; self-loop on 1, edge 1-2 given three times (1 2, 2 1, 1 2),
    # plus 2-3. The simple graph underneath has exactly two edges.
    gr.write_text("p tw 3 5\n1 1\n1 2\n2 1\n1 2\n2 3\n")
    out = tmp_path / "multi.cnf"
    pace_gr_to_quickbb_cnf(str(gr), str(out))
    lines = out.read_text().strip().splitlines()
    assert lines == ["p cnf 3 2", "1 2 0", "2 3 0"]


def test_parse_td_output_formats():
    assert parse_td_output("s td 3 2 4\nb 1 1 2\n")["treewidth"] == 1
    assert parse_td_output("c width 3")["treewidth"] == 3
    assert parse_td_output("Treewidth= 5")["treewidth"] == 5
    assert parse_td_output("garbage") is None
    # tamaki-2016: the width is the first number, never the time field.
    assert parse_td_output("c width = 17, time = 0.215000")["treewidth"] == 17
    assert parse_td_output("c width = 9, time = 1")["treewidth"] == 9
    # A bare integer line is not a result (JVM warnings, progress output).
    assert parse_td_output("c status 4 1791\n7\n") is None
    assert parse_td_output("c widths are 5") is None


def test_parse_td_output_prefers_header_over_width_lines():
    # tamaki-2016 prints "c width = ..." before the "s td" header; the header
    # is authoritative even when a width line comes first, or disagrees.
    out = "c width = 3, time = 0.03\ns td 1 4 4\nb 1 1 2 3 4\n"
    assert parse_td_output(out) == {"treewidth": 3, "n_bags": 1, "n_vertices": 4}
    out = "c width 9\ns td 2 3 5\nb 1 1 2 3\nb 2 3 4 5\n1 2\n"
    assert parse_td_output(out)["treewidth"] == 2
    _assert_raises(ValueError, parse_td_output, "s td 3 2\n")


def test_is_full_td_requires_header_and_a_bag():
    assert runner._is_full_td("s td 1 2 2\nb 1 1 2\n")
    assert runner._is_full_td("c x\nb 1 1 2\ns td 1 2 2\n")  # order-independent
    assert not runner._is_full_td("s td 1 2 2\n")  # header only: truncated
    assert not runner._is_full_td("c width 3\n")  # width-only output
    assert not runner._is_full_td("b 1 1 2\n1 2\n")  # bags without header


def test_parse_quickbb_stat_distinguishes_proven_from_timed_out():
    # n m lb bound time visited pruned optimal
    assert parse_quickbb_stat("27 135 0 17 0.33 120 45 1\n") == {
        "bound": 17, "optimal": True,
    }
    assert parse_quickbb_stat("70 105 0 16 29.3 9000 100 0\n") == {
        "bound": 16, "optimal": False,
    }
    # Appended runs: the last complete row wins; junk rows are skipped.
    text = "1 2 3\n70 105 0 16 29.3 9000 100 0\n27 135 0 17 0.33 120 45 1\n"
    assert parse_quickbb_stat(text)["optimal"] is True
    assert parse_quickbb_stat("") is None
    assert parse_quickbb_stat("Treewidth= 5\n") is None


def _row(instance, status="ok", tw=1):
    return {"solver": "s", "mode": "exact", "benchmark_set": "b", "instance": instance,
            "vertices": 4, "edges": 3, "treewidth": tw, "time_sec": 0.5,
            "status": status, "memory_mb": None}


def test_result_writer_flushes_each_row_before_close(tmp_path):
    out = tmp_path / "sub" / "r.csv"  # parent dir is created on demand
    w = ResultWriter(out)
    w.write(_row("a"))
    w.write(_row("b", status="timeout", tw=None))
    # Still open, but everything written so far must already be on disk so an
    # interrupted run loses nothing.
    lines = out.read_text().splitlines()
    assert lines[0] == ",".join(CSV_FIELDS)
    assert lines[1].startswith("s,exact,b,a,4,3,1,0.5,ok,")
    assert lines[2].startswith("s,exact,b,b,4,3,,0.5,timeout,")
    assert len(lines) == 3 and w.count == 2
    w.close()
    w.close()  # idempotent


def test_write_csv_matches_incremental_writer(tmp_path):
    a, b = tmp_path / "a.csv", tmp_path / "b.csv"
    rows = [_row("x"), _row("y", status="error: boom", tw=None)]
    write_csv(rows, a)
    with ResultWriter(b) as w:
        for r in rows:
            w.write(r)
    assert a.read_text() == b.read_text()
    write_csv([], tmp_path / "none.csv")
    assert not (tmp_path / "none.csv").exists()


def test_resolve_names_dedupes_and_separates_unknown_from_uninstalled():
    import run as run_mod

    known = {"a", "b", "c"}
    installed = {"a": True, "b": False, "c": True}
    resolved, unknown = run_mod._resolve(
        ["a", "typo", "a", "b", "c"], "solver", known, installed.__getitem__,
        lambda: ["a", "c"],
    )
    assert resolved == ["a", "c"]  # duplicate dropped, b not installed
    assert unknown == ["typo"]
    resolved, unknown = run_mod._resolve(
        ["all", "typo"], "solver", known, installed.__getitem__, lambda: ["a", "c"]
    )
    assert resolved == ["a", "c"] and unknown == []


def test_solver_is_installed_requires_config_entry(tmp_path):
    import lib.solver_registry as reg

    orig = reg.SOLVERS_DIR
    reg.SOLVERS_DIR = tmp_path
    try:
        (tmp_path / "stray").mkdir()
        (tmp_path / "stray" / reg.BUILD_MARKER).write_text("ok\n")
        assert not reg.is_installed("stray")
        (tmp_path / "flowcutter-17").mkdir()
        assert not reg.is_installed("flowcutter-17")
        (tmp_path / "flowcutter-17" / reg.BUILD_MARKER).write_text("ok\n")
        assert reg.is_installed("flowcutter-17")
    finally:
        reg.SOLVERS_DIR = orig


def test_cli_rejects_out_of_range_numbers():
    import argparse
    import run as run_mod

    assert run_mod._positive_int("3") == 3
    assert run_mod._non_negative_int("0") == 0
    for fn, bad in ((run_mod._positive_int, "0"), (run_mod._positive_int, "-2"),
                    (run_mod._non_negative_int, "-1")):
        _assert_raises(argparse.ArgumentTypeError, fn, bad)


def test_summary_counts_each_status_separately():
    import run as run_mod

    rows = [_row("a"), _row("b", status="timeout"), _row("c", status="invalid"),
            _row("d", status="parse_error"), _row("e", status="error: exit 1"),
            _row("f", status="error: boom"), _row("g", status="invalid")]
    assert run_mod.summarize(rows) == (
        "Summary: 1 ok, 1 timeout, 2 invalid, 1 parse_error, 2 error"
    )
    assert run_mod.summarize([_row("a")]) == "Summary: 1 ok, 0 timeout"


def _sleepers_alive(tag):
    import subprocess

    r = subprocess.run(["pgrep", "-f", f"sleep {tag}"], capture_output=True, text=True)
    return [pid for pid in r.stdout.split() if pid != str(os.getpid())]


def test_interrupt_during_solver_kills_whole_process_group(tmp_path):
    """A KeyboardInterrupt while waiting on the solver must not orphan it.

    The command spawns a grandchild too (like the shell wrappers around the
    JVM solvers); both must be gone after the interrupt propagates.
    """
    import signal

    tag = f"31.4159{os.getpid() % 1000}"
    cmd = f"sleep {tag} & sleep {tag}"

    def alarm(signum, frame):
        raise KeyboardInterrupt

    old = signal.signal(signal.SIGALRM, alarm)
    try:
        signal.setitimer(signal.ITIMER_REAL, 0.5)
        try:
            runner._run_with_timeout(cmd, str(tmp_path), None, timeout=30)
        except KeyboardInterrupt:
            pass
        else:
            raise AssertionError("KeyboardInterrupt did not propagate")
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old)
    assert _sleepers_alive(tag) == []
    assert runner._current_proc is None


def test_group_memory_uses_pss_and_counts_the_whole_group(tmp_path):
    """Two processes sharing one big file mapping count it about once."""
    import subprocess
    import time as _time

    if not os.path.exists("/proc/self/smaps_rollup"):
        return  # PSS unavailable; RSS fallback is exercised implicitly
    # A child that maps and touches ~64 MB, then forks: parent and child share
    # the pages, so PSS over the group is ~64 MB while RSS would be ~128 MB.
    code = (
        "import os, time, mmap\n"
        "m = mmap.mmap(-1, 64 << 20)\n"
        "m.write(b'x' * (64 << 20))\n"
        "pid = os.fork()\n"
        "time.sleep(3)\n"
    )
    p = subprocess.Popen([sys.executable, "-c", code], start_new_session=True)
    try:
        _time.sleep(1.0)
        kb = runner._group_rss_kb(p.pid)
        own = runner._proc_mem_kb(p.pid)
    finally:
        runner._kill_group(p, 9)
        p.wait()
    assert 60_000 < kb < 110_000, kb      # shared pages not double counted
    assert own < kb                       # ...but the child is included


def test_internal_time_limit_keeps_a_useful_budget_for_short_timeouts():
    f = runner.internal_time_limit
    assert f(300) == 290 and f(60) == 50 and f(40) == 30
    # Below 40 s the margin shrinks with the timeout instead of eating it.
    assert f(20) == 15 and f(11) == 9 and f(8) == 6 and f(4) == 3
    assert f(2) == 1 and f(1) == 1
    for t in range(1, 400):
        assert 1 <= f(t) <= t


def test_run_with_timeout_tolerates_non_utf8_output(tmp_path):
    out, err, timed_out, killed, rc, _mb = runner._run_with_timeout(
        "printf 's td 1 2 2\\n\\377\\376 junk\\n'; printf '\\377' >&2",
        str(tmp_path), None, timeout=5,
    )
    assert not timed_out and not killed and rc == 0
    assert out.startswith("s td 1 2 2\n") and "\ufffd" in out and "\ufffd" in err


def test_run_with_timeout_reports_kill_after_grace(tmp_path):
    """A solver that ignores SIGTERM is SIGKILLed after the grace period and
    the call reports killed=True; one that exits on SIGTERM is not killed."""
    import time as _time

    t0 = _time.monotonic()
    out, _err, timed_out, killed, rc, _mb = runner._run_with_timeout(
        "trap '' TERM; echo s td 1 1 1; sleep 30", str(tmp_path), None,
        timeout=0.3, grace=0.5,
    )
    assert timed_out and killed and rc != 0
    assert _time.monotonic() - t0 < 10
    out, _err, timed_out, killed, _rc, _mb = runner._run_with_timeout(
        "echo s td 1 1 1; sleep 30", str(tmp_path), None, timeout=0.3, grace=5,
    )
    assert timed_out and not killed
    assert "s td 1 1 1" in out


def test_run_solver_classifies_nonzero_exit_as_error(tmp_path):
    """Output printed before a crash must not be recorded as ok."""
    import lib.solver_registry as reg

    fake = {
        "name": "fake", "type": "exact", "language": "c",
        "run_command": "echo 's td 1 1 1'; echo 'b 1 1'; exit 3",
        "run_mode": "stdin_stdout", "input_format": "pace_gr",
        "output_format": "pace_td",
    }
    orig_get, orig_dir = runner.get_solver, runner.solver_dir
    runner.get_solver = lambda name: fake
    runner.solver_dir = lambda name: tmp_path
    try:
        r = runner.run_solver("fake", _gr("path4.gr"), timeout=5, debug=True)
        assert r["status"] == "error: exit 3" and r["treewidth"] is None
        assert r["_debug"]["returncode"] == 3
        fake["run_command"] = "echo 's td 1 1 1'; echo 'b 1 1'; kill -ABRT $$"
        r = runner.run_solver("fake", _gr("path4.gr"), timeout=5)
        assert r["status"] == "error: signal 6"
        fake["run_command"] = "echo 's td 1 2 4'; echo 'b 1 1 2'"
        r = runner.run_solver("fake", _gr("path4.gr"), timeout=5)
        assert r["status"] == "ok" and r["treewidth"] == 1
    finally:
        runner.get_solver, runner.solver_dir = orig_get, orig_dir


def test_run_solver_records_mode_that_actually_ran(tmp_path):
    fake = {
        "name": "fake", "type": "exact", "language": "c",
        "run_command": "echo 'c width 1'",
        "run_mode": "stdin_stdout", "input_format": "pace_gr",
        "output_format": "pace_td",
    }
    orig_get, orig_dir = runner.get_solver, runner.solver_dir
    runner.get_solver = lambda name: fake
    runner.solver_dir = lambda name: tmp_path
    try:
        # No heuristic command: --heuristic silently ran exact before; the
        # row must say which one ran.
        r = runner.run_solver("fake", _gr("path4.gr"), timeout=5, use_heuristic=True)
        assert r["mode"] == "exact" and r["treewidth"] == 1
        fake["run_command_heuristic"] = "echo 'c width 2'"
        r = runner.run_solver("fake", _gr("path4.gr"), timeout=5, use_heuristic=True)
        assert r["mode"] == "heuristic" and r["treewidth"] == 2
        r = runner.run_solver("fake", _gr("path4.gr"), timeout=5)
        assert r["mode"] == "exact" and r["treewidth"] == 1
        fake["type"] = "heuristic"
        r = runner.run_solver("fake", _gr("path4.gr"), timeout=5)
        assert r["mode"] == "heuristic"
    finally:
        runner.get_solver, runner.solver_dir = orig_get, orig_dir


def test_run_solver_rejects_output_truncated_by_sigkill(tmp_path):
    """Signal-protocol mode: output cut off by SIGKILL is a timeout, not ok."""
    fake = {
        "name": "fake", "type": "heuristic", "language": "c",
        "run_command": "trap '' TERM; echo 's td 1 2 4'; sleep 30",
        "run_mode": "stdin_stdout_signal", "input_format": "pace_gr",
        "output_format": "pace_td",
    }
    orig_get, orig_dir, orig_grace = (
        runner.get_solver, runner.solver_dir, runner.OUTPUT_GRACE_SEC
    )
    runner.get_solver = lambda name: fake
    runner.solver_dir = lambda name: tmp_path
    runner.OUTPUT_GRACE_SEC = 0.5
    try:
        r = runner.run_solver("fake", _gr("path4.gr"), timeout=1)
        assert r["status"] == "timeout" and r["treewidth"] is None
        # Same solver, but it honours SIGTERM: its flushed output counts.
        fake["run_command"] = "trap 'echo s td 1 2 4; echo b 1 1 2; exit 0' TERM; sleep 30 & wait"
        r = runner.run_solver("fake", _gr("path4.gr"), timeout=1)
        assert r["status"] == "ok" and r["treewidth"] == 1
    finally:
        runner.get_solver, runner.solver_dir = orig_get, orig_dir
        runner.OUTPUT_GRACE_SEC = orig_grace


def test_abort_request_prevents_launching_next_solver(tmp_path):
    """The worker handler sets a flag when idle; the next launch must abort."""
    assert runner._current_proc is None
    saved = (runner._abort_requested, runner._raise_when_idle)
    try:
        runner._raise_when_idle = False  # worker mode: do not raise while idle
        runner._request_abort(None, None)  # returns, only flags
        assert runner._abort_requested
        try:
            runner._run_with_timeout("echo should-not-run", str(tmp_path), None, 5)
        except KeyboardInterrupt:
            pass
        else:
            raise AssertionError("expected KeyboardInterrupt before launch")
        runner._raise_when_idle = True  # main-process mode raises at once
        try:
            runner._request_abort(None, None)
        except KeyboardInterrupt:
            pass
        else:
            raise AssertionError("main-process handler must raise when idle")
    finally:
        runner._abort_requested, runner._raise_when_idle = saved


def test_validate_accepts_correct_path_decomposition():
    td = "s td 3 2 4\nb 1 1 2\nb 2 2 3\nb 3 3 4\n1 2\n2 3\n"
    is_valid, treewidth, errors = validate(_gr("path4.gr"), td)
    assert is_valid, errors
    assert treewidth == 1


def test_validate_rejects_uncovered_edge():
    # Bags cover the vertices but never put 3 and 4 together (edge 3-4 missing).
    td = "s td 3 1 4\nb 1 1 2\nb 2 2 3\nb 3 4\n1 2\n2 3\n"
    is_valid, _tw, errors = validate(_gr("path4.gr"), td)
    assert not is_valid
    assert any("not covered" in e for e in errors)


def test_validate_rejects_non_tree():
    # Bags wired into a cycle: not a valid tree decomposition.
    td = "s td 4 2 4\nb 1 1 2\nb 2 2 3\nb 3 2 3\nb 4 3 4\n1 2\n2 3\n3 1\n3 4\n"
    is_valid, _tw, errors = validate(_gr("path4.gr"), td)
    assert not is_valid
    # 4 tree edges among 4 bags: too many for a tree (the old assertion
    # "tree" in e also matched the connectivity message).
    assert any("4 tree edges, expected 3" in e for e in errors), errors
    # A forest: too few edges, and the bags are disconnected.
    td = "s td 3 2 4\nb 1 1 2\nb 2 2 3\nb 3 3 4\n1 2\n"
    is_valid, _tw, errors = validate(_gr("path4.gr"), td)
    assert not is_valid
    assert any("not connected" in e for e in errors), errors
    assert any("1 tree edges, expected 2" in e for e in errors), errors


def test_validate_rejects_disconnected_vertex_subtree():
    # Vertex 2 is in bags 1 and 3, which are not adjacent: condition 3 fails.
    td = "s td 3 2 4\nb 1 1 2\nb 2 3\nb 3 2 3 4\n1 2\n2 3\n"
    is_valid, _tw, errors = validate(_gr("path4.gr"), td)
    assert not is_valid
    assert any("vertex 2 are not connected" in e for e in errors), errors


def test_validate_rejects_header_mismatch_and_out_of_range_vertex():
    td = "s td 9 2 4\nb 1 1 2\nb 2 2 3\nb 3 3 4\n1 2\n2 3\n"
    is_valid, _tw, errors = validate(_gr("path4.gr"), td)
    assert not is_valid
    assert any("declares 9 bags but 3" in e for e in errors), errors
    td = "s td 3 3 4\nb 1 1 2\nb 2 2 3\nb 3 3 4 7\n1 2\n2 3\n"
    is_valid, _tw, errors = validate(_gr("path4.gr"), td)
    assert not is_valid
    assert any("out-of-range vertex 7" in e for e in errors), errors


def test_validate_names_duplicate_bag_ids_and_missing_bags():
    # Bag 2 is defined twice; the header's count of 3 then disagrees with the
    # 2 distinct bags, but the direct cause must be reported by name.
    td = "s td 3 2 4\nb 1 1 2\nb 2 2 3\nb 2 3 4\n1 2\n2 3\n"
    is_valid, _tw, errors = validate(_gr("path4.gr"), td)
    assert not is_valid
    assert any("bag 2 is defined twice" in e for e in errors), errors
    # Tree edge to a bag that does not exist.
    td = "s td 3 2 4\nb 1 1 2\nb 2 2 3\nb 3 3 4\n1 2\n2 5\n"
    is_valid, _tw, errors = validate(_gr("path4.gr"), td)
    assert not is_valid
    assert any("refers to missing bag 5" in e for e in errors), errors


def test_parse_td_reports_malformed_lines_as_value_error():
    from lib.validator import parse_td

    _assert_raises(ValueError, parse_td, "s td 3 2\nb 1 1 2\n")
    _assert_raises(ValueError, parse_td, "s td 3 2 4\nb\n")
    _assert_raises(ValueError, parse_td, "s td 3 2 4\nb 1 x\n")
    _assert_raises(ValueError, parse_td, "s td 3 2 4\nb 1 1\n1 x\n")
    # Solver chatter such as tamaki-2016's progress lines is still ignored.
    bags, edges, nb, w1, n, problems = parse_td(
        "width = 1\nc width = 1, time = 0.1\ns td 1 2 2\nb 1 1 2\n"
    )
    assert bags == {1: {1, 2}} and edges == [] and (nb, w1, n) == (1, 2, 2)
    assert problems == []


def test_missing_dependencies_names_tools_and_headers():
    import lib.solver_registry as reg

    assert reg.missing_dependencies({"language": "c", "tools": ["sh"]}) == []
    missing = reg.missing_dependencies({
        "language": "c", "tools": ["sh", "no-such-tool-xyz"],
        "headers": ["stdio.h", "no/such/header.hpp"],
    })
    assert missing == ["no-such-tool-xyz", "<no/such/header.hpp>"]
    assert reg.missing_dependencies({"language": "cobol"}) == []
    assert reg.check_dependency("c")
    # Every configured solver names only tools the registry can look up.
    for s in reg.load_solvers():
        assert isinstance(s.get("tools", []), list)


def test_build_step_timeout_kills_the_whole_process_tree(tmp_path):
    """A timed-out step must take its children with it, and the log must
    hold everything the step printed."""
    import lib.solver_registry as reg

    orig = reg.SOLVERS_DIR
    reg.SOLVERS_DIR = tmp_path
    tag = f"27.1828{os.getpid() % 1000}"
    try:
        (tmp_path / "fake").mkdir()
        solver = {"name": "fake", "build_timeout": 1,
                  "build_steps": ["echo step-one-ran", f"echo slow; sleep {tag}"]}
        assert not reg.build_solver(solver)
        assert _sleepers_alive(tag) == []
        assert not (tmp_path / "fake" / reg.BUILD_MARKER).exists()
        log = (tmp_path / "fake" / reg.BUILD_LOG).read_text()
        assert "$ echo step-one-ran\nstep-one-ran\n" in log and "slow\n" in log
        solver = {"name": "fake", "build_steps": ["echo fine", "echo bad >&2; exit 2"]}
        assert not reg.build_solver(solver)
        assert "bad" in (tmp_path / "fake" / reg.BUILD_LOG).read_text()
        solver = {"name": "fake", "build_steps": ["echo fine"]}
        assert reg.build_solver(solver)
        assert (tmp_path / "fake" / reg.BUILD_MARKER).exists()
    finally:
        reg.SOLVERS_DIR = orig


def test_decompress_is_atomic_and_streams(tmp_path):
    import bz2
    import lzma

    from lib.benchmark_registry import _decompress_files

    body = b"p tw 2 1\n1 2\n"
    (tmp_path / "a.gr.xz").write_bytes(lzma.compress(body))
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b.gr.bz2").write_bytes(bz2.compress(body))
    # Corrupt archive: must not leave a (partial or empty) b.gr behind.
    (tmp_path / "bad.gr.xz").write_bytes(b"\xfd7zXZ\x00garbage")
    assert _decompress_files(tmp_path) == 2
    assert (tmp_path / "a.gr").read_bytes() == body
    assert (tmp_path / "sub" / "b.gr").read_bytes() == body
    assert not (tmp_path / "bad.gr").exists()
    assert not list(tmp_path.rglob("*.tw_partial"))
    # Second pass: existing .gr files are skipped, the bad one retried.
    assert _decompress_files(tmp_path) == 0


def _git(path, *args):
    import subprocess

    subprocess.run(
        ["git", "-C", str(path), *args], check=True, capture_output=True,
        env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@x",
             "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@x"},
    )


def _make_repo(path):
    path.mkdir()
    _git(path, "init", "-q")
    (path / "a.txt").write_text("a\n")
    _git(path, "add", "a.txt")
    _git(path, "commit", "-q", "-m", "init")


def test_clone_pinned_checks_out_exactly_the_requested_commit(tmp_path):
    import subprocess

    from lib.clone_check import clone_pinned, head_commit

    src = tmp_path / "src"
    _make_repo(src)
    old = head_commit(src)
    (src / "a.txt").write_text("newer\n")
    _git(src, "commit", "-q", "-am", "second")
    new = head_commit(src)
    assert old != new
    repo = f"file://{src}"
    dst = tmp_path / "dst"
    clone_pinned(repo, old, dst)
    assert head_commit(dst) == old and (dst / "a.txt").read_text() == "a\n"
    dst2 = tmp_path / "dst2"
    clone_pinned(repo, None, dst2)  # unpinned: upstream HEAD
    assert head_commit(dst2) == new
    bad = tmp_path / "bad"
    _assert_raises(subprocess.CalledProcessError, clone_pinned, repo, "0" * 40, bad)
    assert not bad.exists()  # nothing half-made is left behind


def test_every_configured_repo_is_pinned_to_a_full_sha():
    import re

    from lib.benchmark_registry import load_benchmarks
    from lib.solver_registry import load_solvers

    for entry in load_solvers() + load_benchmarks():
        assert re.fullmatch(r"[0-9a-f]{40}", entry.get("commit", "")), entry["name"]


def test_every_configured_solver_is_well_formed():
    """Each solvers.json entry has the keys the registry and runner read, a
    language the dependency check knows, and command templates that use only
    the placeholders run_solver substitutes (a typo there would surface as a
    KeyError on the first benchmark run rather than at configuration time)."""
    import string

    import lib.solver_registry as reg

    placeholders = {
        "input", "input_dir", "instance_name", "output_td", "output_stat",
        "output_dir", "timeout", "timeout_soft",
    }
    seen = set()
    for s in reg.load_solvers():
        assert s["name"] not in seen, s["name"]
        seen.add(s["name"])
        for key in ("type", "language", "repo", "commit", "build_steps",
                    "run_command", "run_mode", "description"):
            assert key in s, (s["name"], key)
        assert s["type"] in ("exact", "heuristic", "both"), s["name"]
        assert s["language"] in reg.LANGUAGE_TOOLS, (s["name"], s["language"])
        assert s["run_mode"] in ("stdin_stdout", "stdin_stdout_signal", "file"), s["name"]
        assert (s["type"] == "both") == ("run_command_heuristic" in s), s["name"]
        for cmd in (s["run_command"], s.get("run_command_heuristic", "")):
            used = {f for _, f, _, _ in string.Formatter().parse(cmd) if f}
            assert used <= placeholders, (s["name"], used - placeholders)
            # Every command must name the instance somewhere.
            assert used & {"input", "input_dir", "instance_name"} or not cmd, s["name"]


def test_complete_clone_without_marker_is_adopted_not_deleted(tmp_path):
    repo = tmp_path / "repo"
    _make_repo(repo)
    (repo / "built.bin").write_text("binary\n")  # untracked build product
    (repo / "a.txt").write_text("patched\n")  # local modification
    assert is_complete_clone(repo)
    assert adopt_or_reject_existing(repo, ".marker", "repo") == "adopted"
    assert (repo / ".marker").exists()
    assert (repo / "built.bin").exists()


def test_interrupted_checkout_is_incomplete(tmp_path):
    repo = tmp_path / "repo"
    _make_repo(repo)
    (repo / "a.txt").unlink()  # tracked file missing: checkout never finished
    assert not is_complete_clone(repo)
    assert adopt_or_reject_existing(repo, ".marker", "repo") == "incomplete"
    assert not (repo / ".marker").exists()


def test_interrupted_fetch_is_incomplete(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")  # .git exists but HEAD resolves to nothing
    assert not is_complete_clone(repo)
    assert adopt_or_reject_existing(repo, ".marker", "repo") == "incomplete"


def test_plain_directory_is_foreign_and_kept(tmp_path):
    d = tmp_path / "manual"
    d.mkdir()
    (d / "x.gr").write_text("p tw 1 0\n")
    assert adopt_or_reject_existing(d, ".marker", "manual") == "foreign"
    assert (d / "x.gr").exists()
    assert not (d / ".marker").exists()


def _run_all():
    import tempfile
    from pathlib import Path

    passed = 0
    for name, fn in sorted(globals().items()):
        if not name.startswith("test_") or not callable(fn):
            continue
        argcount = fn.__code__.co_argcount
        with tempfile.TemporaryDirectory() as td:
            fn(Path(td)) if argcount else fn()
        print(f"  PASS {name}")
        passed += 1
    print(f"\n{passed} test(s) passed")


if __name__ == "__main__":
    _run_all()
