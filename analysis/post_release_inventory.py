#!/usr/bin/env python3
"""Reproducible inventory of post-release Python repository-issue tasks.

Question
--------
Are there enough Python repository-issue tasks created on or after
2026-04-02T00:00:00Z (Gemma 4's public release), with a runnable Docker/test
environment and an open license, to build a ~300-task fresh evaluation set that
is repo-disjoint from the training pool (the Python rows of nebius/SWE-rebench-V2)?

What the script does
--------------------
1. Resolves each Hugging Face dataset at a pinned revision (or at ``main`` with
   ``--latest``) and records the revision sha, license and last-modified time.
2. Reads only the needed columns of only the needed parquet files. Column chunks
   are fetched with HTTP range requests planned from the parquet footer; if a
   server does not support range requests the whole file is downloaded instead.
   The projected columns are cached as small local parquet files.
3. Applies the criteria in order: created_at >= cutoff, Python, Docker image
   reference present, image tag published on Docker Hub, repository license
   confirmed open (GitHub SPDX id, plus documented manual reviews where GitHub
   reports NOASSERTION), repository not in the V2 Python pool (exact owner/name,
   GitHub canonical name, and same-name repos under another owner resolved on
   GitHub to catch transfers). Counted sources: SWE-rebench-leaderboard
   (primary) and SWE-bench-Live (top-up). SWE-bench-Live/Windows and
   SWE-rebench-V2-PRs are read for the record but not counted.
4. Measures repo overlap with the V2 Python training pool, both ways: drop the
   overlapping repos from the test candidates, or drop them from training.
5. Prints a summary and writes it as JSON (default:
   ``analysis/post_release_inventory.json``).

A row count is not a count of valid tasks: every candidate must still be built
and gold-validated (gold patch passes twice, empty patch fails, flaky tests
dropped) before it can be used.

Usage
-----
    python -I analysis/post_release_inventory.py
    python -I analysis/post_release_inventory.py --cache-dir /some/dir --out out.json
    python -I analysis/post_release_inventory.py --latest          # resolve 'main' instead of the pinned shas
    python -I analysis/post_release_inventory.py --skip-github --skip-dockerhub

Cache directory precedence: ``--cache-dir`` > ``$INVENTORY_CACHE_DIR`` >
``analysis/.cache_inventory/`` (next to this script; gitignored). Delete
``<cache>/_api`` to refresh cached GitHub / Docker Hub answers.

Safety
------
Downloaded files are untrusted data. They are only parsed as parquet or JSON,
stored only in the cache directory, and never executed. Run with ``python -I``.
No local absolute paths, usernames or tokens are written to the outputs; the
script checks this before writing. No authentication token is used.

Requirements: Python 3.9+, pandas, pyarrow (standard library otherwise).
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import datetime as dt
import fnmatch
import hashlib
import io
import json
import math
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

# ---------------------------------------------------------------------------
# Parameters
# ---------------------------------------------------------------------------

CUTOFF_UTC = "2026-04-02T00:00:00Z"  # Gemma 4 public release
TARGET_TASKS = 300
MIN_TASKS = 200
# Earlier gold-validation pass on a different panel: 101 of 115 tasks kept.
GOLD_VALIDATION_PRIOR = {"kept": 101, "total": 115}

# Revisions are pinned to the commits this report was produced from.
# Use --latest to resolve each dataset's 'main' branch at run time instead.
SOURCES = [
    {
        "key": "swe_rebench_leaderboard",
        "dataset_id": "nebius/SWE-rebench-leaderboard",
        "revision": "34d5a58864acf91613740a09ec5d205228dcfa39",
        "role": "primary",
        "counted": True,
        "splits": "*",  # every split in the dataset card (monthly YYYY_MM splits + 'test')
        "columns": ["repo", "instance_id", "created_at", "docker_image", "image_name", "install_config"],
        "python_rule": "install_config.python (interpreter version) is set",
        "env_rule": "docker_image is a non-empty image reference (prebuilt image per task)",
    },
    {
        "key": "swe_bench_live",
        "dataset_id": "SWE-bench-Live/SWE-bench-Live",
        "revision": "b51a86422e10cfd403beb4773e5a2947953e36ec",
        "role": "top-up",
        "counted": True,
        "splits": ["full"],  # README: 'full' holds all released tasks; lite/verified are frozen subsets
        "columns": ["repo", "instance_id", "created_at", "log_parser"],
        "python_rule": "dataset is Python-only (README)",
        "env_rule": "per-instance Docker image documented in README; no image column in the parquet",
    },
    {
        "key": "swe_bench_live_windows",
        "dataset_id": "SWE-bench-Live/Windows",
        "revision": "b9fa25f2732dbc2c93b9738b610d053d8b7bd7a9",
        "role": "checked only (Windows-container tasks; not counted toward the Linux Docker test set)",
        "counted": False,
        "splits": ["test"],
        "columns": ["repo", "instance_id", "created_at", "language", "docker_image"],
        "python_rule": "language == 'Python'",
        "env_rule": "docker_image is a non-empty image reference (Windows container)",
    },
    {
        "key": "swe_rebench_v2_prs",
        "dataset_id": "nebius/SWE-rebench-V2-PRs",
        "revision": "fbf0ecf50f268d5344149e2f0097db6bede83737",
        "role": "checked only (date check; PR tasks without prebuilt images or a language column)",
        "counted": False,
        "date_only": True,
        "splits": ["train"],
        "columns": ["repo", "instance_id", "created_at"],
        "python_rule": "not determinable (no language column)",
        "env_rule": "no prebuilt image column; environments would have to be built",
    },
]

# Datasets considered but not read row by row: recorded with their current metadata.
CONSIDERED_NOT_READ = [
    {"dataset_id": "nebius/SWE-rebench",
     "reason": "original SWE-rebench corpus; last modified before the cutoff, so it cannot hold post-cutoff tasks"},
    {"dataset_id": "SWE-bench-Live/MultiLang",
     "reason": "non-Python languages only (C, C++, C#, Go, Java, JS, Rust, TS splits)"},
]
# Not on Hugging Face; noted in the report, not machine-counted.
OFF_HUB_NOTES = [
    {"name": "SWE-rebench July 2026 snapshot on Harbor Hub (ibragim-badertdinov/swe-rebench-07-2026)",
     "pointer": "named in the nebius/SWE-rebench-leaderboard dataset card",
     "described_as": "111 tasks: Go 21, Java 21, Python 20, Rust 25, TypeScript 24; source declared CC BY 4.0",
     "status": "not counted: per-task created_at, repos and licenses not verified by this script"},
]

TRAIN_POOL = {
    "key": "swe_rebench_v2",
    "dataset_id": "nebius/SWE-rebench-V2",
    "revision": "10483de0f50fe5da545942705a76c6150171af7f",
    "split": "train",
    "columns": ["repo", "instance_id", "created_at", "language", "image_name"],
    "language_column": "language",
    "language_value": "python",  # compared case-insensitively
}

# Licenses counted as "open" (OSI-approved SPDX ids, plus public-domain dedications).
OPEN_LICENSES = {
    "0BSD", "AFL-3.0", "AGPL-3.0", "AGPL-3.0-only", "AGPL-3.0-or-later", "Apache-2.0",
    "Artistic-2.0", "BSD-2-Clause", "BSD-3-Clause", "BSD-3-Clause-Clear", "BSL-1.0",
    "CC0-1.0", "ECL-2.0", "EPL-1.0", "EPL-2.0", "EUPL-1.1", "EUPL-1.2", "GPL-2.0",
    "GPL-2.0-only", "GPL-2.0-or-later", "GPL-3.0", "GPL-3.0-only", "GPL-3.0-or-later",
    "ISC", "LGPL-2.1", "LGPL-2.1-only", "LGPL-2.1-or-later", "LGPL-3.0", "LGPL-3.0-only",
    "LGPL-3.0-or-later", "MIT", "MIT-0", "MPL-2.0", "MulanPSL-2.0", "NCSA", "OSL-3.0",
    "PostgreSQL", "PSF-2.0", "Python-2.0", "UPL-1.0", "Unlicense", "Zlib",
}
# Manual reviews, applied only where GitHub could not classify the license (spdx_id
# NOASSERTION or missing). Counts are reported both with and without these.
MANUAL_LICENSE_REVIEW = {
    "raullenchai/rapid-mlx": {
        "spdx_id": "Apache-2.0",
        "note": ("LICENSE is the Apache-2.0 text preceded by a short project preamble and a NOTICE "
                 "pointer; GitHub reports NOASSERTION. Read by hand on 2026-10-27."),
    },
}
PERMISSIVE_LICENSES = {
    "0BSD", "AFL-3.0", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "BSD-3-Clause-Clear",
    "BSL-1.0", "CC0-1.0", "ECL-2.0", "ISC", "MIT", "MIT-0", "NCSA", "PostgreSQL",
    "PSF-2.0", "Python-2.0", "UPL-1.0", "Unlicense", "Zlib",
}

HF = "https://huggingface.co"
USER_AGENT = "post-release-inventory/1.0 (research; stdlib urllib)"
SCRIPT_RELPATH = "analysis/post_release_inventory.py"
DEFAULT_OUT_NAME = "post_release_inventory.json"
RANGE_GAP_BYTES = 64 * 1024  # merge column-chunk ranges closer than this
FETCH_WORKERS = 8

# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------


class RangeUnsupported(RuntimeError):
    pass


def _redact(url: str) -> str:
    """Drop query strings (signed CDN URLs) from anything that may be printed."""
    return url.split("?", 1)[0]


def http_get(url: str, headers: dict | None = None, timeout: int = 120, retries: int = 5):
    """GET with retries on transient errors. Returns (status, lower-cased headers, body, final_url)."""
    hdrs = {"User-Agent": USER_AGENT}
    hdrs.update(headers or {})
    last_err = None
    for attempt in range(retries):
        req = urllib.request.Request(url, headers=hdrs)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.status, {k.lower(): v for k, v in r.headers.items()}, r.read(), r.geturl()
        except urllib.error.HTTPError as e:
            body = e.read() if e.fp else b""
            h = {k.lower(): v for k, v in (e.headers or {}).items()}
            if e.code in (429, 500, 502, 503, 504):
                last_err = f"HTTP {e.code}"
            else:
                return e.code, h, body, url
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
            last_err = type(e).__name__
        time.sleep(min(30, 2 ** attempt))
    raise RuntimeError(f"GET failed after {retries} attempts: {_redact(url)} ({last_err})")


def get_json(url: str):
    status, _, body, _ = http_get(url, headers={"Accept": "application/json"})
    if status != 200:
        raise RuntimeError(f"GET {_redact(url)} -> HTTP {status}")
    return json.loads(body.decode("utf-8"))


class SparseRemoteFile(io.RawIOBase):
    """Read-only, seekable view of a remote file backed by HTTP range requests.

    Byte ranges are prefetched in parallel (see ``prefetch``); any read that is not
    covered falls back to an on-demand range request. Only bytes are handled here;
    nothing downloaded is ever executed.
    """

    def __init__(self, url: str):
        super().__init__()
        self._url = url
        self._final_url = url
        self._segments: list[tuple[int, bytes]] = []
        self._pos = 0
        self.n_requests = 0
        self.n_bytes = 0
        self.n_misses = 0
        status, headers, body, final = http_get(url, headers={"Range": "bytes=0-0"})
        self.n_requests += 1
        if status != 206 or "content-range" not in headers:
            raise RangeUnsupported(f"no range support (HTTP {status})")
        self.size = int(headers["content-range"].rsplit("/", 1)[1])
        self._final_url = final

    # -- io.RawIOBase interface ------------------------------------------------
    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self._pos

    def seek(self, offset, whence=io.SEEK_SET):
        if whence == io.SEEK_SET:
            self._pos = offset
        elif whence == io.SEEK_CUR:
            self._pos += offset
        else:
            self._pos = self.size + offset
        return self._pos

    def read(self, n=-1):
        if n is None or n < 0:
            n = self.size - self._pos
        n = max(0, min(n, self.size - self._pos))
        if n == 0:
            return b""
        data = self._lookup(self._pos, n)
        if data is None:
            self.n_misses += 1
            data = self._fetch(self._pos, self._pos + n)
            self._segments.append((self._pos, data))
        self._pos += len(data)
        return data

    def readinto(self, b):
        data = self.read(len(b))
        b[: len(data)] = data
        return len(data)

    # -- range machinery ---------------------------------------------------------
    def _lookup(self, start: int, n: int):
        for s, buf in self._segments:
            if s <= start and start + n <= s + len(buf):
                return buf[start - s: start - s + n]
        return None

    def _fetch(self, start: int, end: int) -> bytes:
        """Fetch bytes [start, end). Re-resolves the redirect if a signed URL expired."""
        for url in (self._final_url, self._url):
            status, _, body, final = http_get(url, headers={"Range": f"bytes={start}-{end - 1}"})
            self.n_requests += 1
            if status == 206 and len(body) == end - start:
                self.n_bytes += len(body)
                if url == self._url:
                    self._final_url = final
                return body
        raise RuntimeError(f"range fetch failed for bytes {start}-{end - 1} of {_redact(self._url)}")

    def prefetch(self, ranges, gap: int = RANGE_GAP_BYTES):
        """Merge nearby ranges and fetch them in parallel into the segment cache."""
        merged: list[list[int]] = []
        for s, e in sorted((max(0, s), min(self.size, e)) for s, e in ranges if e > s):
            if merged and s <= merged[-1][1] + gap:
                merged[-1][1] = max(merged[-1][1], e)
            else:
                merged.append([s, e])
        with cf.ThreadPoolExecutor(max_workers=FETCH_WORKERS) as ex:
            futs = {ex.submit(self._fetch, s, e): s for s, e in merged}
            for fut in cf.as_completed(futs):
                self._segments.append((futs[fut], fut.result()))
        self._segments.sort(key=lambda x: x[0])
        return len(merged)


def _column_chunk_ranges(md: pq.FileMetaData, top_level: set[str]):
    ranges = []
    for rg in range(md.num_row_groups):
        r = md.row_group(rg)
        for i in range(r.num_columns):
            c = r.column(i)
            if c.path_in_schema.split(".")[0] not in top_level:
                continue
            start = c.data_page_offset
            dict_off = c.dictionary_page_offset
            if c.has_dictionary_page and dict_off is not None and 0 < dict_off < start:
                start = dict_off
            ranges.append((start, start + c.total_compressed_size))
    return ranges


def read_hf_parquet_columns(dataset_id: str, revision: str, path: str, columns: list[str],
                            cache_dir: Path, force_full: bool = False) -> tuple[pd.DataFrame, dict]:
    """Return the requested columns of one parquet file of a HF dataset at a fixed revision."""
    # Short names keep paths under the Windows 260-character limit even for deep cache dirs.
    key = hashlib.sha1(f"{path}|{','.join(sorted(columns))}".encode()).hexdigest()[:8]
    ds_dir = cache_dir / f"{dataset_id.split('/')[-1][:24]}-{revision[:8]}"
    cached = ds_dir / f"{Path(path).stem[:24]}.{key}.parquet"
    sidecar = cached.with_suffix(".fetch.json")  # stats of the original fetch, for the report
    stats = {"path": path, "columns": sorted(columns)}
    if cached.exists():
        if sidecar.exists():
            stats.update(json.loads(sidecar.read_text(encoding="utf-8")))
        stats["served_from_cache"] = True
        return pq.read_table(cached).to_pandas(), stats

    url = f"{HF}/datasets/{dataset_id}/resolve/{revision}/{urllib.parse.quote(path)}"
    table = None
    if not force_full:
        try:
            f = SparseRemoteFile(url)
            tail = min(f.size, 1 << 20)
            f.prefetch([(f.size - tail, f.size)], gap=0)
            footer_len = int.from_bytes(f._lookup(f.size - 8, 4), "little")
            if footer_len + 8 > tail:
                f.prefetch([(f.size - footer_len - 8, f.size)], gap=0)
            pf = pq.ParquetFile(f)
            names = set(pf.schema_arrow.names)
            missing = [c for c in columns if c not in names]
            if missing:
                raise KeyError(f"{dataset_id}:{path} lacks columns {missing}")
            ranges = _column_chunk_ranges(pf.metadata, set(columns))
            n_merged = f.prefetch(ranges)
            table = pf.read(columns=columns, use_threads=False)
            stats.update(fetch="http-range", file_bytes=f.size, bytes_downloaded=f.n_bytes,
                         requests=f.n_requests, merged_ranges=n_merged, on_demand_misses=f.n_misses)
        except RangeUnsupported:
            table = None
    if table is None:  # fallback: whole-file download kept in the cache directory
        raw = ds_dir / f"{Path(path).stem[:24]}.{hashlib.sha1(path.encode()).hexdigest()[:8]}.full.parquet"
        if not raw.exists():
            status, _, body, _ = http_get(url, timeout=600)
            if status != 200:
                raise RuntimeError(f"download failed: {_redact(url)} -> HTTP {status}")
            raw.parent.mkdir(parents=True, exist_ok=True)
            tmp = raw.with_suffix(".tmp")
            tmp.write_bytes(body)
            os.replace(tmp, raw)
        table = pq.read_table(raw, columns=columns)
        stats.update(fetch="full-download", file_bytes=raw.stat().st_size)

    cached.parent.mkdir(parents=True, exist_ok=True)
    tmp = cached.with_suffix(".tmp")
    pq.write_table(table, tmp)
    os.replace(tmp, cached)
    sidecar.write_text(json.dumps({k: v for k, v in stats.items() if k not in ("path", "columns")}),
                       encoding="utf-8")
    stats["served_from_cache"] = False
    return table.to_pandas(), stats


def hf_dataset_meta(dataset_id: str, revision: str) -> dict:
    d = get_json(f"{HF}/api/datasets/{dataset_id}/revision/{revision}")
    card = d.get("cardData") or {}
    files = [s["rfilename"] for s in d.get("siblings", [])]
    split_files: dict[str, list[str]] = {}
    for cfg in card.get("configs") or []:
        if cfg.get("config_name", "default") != "default":
            continue
        for df_spec in cfg.get("data_files") or []:
            patterns = df_spec["path"] if isinstance(df_spec["path"], list) else [df_spec["path"]]
            split_files[df_spec["split"]] = sorted(
                f for f in files for p in patterns if fnmatch.fnmatch(f, p))
    return {
        "dataset_id": d.get("id", dataset_id),
        "requested_revision": revision,
        "revision_sha": d["sha"],
        "last_modified": d.get("lastModified"),
        "license": card.get("license"),
        "gated": d.get("gated"),
        "split_files": split_files,
    }


# ---------------------------------------------------------------------------
# Cached third-party lookups (GitHub repo metadata, Docker Hub tag existence)
# ---------------------------------------------------------------------------


def _api_cache(cache_dir: Path, kind: str, key: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", key)[:150]
    return cache_dir / "_api" / kind / f"{safe}.json"


def github_repo_info(repo: str, cache_dir: Path) -> dict:
    """Canonical full_name, SPDX license id and archived flag from the public GitHub API (no token)."""
    p = _api_cache(cache_dir, "github", repo.lower())
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    status, headers, body, _ = http_get(f"https://api.github.com/repos/{repo}",
                                        headers={"Accept": "application/vnd.github+json"}, retries=3)
    fetched = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if status == 200:
        d = json.loads(body.decode("utf-8"))
        info = {"status": "ok", "full_name": d.get("full_name"),
                "spdx_id": (d.get("license") or {}).get("spdx_id"),
                "archived": bool(d.get("archived")), "fetched_at_utc": fetched}
    elif status == 404:
        info = {"status": "not_found", "full_name": None, "spdx_id": None, "archived": None,
                "fetched_at_utc": fetched}
    else:  # rate limit or other error: do not cache, report as unknown
        return {"status": f"unavailable (HTTP {status}, ratelimit-remaining="
                          f"{headers.get('x-ratelimit-remaining')})",
                "full_name": None, "spdx_id": None, "archived": None, "fetched_at_utc": fetched}
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(info), encoding="utf-8")
    return info


def dockerhub_tag_exists(image_ref: str, cache_dir: Path):
    """True/False if Docker Hub reports the tag; None if it could not be checked."""
    ref = image_ref.strip()
    if ref.startswith("docker.io/"):
        ref = ref[len("docker.io/"):]
    name, _, tag = ref.partition(":")
    tag = tag or "latest"
    if name.count("/") != 1:
        return None
    ns, repo = name.split("/")
    p = _api_cache(cache_dir, "dockerhub", f"{ns}__{repo}__{tag}")
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))["exists"]
    try:
        status, _, _, _ = http_get(
            f"https://hub.docker.com/v2/namespaces/{ns}/repositories/{repo}/tags/{tag}", retries=3)
    except RuntimeError:
        return None
    if status not in (200, 404):
        return None
    exists = status == 200
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"exists": exists}), encoding="utf-8")
    return exists


# ---------------------------------------------------------------------------
# Normalisation
# ---------------------------------------------------------------------------


def to_utc(series: pd.Series) -> pd.Series:
    """Parse created_at to tz-aware UTC. Naive timestamps are GitHub API times, i.e. UTC."""
    if pd.api.types.is_integer_dtype(series):
        return pd.to_datetime(series, unit="ms", utc=True)
    if isinstance(series.dtype, pd.DatetimeTZDtype):
        return series.dt.tz_convert("UTC")
    if pd.api.types.is_datetime64_any_dtype(series):
        return series.dt.tz_localize("UTC")
    return pd.to_datetime(series, utc=True, format="mixed")


def norm_repo(repo) -> str:
    return str(repo).strip().strip("/").lower()


def _nonempty(x) -> bool:
    return isinstance(x, str) and x.strip() != ""


def load_source(src: dict, meta: dict, cache_dir: Path, force_full: bool):
    split_files = meta["split_files"]
    splits = sorted(split_files) if src["splits"] == "*" else src["splits"]
    frames, fetch_log = [], []
    for split in splits:
        for path in split_files.get(split, []):
            df, st = read_hf_parquet_columns(meta["dataset_id"], meta["revision_sha"], path,
                                             src["columns"], cache_dir, force_full)
            df["split"] = split
            frames.append(df)
            fetch_log.append(st)
    raw = pd.concat(frames, ignore_index=True)
    raw["created_at_utc"] = to_utc(raw["created_at"])
    raw["repo_norm"] = raw["repo"].map(norm_repo)

    if src.get("date_only"):
        raw["is_python"] = False  # not determinable; such sources are reported by date only
        raw["env_ref"] = None
    elif src["key"] == "swe_rebench_leaderboard":
        raw["is_python"] = raw["install_config"].map(lambda c: isinstance(c, dict) and _nonempty(c.get("python")))
        raw["env_ref"] = raw["docker_image"].where(raw["docker_image"].map(_nonempty), None)
    elif src["key"] == "swe_bench_live":
        raw["is_python"] = True
        raw["env_ref"] = "documented-per-instance-image"
    elif src["key"] == "swe_bench_live_windows":
        raw["is_python"] = raw["language"].astype(str).str.lower().eq("python")
        raw["env_ref"] = raw["docker_image"].where(raw["docker_image"].map(_nonempty), None)
    else:
        raise ValueError(src["key"])
    raw["has_env"] = raw["env_ref"].map(_nonempty)
    return raw, splits, fetch_log


def month_counts(dates: pd.Series) -> dict:
    if len(dates) == 0:
        return {}
    return {str(k): int(v) for k, v in dates.dt.strftime("%Y-%m").value_counts().sort_index().items()}


def ts(x) -> str | None:
    if x is None or pd.isna(x):
        return None
    return pd.Timestamp(x).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Main analysis
# ---------------------------------------------------------------------------


def main(argv=None) -> int:
    here = Path(__file__).resolve().parent
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--cache-dir", default=None,
                    help="cache directory (default: $INVENTORY_CACHE_DIR or analysis/.cache_inventory)")
    ap.add_argument("--out", default=str(here / DEFAULT_OUT_NAME), help="output JSON path")
    ap.add_argument("--latest", action="store_true", help="resolve 'main' instead of the pinned revisions")
    ap.add_argument("--full-download", action="store_true", help="download whole parquet files (no range reads)")
    ap.add_argument("--skip-github", action="store_true", help="skip GitHub license / canonical-name lookups")
    ap.add_argument("--skip-dockerhub", action="store_true", help="skip Docker Hub image-tag checks")
    args = ap.parse_args(argv)

    cache_dir = Path(args.cache_dir or os.environ.get("INVENTORY_CACHE_DIR") or here / ".cache_inventory")
    cache_source = "cli" if args.cache_dir else ("env" if os.environ.get("INVENTORY_CACHE_DIR") else "default")
    cache_dir.mkdir(parents=True, exist_ok=True)
    cutoff = pd.Timestamp(CUTOFF_UTC)
    run_started = dt.datetime.now(dt.timezone.utc)

    # ---------------- training pool -------------------------------------------------
    tp_meta = hf_dataset_meta(TRAIN_POOL["dataset_id"], "main" if args.latest else TRAIN_POOL["revision"])
    tp_frames, tp_log = [], []
    for path in tp_meta["split_files"].get(TRAIN_POOL["split"], []):
        df, st = read_hf_parquet_columns(tp_meta["dataset_id"], tp_meta["revision_sha"], path,
                                         TRAIN_POOL["columns"], cache_dir, args.full_download)
        tp_frames.append(df)
        tp_log.append(st)
    v2 = pd.concat(tp_frames, ignore_index=True)
    v2["repo_norm"] = v2["repo"].map(norm_repo)
    v2["created_at_utc"] = to_utc(v2["created_at"])
    lang = v2[TRAIN_POOL["language_column"]].astype(str).str.lower()
    v2_py = v2[lang.eq(TRAIN_POOL["language_value"])]
    v2_py_repos = set(v2_py["repo_norm"])
    v2_all_repos = set(v2["repo_norm"])

    # ---------------- test-candidate sources -----------------------------------------
    source_reports, frames = {}, []
    for src in SOURCES:
        meta = hf_dataset_meta(src["dataset_id"], "main" if args.latest else src["revision"])
        raw, splits, fetch_log = load_source(src, meta, cache_dir, args.full_download)
        uniq = raw.drop_duplicates("instance_id")
        post = uniq[uniq["created_at_utc"] >= cutoff]
        rep = {
            "role": src["role"],
            "counted_toward_test_set": src["counted"],
            "dataset_id": meta["dataset_id"],
            "revision_sha": meta["revision_sha"],
            "last_modified": meta["last_modified"],
            "license": meta["license"],
            "splits_available": sorted(meta["split_files"]),
            "splits_read": splits,
            "files_read": fetch_log,
            "python_rule": src["python_rule"],
            "env_rule": src["env_rule"],
            "rows_read": int(len(raw)),
            "unique_instances": int(len(uniq)),
            "created_at_min_utc": ts(uniq["created_at_utc"].min()),
            "created_at_max_utc": ts(uniq["created_at_utc"].max()),
            "rows_per_split": {s: int(n) for s, n in raw.groupby("split").size().items()},
            "post_cutoff_rows_per_split": {
                s: int(n) for s, n in raw[raw["created_at_utc"] >= cutoff].groupby("split").size().items()},
            "funnel": {
                "unique_instances": int(len(uniq)),
                "created_on_or_after_cutoff": int(len(post)),
                "and_python": None if src.get("date_only") else int(post["is_python"].sum()),
                "and_env_reference": None if src.get("date_only") else
                int((post["is_python"] & post["has_env"]).sum()),
            },
            "post_cutoff_by_month": month_counts(post["created_at_utc"]),
        }
        if src["key"] == "swe_rebench_leaderboard" and "test" in splits:
            monthly = set(raw.loc[raw["split"] != "test", "instance_id"])
            test_ids = set(raw.loc[raw["split"] == "test", "instance_id"])
            rep["test_split_equals_union_of_monthly_splits"] = monthly == test_ids
            # Monthly split each post-cutoff task is filed under (split names != creation month).
            rep["post_cutoff_tasks_by_monthly_split"] = {
                s: int(n) for s, n in raw[(raw["split"] != "test") & (raw["created_at_utc"] >= cutoff)]
                .groupby("split").size().items()}
            py_month = uniq[uniq["is_python"]].groupby(uniq["created_at_utc"].dt.strftime("%Y-%m")).size()
            rep["python_tasks_by_creation_month_all_time"] = {str(k): int(v) for k, v in py_month.items()}
        source_reports[src["key"]] = rep
        sel = post[post["is_python"] & post["has_env"]].copy()
        sel["source"] = src["key"]
        sel["counted"] = src["counted"]
        frames.append(sel[["source", "counted", "split", "instance_id", "repo", "repo_norm",
                           "created_at_utc", "env_ref"]])

    considered = []
    for c in CONSIDERED_NOT_READ:
        m = hf_dataset_meta(c["dataset_id"], "main")
        considered.append({**c, "revision_sha": m["revision_sha"], "last_modified": m["last_modified"],
                           "license": m["license"],
                           "last_modified_before_cutoff": pd.Timestamp(m["last_modified"]) < cutoff})

    allsel = pd.concat(frames, ignore_index=True)
    checked_only = allsel[~allsel["counted"]]
    cand = allsel[allsel["counted"]].drop_duplicates("instance_id").copy()

    # ---------------- Docker Hub image-tag check -------------------------------------
    def image_status(ref):
        if args.skip_dockerhub or not _nonempty(ref) or ref == "documented-per-instance-image":
            return "not_checked"
        ex = dockerhub_tag_exists(ref, cache_dir)
        return {True: "published", False: "missing", None: "unknown"}[ex]

    cand["image_status"] = [image_status(r) for r in cand["env_ref"]]

    # ---------------- GitHub license + canonical name ------------------------------------
    repo_info = {}
    for repo in sorted(cand["repo"].unique(), key=str.lower):
        repo_info[norm_repo(repo)] = (
            {"status": "skipped", "full_name": None, "spdx_id": None, "archived": None}
            if args.skip_github else github_repo_info(repo, cache_dir))
    cand["spdx_github"] = cand["repo_norm"].map(lambda r: repo_info[r].get("spdx_id"))

    def effective_license(row):
        if row.spdx_github in (None, "NOASSERTION") and row.repo_norm in MANUAL_LICENSE_REVIEW:
            return MANUAL_LICENSE_REVIEW[row.repo_norm]["spdx_id"], "manual_review"
        return row.spdx_github, "github"

    eff = [effective_license(r) for r in cand.itertuples()]
    cand["spdx_id"] = [e[0] for e in eff]
    cand["license_source"] = [e[1] for e in eff]
    cand["license_open"] = cand["spdx_id"].map(lambda s: s in OPEN_LICENSES)
    cand["license_open_github_only"] = cand["spdx_github"].map(lambda s: s in OPEN_LICENSES)
    cand["canonical_repo"] = cand["repo_norm"].map(
        lambda r: norm_repo(repo_info[r]["full_name"]) if repo_info[r].get("full_name") else r)

    # ---------------- overlap with the V2 training pool ----------------------------------
    # Renames/transfers: a V2 repo with the same short name as a candidate (or as its GitHub
    # canonical name) but another owner is looked up on GitHub; if it resolves to the same
    # canonical repo, it is treated as the same repository.
    v2_all_short: dict[str, set[str]] = {}
    for r in v2_all_repos:
        v2_all_short.setdefault(r.split("/")[-1], set()).add(r)
    v2_alias: dict[str, set[str]] = {}
    alias_checks = []
    for r, info in sorted(repo_info.items()):
        canon = norm_repo(info["full_name"]) if info.get("full_name") else r
        names = {r, canon}
        others = set().union(*(v2_all_short.get(n.split("/")[-1], set()) for n in names)) - names
        for v in sorted(others):
            vinfo = ({"status": "skipped", "full_name": None} if args.skip_github
                     else github_repo_info(v, cache_dir))
            v_canon = norm_repo(vinfo["full_name"]) if vinfo.get("full_name") else None
            same = v_canon is not None and v_canon == canon
            alias_checks.append({"candidate_repo": r, "v2_repo": v,
                                 "v2_repo_in_python_pool": v in v2_py_repos,
                                 "v2_repo_github_canonical": vinfo.get("full_name"),
                                 "lookup_status": vinfo["status"], "same_repository": same})
            if same:
                v2_alias.setdefault(canon, set()).add(v)

    def v2_names(row, pool):
        names = {row.repo_norm, row.canonical_repo} | v2_alias.get(row.canonical_repo, set())
        return {n for n in names if n in pool}

    cand["v2_python_names"] = [v2_names(r, v2_py_repos) for r in cand.itertuples()]
    cand["in_v2_python"] = cand["v2_python_names"].map(bool)
    cand["in_v2_any_language"] = [bool(v2_names(r, v2_all_repos)) for r in cand.itertuples()]

    # Funnel over the counted sources.
    f0 = cand
    f1 = f0[f0["image_status"] != "missing"]  # keep 'unknown'/'not_checked', flagged below
    f2 = f1[f1["license_open"]] if not args.skip_github else f1
    f3 = f2[~f2["in_v2_python"]]
    f3_strict = f2[~f2["in_v2_any_language"]]
    # Same funnel without the manual license reviews (GitHub SPDX ids only).
    f2_gh = f1[f1["license_open_github_only"]] if not args.skip_github else f1
    f3_gh = f2_gh[~f2_gh["in_v2_python"]]

    overlap_repos = sorted(set(f2.loc[f2["in_v2_python"], "repo_norm"]))
    overlap_v2_names = set().union(*f2.loc[f2["in_v2_python"], "v2_python_names"]) if len(overlap_repos) else set()
    v2_rows_in_overlap = v2_py[v2_py["repo_norm"].isin(overlap_v2_names)]
    v2_tasks_per_repo = v2_py["repo_norm"].value_counts()

    # Same short name, other owner, not resolved by GitHub: left for manual review.
    name_flags = [a for a in alias_checks if not a["same_repository"] and a["lookup_status"] != "ok"]

    # ---------------- reachability ------------------------------------------------------
    keep_rate = GOLD_VALIDATION_PRIOR["kept"] / GOLD_VALIDATION_PRIOR["total"]
    final_n = int(len(f3))
    expected_valid = final_n * keep_rate
    rows_needed = {str(t): math.ceil(t / keep_rate) for t in (MIN_TASKS, TARGET_TASKS)}
    lb = source_reports["swe_rebench_leaderboard"]
    lb_cov_end = pd.Timestamp(lb["created_at_max_utc"])
    # Rough run-rate: Python leaderboard tasks per complete month over the 12 complete
    # months before the end of published coverage.
    last_complete = lb_cov_end.tz_convert(None).to_period("M") - 1
    window = [str(last_complete - i) for i in range(12)]
    by_m = lb["python_tasks_by_creation_month_all_time"]
    monthly_rate = sum(by_m.get(m, 0) for m in window) / 12.0
    disjoint_frac = (len(f3) / len(f2)) if len(f2) else 0.0
    eff_rate = monthly_rate * disjoint_frac * keep_rate

    def months_to(target):
        gap = target - expected_valid
        if gap <= 0:
            return 0
        return math.ceil(gap / eff_rate) if eff_rate > 0 else None

    repos_table = []
    for r, g in f2.groupby("repo_norm"):
        info = repo_info.get(r, {})
        repos_table.append({
            "repo": g["repo"].iloc[0], "tasks": int(len(g)), "spdx_id": g["spdx_id"].iloc[0],
            "license_source": g["license_source"].iloc[0], "spdx_id_github": info.get("spdx_id"),
            "github_canonical": info.get("full_name"), "archived": info.get("archived"),
            "in_v2_python": bool(g["in_v2_python"].any()),
            "in_v2_any_language": bool(g["in_v2_any_language"].any()),
            "v2_python_repo_names_matched": sorted(set().union(*g["v2_python_names"])),
            "v2_python_tasks_in_repo": int(sum(v2_tasks_per_repo.get(n, 0)
                                               for n in set().union(*g["v2_python_names"]))),
        })
    repos_table.sort(key=lambda x: (-x["tasks"], x["repo"].lower()))

    excluded_license = f1[~f1["license_open"]] if not args.skip_github else f1.iloc[0:0]
    all_logs = tp_log + [f for rep in source_reports.values() for f in rep["files_read"]]

    result = {
        "schema_version": 1,
        "generated_at_utc": run_started.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "script": SCRIPT_RELPATH,
        "question": ("Are there enough Python repository-issue tasks created on or after "
                     f"{CUTOFF_UTC} (Gemma 4 public release), with a runnable Docker/test environment "
                     "and an open license, to build a ~300-task fresh evaluation set that is "
                     "repo-disjoint from the V2 Python training pool?"),
        "parameters": {
            "cutoff_utc": CUTOFF_UTC, "target_tasks": TARGET_TASKS, "min_tasks": MIN_TASKS,
            "gold_validation_prior": {**GOLD_VALIDATION_PRIOR, "keep_rate": round(keep_rate, 4)},
            "revisions": "latest (main resolved at run time)" if args.latest else "pinned",
            "cache_dir": cache_source,
            "github_checks": not args.skip_github, "dockerhub_checks": not args.skip_dockerhub,
            "open_license_spdx_ids": sorted(OPEN_LICENSES),
            "manual_license_review": MANUAL_LICENSE_REVIEW,
            "created_at_note": "naive created_at timestamps are treated as UTC (GitHub API times)",
            "repo_match_note": ("repos matched case-insensitively on owner/name, and on GitHub's current "
                                "canonical owner/name for the candidate repos"),
        },
        "training_pool": {
            "dataset_id": tp_meta["dataset_id"], "revision_sha": tp_meta["revision_sha"],
            "last_modified": tp_meta["last_modified"], "license": tp_meta["license"],
            "split": TRAIN_POOL["split"], "files_read": tp_log,
            "language_field": TRAIN_POOL["language_column"],
            "rows": int(len(v2)), "languages": {k: int(v) for k, v in lang.value_counts().items()},
            "python_rows": int(len(v2_py)), "python_repos": len(v2_py_repos),
            "all_language_repos": len(v2_all_repos),
            "python_rows_with_image_name": int(v2_py["image_name"].map(_nonempty).sum()),
            "created_at_min_utc": ts(v2["created_at_utc"].min()),
            "created_at_max_utc": ts(v2["created_at_utc"].max()),
            "python_rows_on_or_after_cutoff": int((v2_py["created_at_utc"] >= cutoff).sum()),
        },
        "download_summary": {
            "parquet_files_read": len(all_logs),
            "parquet_bytes_total": int(sum(x.get("file_bytes", 0) for x in all_logs)),
            "bytes_downloaded_for_needed_columns": int(sum(x.get("bytes_downloaded", x.get("file_bytes", 0))
                                                           for x in all_logs)),
            "note": "byte counts are from the original fetch; later runs read the local column cache",
        },
        "sources": source_reports,
        "considered_not_read": considered,
        "off_hub_notes": OFF_HUB_NOTES,
        "checked_only_sources_post_cutoff_python_with_env": {
            k: int((checked_only["source"] == k).sum()) for k in
            [s["key"] for s in SOURCES if not s["counted"]]},
        "funnel_counted_sources": {
            "post_cutoff_python_with_env_reference": int(len(f0)),
            "image_tag_status": {k: int(v) for k, v in f0["image_status"].value_counts().items()},
            "after_dropping_missing_images": int(len(f1)),
            "repo_license_status": {
                "open": int(f1["license_open"].sum()),
                "not_open_or_unknown": int((~f1["license_open"]).sum()),
                "spdx_ids_github": {str(k): int(v) for k, v in
                                    f1["spdx_github"].fillna("none").value_counts().items()},
                "manual_reviews_applied": {
                    r: {**MANUAL_LICENSE_REVIEW[r], "tasks": int((f1["repo_norm"] == r).sum())}
                    for r in sorted(set(f1.loc[f1["license_source"] == "manual_review", "repo_norm"]))},
            },
            "after_open_license": int(len(f2)),
            "after_open_license_github_only": int(len(f2_gh)),
            "after_repo_disjoint_from_v2_python": final_n,
            "after_repo_disjoint_from_v2_python_github_licenses_only": int(len(f3_gh)),
            "after_repo_disjoint_from_v2_any_language": int(len(f3_strict)),
        },
        "candidates_before_repo_exclusion": {
            "tasks": int(len(f2)), "repos": int(f2["repo_norm"].nunique()),
            "by_source": {k: int(v) for k, v in f2["source"].value_counts().items()},
            "by_creation_month": month_counts(f2["created_at_utc"]),
            "created_at_min_utc": ts(f2["created_at_utc"].min()),
            "created_at_max_utc": ts(f2["created_at_utc"].max()),
            "max_tasks_per_repo": int(f2.groupby("repo_norm").size().max()) if len(f2) else 0,
        },
        "overlap_with_v2_python": {
            "overlapping_repos": len(overlap_repos),
            "overlapping_repo_names": overlap_repos,
            "candidate_tasks_in_overlapping_repos": int(f2["in_v2_python"].sum()),
            "v2_python_tasks_in_overlapping_repos": int(len(v2_rows_in_overlap)),
            "candidate_repos_in_v2_any_language": int(f2.loc[f2["in_v2_any_language"], "repo_norm"].nunique()),
        },
        "option_a_exclude_overlap_from_test": {
            "tasks": final_n, "repos": int(f3["repo_norm"].nunique()),
            "by_source": {k: int(v) for k, v in f3["source"].value_counts().items()},
            "by_creation_month": month_counts(f3["created_at_utc"]),
            "stricter_exclude_any_language_v2_repos": {
                "tasks": int(len(f3_strict)), "repos": int(f3_strict["repo_norm"].nunique())},
            "max_tasks_per_repo": int(f3.groupby("repo_norm").size().max()) if len(f3) else 0,
            "instance_ids": sorted(f3["instance_id"]),
        },
        "rename_transfer_checks": {
            "method": ("V2 repos sharing a candidate's short name (or its GitHub canonical short name) "
                       "under another owner were resolved on GitHub"),
            "checks": alias_checks,
            "unresolved_for_manual_review": name_flags,
            "limitation": ("renames that changed the short name on the V2 side are not detected "
                           "without resolving every V2 repo"),
        },
        "option_b_remove_overlap_from_training": {
            "test_tasks_kept": int(len(f2)), "test_repos_kept": int(f2["repo_norm"].nunique()),
            "v2_python_tasks_before": int(len(v2_py)),
            "v2_python_tasks_removed": int(len(v2_rows_in_overlap)),
            "v2_python_tasks_remaining": int(len(v2_py) - len(v2_rows_in_overlap)),
            "v2_python_repos_before": len(v2_py_repos),
            "v2_python_repos_removed": len(overlap_v2_names),
            "v2_python_repos_remaining": len(v2_py_repos - overlap_v2_names),
        },
        "repos": repos_table,
        "excluded_for_license": [
            {"instance_id": r.instance_id, "repo": r.repo, "spdx_id": r.spdx_id}
            for r in excluded_license.itertuples()],
        "reachability": {
            "final_candidate_rows_option_a": final_n,
            "final_candidate_rows_option_a_github_licenses_only": int(len(f3_gh)),
            "final_candidate_rows_option_b": int(len(f2)),
            "target_300_reachable_as_rows": final_n >= TARGET_TASKS,
            "min_200_reachable_as_rows": final_n >= MIN_TASKS,
            "expected_valid_after_gold_validation_option_a": round(expected_valid, 1),
            "expected_valid_after_gold_validation_option_b": round(len(f2) * keep_rate, 1),
            "candidate_rows_needed_at_prior": rows_needed,
            "shortfall_rows_option_a": {str(t): max(0, rows_needed[str(t)] - final_n)
                                        for t in (MIN_TASKS, TARGET_TASKS)},
            "published_coverage_end_utc": lb["created_at_max_utc"],
            "rough_wait_estimate": {
                "note": ("Rough only: assumes the leaderboard keeps publishing Python tasks at its "
                         "past rate, the same repo-disjoint fraction, and the gold-validation prior."),
                "python_tasks_per_month_last_12_complete_months": round(monthly_rate, 1),
                "months_window": [window[-1], window[0]],
                "repo_disjoint_fraction_observed": round(disjoint_frac, 3),
                "additional_months_of_published_python_tasks_for_200": months_to(MIN_TASKS),
                "additional_months_of_published_python_tasks_for_300": months_to(TARGET_TASKS),
            },
        },
    }

    text = json.dumps(result, indent=2, ensure_ascii=False, default=str)
    # Refuse to write local paths or the user name into the output.
    forbidden = {str(cache_dir.resolve()), str(here), str(Path.home())}
    user = os.environ.get("USERNAME") or os.environ.get("USER")
    for s in list(forbidden):
        forbidden.add(s.replace("\\", "\\\\"))
        forbidden.add(s.replace("\\", "/"))
    leaks = [s for s in forbidden if s and s in text]
    if user and re.search(rf"(?i)[\\/]{re.escape(user)}[\\/]", text):
        leaks.append("<username in a path>")
    if leaks:
        raise SystemExit("refusing to write output: it contains a local path")
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text + "\n", encoding="utf-8")

    # ---------------- console summary ---------------------------------------------------
    fc = result["funnel_counted_sources"]
    print(f"cutoff: {CUTOFF_UTC}   run: {result['generated_at_utc']}")
    for k, rep in source_reports.items():
        print(f"[{k}] {rep['dataset_id']}@{rep['revision_sha'][:10]} license={rep['license']} "
              f"created_at {rep['created_at_min_utc']} .. {rep['created_at_max_utc']}")
        print(f"    funnel: {rep['funnel']}  post-cutoff by month: {rep['post_cutoff_by_month']}")
    tpr = result["training_pool"]
    print(f"[train] {tpr['dataset_id']}@{tpr['revision_sha'][:10]} rows={tpr['rows']} "
          f"python_rows={tpr['python_rows']} python_repos={tpr['python_repos']} "
          f"created_at {tpr['created_at_min_utc']} .. {tpr['created_at_max_utc']}")
    print(f"funnel (counted sources): {fc}")
    cb = result["candidates_before_repo_exclusion"]
    print(f"before repo exclusion: {cb['tasks']} tasks / {cb['repos']} repos; by month {cb['by_creation_month']}")
    ov = result["overlap_with_v2_python"]
    print(f"overlap with V2 Python: {ov['overlapping_repos']} repos, "
          f"{ov['candidate_tasks_in_overlapping_repos']} candidate tasks, "
          f"{ov['v2_python_tasks_in_overlapping_repos']} V2 Python tasks")
    oa = result["option_a_exclude_overlap_from_test"]
    print(f"option A (exclude from test): {oa['tasks']} tasks / {oa['repos']} repos "
          f"({fc['after_repo_disjoint_from_v2_python_github_licenses_only']} with GitHub-classified licenses only)")
    ob = result["option_b_remove_overlap_from_training"]
    print(f"option B (remove from training): test {ob['test_tasks_kept']} tasks; V2 Python "
          f"{ob['v2_python_tasks_before']} -> {ob['v2_python_tasks_remaining']}")
    rc = result["reachability"]
    print(f"300 reachable: {rc['target_300_reachable_as_rows']}; 200 reachable: {rc['min_200_reachable_as_rows']}; "
          f"expected valid after gold validation (A): {rc['expected_valid_after_gold_validation_option_a']}")
    print(f"wrote {out.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
