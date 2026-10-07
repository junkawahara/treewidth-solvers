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


def test_read_pace_gr_counts():
    assert get_graph_info(_gr("k4.gr")) == {"vertices": 4, "edges": 6}
    assert get_graph_info(_gr("cycle5.gr")) == {"vertices": 5, "edges": 5}
    assert get_graph_info(_gr("path4.gr")) == {"vertices": 4, "edges": 3}


def test_read_pace_gr_rejects_edge_count_mismatch(tmp_path):
    bad = tmp_path / "bad.gr"
    bad.write_text("p tw 4 6\n1 2\n2 3\n")  # declares 6 edges, lists 2
    try:
        read_pace_gr(str(bad))
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError on edge-count mismatch")


def test_quickbb_cnf_conversion(tmp_path):
    out = tmp_path / "k4.cnf"
    pace_gr_to_quickbb_cnf(_gr("k4.gr"), str(out))
    lines = out.read_text().strip().splitlines()
    assert lines[0] == "p cnf 4 6"
    assert lines[1].endswith(" 0")
    assert len(lines) == 7  # header + 6 edges


def test_parse_td_output_formats():
    assert parse_td_output("s td 3 2 4\nb 1 1 2\n")["treewidth"] == 1
    assert parse_td_output("c width 3")["treewidth"] == 3
    assert parse_td_output("Treewidth= 5")["treewidth"] == 5
    assert parse_td_output("garbage") is None


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
    return {"solver": "s", "benchmark_set": "b", "instance": instance,
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
    assert lines[1].startswith("s,b,a,4,3,1,0.5,ok,")
    assert lines[2].startswith("s,b,b,4,3,,0.5,timeout,")
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
    assert any("tree" in e for e in errors)


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
