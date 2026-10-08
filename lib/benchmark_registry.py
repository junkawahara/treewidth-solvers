"""Benchmark registry: download and manage benchmark instance sets."""

import bz2
import json
import lzma
import shutil
import subprocess
from pathlib import Path
from glob import glob as globfn

from lib.clone_check import (
    adopt_or_reject_existing,
    clone_pinned,
    is_complete_clone,
    warn_if_not_pinned,
)


BASE_DIR = Path(__file__).resolve().parent.parent
BENCHMARKS_DIR = BASE_DIR / "benchmarks"
CONFIG_FILE = BASE_DIR / "config" / "benchmarks.json"
# Marker written once a benchmark clone has fully completed, so an interrupted
# clone is detected and retried instead of being trusted as a full download.
DOWNLOAD_MARKER = ".tw_download_complete"


def load_benchmarks():
    with open(CONFIG_FILE) as f:
        return json.load(f)


def get_benchmark(name):
    for b in load_benchmarks():
        if b["name"] == name:
            return b
    raise ValueError(f"Unknown benchmark: {name}")


def benchmark_dir(name):
    return BENCHMARKS_DIR / name


def is_installed(name):
    # Installed only if the clone completed; a partial download is not usable.
    # Clones made before the marker existed have no marker, so fall back to
    # asking git whether the checkout is complete.
    dest = benchmark_dir(name)
    return (dest / DOWNLOAD_MARKER).exists() or is_complete_clone(dest)


_OPENERS = {".xz": lzma.open, ".bz2": bz2.open}


def _decompress_one(src, gr_path):
    """Decompress src to gr_path atomically, streaming.

    Writes to a temporary file beside the target and renames it into place
    only when the whole stream has been read, so an interrupted or failed
    decompression (Ctrl-C, disk full, corrupt archive) never leaves a
    truncated .gr that later runs would take for a complete instance and skip
    forever. Streams in chunks instead of reading the whole archive into
    memory: the road graphs decompress to over 500 MB.
    """
    tmp = gr_path.with_name(gr_path.name + ".tw_partial")
    opener = _OPENERS[src.suffix]
    try:
        with opener(src, "rb") as fin, open(tmp, "wb") as fout:
            shutil.copyfileobj(fin, fout, 1 << 20)
        tmp.replace(gr_path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def _decompress_files(dest):
    """Decompress all .gr.xz and .gr.bz2 files under dest to .gr."""
    count = 0
    for suffix in _OPENERS:
        for src in sorted(dest.rglob("*.gr" + suffix)):
            gr_path = src.with_suffix("")
            if gr_path.exists():
                continue
            try:
                _decompress_one(src, gr_path)
                count += 1
            except Exception as e:
                print(f"    Warning: failed to decompress {src.name}: {e}")
    if count:
        print(f"  Decompressed {count} compressed files")
    return count


def download_benchmark(bench):
    name = bench["name"]
    dest = benchmark_dir(name)
    commit = bench.get("commit")
    if dest.exists():
        if (dest / DOWNLOAD_MARKER).exists():
            print(f"  [{name}] Already downloaded, skipping clone")
            warn_if_not_pinned(dest, commit, name)
            _decompress_files(dest)
            return True
        # No marker: either a clone made before markers existed (keep it), an
        # interrupted clone (safe to redo), or something the user put there
        # by hand (never delete it).
        state = adopt_or_reject_existing(dest, DOWNLOAD_MARKER, name)
        if state == "adopted":
            warn_if_not_pinned(dest, commit, name)
            _decompress_files(dest)
            return True
        if state == "foreign":
            print(
                f"  [{name}] {dest} exists but is not a git clone; "
                f"refusing to delete it. Move it away to re-download."
            )
            return False
        print(f"  [{name}] Removing incomplete download and re-cloning")
        shutil.rmtree(dest, ignore_errors=True)
    print(f"  [{name}] Cloning {bench['repo']} at {commit or 'HEAD'} ...")
    try:
        clone_pinned(bench["repo"], commit, dest)
        (dest / DOWNLOAD_MARKER).write_text("ok\n")
        _decompress_files(dest)
        return True
    except subprocess.CalledProcessError as e:
        print(f"  [{name}] Clone failed: {(e.stderr or '').strip()}")
        return False


def setup_all():
    benchmarks = load_benchmarks()
    results = {}
    for bench in benchmarks:
        name = bench["name"]
        print(f"\n--- Downloading benchmark: {name} ---")
        results[name] = download_benchmark(bench)
    return results


def list_instances(name):
    """List all .gr files in a benchmark set."""
    bench = get_benchmark(name)
    dest = benchmark_dir(name)
    if not dest.exists():
        return []
    pattern = str(dest / bench.get("glob", "**/*.gr"))
    files = sorted(globfn(pattern, recursive=True))
    return files


def list_installed():
    return [b["name"] for b in load_benchmarks() if is_installed(b["name"])]


def count_instances(name):
    return len(list_instances(name))
