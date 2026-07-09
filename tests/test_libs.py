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
    parse_td_output,
    read_pace_gr,
)
from lib.validator import validate  # noqa: E402

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
