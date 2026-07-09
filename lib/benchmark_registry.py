"""Benchmark registry: download and manage benchmark instance sets."""

import bz2
import json
import lzma
import shutil
import subprocess
from pathlib import Path
from glob import glob as globfn


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
    return (benchmark_dir(name) / DOWNLOAD_MARKER).exists()


def _decompress_files(dest):
    """Decompress all .gr.xz and .gr.bz2 files to .gr."""
    count = 0
    for xz_path in dest.rglob("*.gr.xz"):
        gr_path = xz_path.with_suffix("")
        if gr_path.exists():
            continue
        try:
            with lzma.open(xz_path, "rb") as fin:
                with open(gr_path, "wb") as fout:
                    fout.write(fin.read())
            count += 1
        except Exception as e:
            print(f"    Warning: failed to decompress {xz_path.name}: {e}")
    for bz2_path in dest.rglob("*.gr.bz2"):
        gr_path = bz2_path.with_suffix("")
        if gr_path.exists():
            continue
        try:
            with bz2.open(bz2_path, "rb") as fin:
                with open(gr_path, "wb") as fout:
                    fout.write(fin.read())
            count += 1
        except Exception as e:
            print(f"    Warning: failed to decompress {bz2_path.name}: {e}")
    if count:
        print(f"  Decompressed {count} compressed files")
    return count


def download_benchmark(bench):
    name = bench["name"]
    dest = benchmark_dir(name)
    if dest.exists():
        if (dest / DOWNLOAD_MARKER).exists():
            print(f"  [{name}] Already downloaded, skipping clone")
            _decompress_files(dest)
            return True
        # Directory exists without the completion marker: a previous clone was
        # interrupted. Remove the partial tree and clone again from scratch.
        print(f"  [{name}] Removing incomplete download and re-cloning")
        shutil.rmtree(dest, ignore_errors=True)
    print(f"  [{name}] Cloning {bench['repo']} ...")
    try:
        subprocess.run(
            ["git", "clone", "--depth", "1", bench["repo"], str(dest)],
            check=True,
            capture_output=True,
            text=True,
        )
        (dest / DOWNLOAD_MARKER).write_text("ok\n")
        _decompress_files(dest)
        return True
    except subprocess.CalledProcessError as e:
        print(f"  [{name}] Clone failed: {e.stderr.strip()}")
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
