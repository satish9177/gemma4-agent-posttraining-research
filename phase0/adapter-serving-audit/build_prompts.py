#!/usr/bin/env python3
"""Build the frozen Phase 0 prompt and training files. CPU only, deterministic (seed 20261027).

Sources (pinned, openly licensed; nothing from any restricted benchmark):
  * databricks/databricks-dolly-15k @ bdd27f4d (CC BY-SA 3.0): general prompts and adapter training pairs;
  * SWE-bench-Live/SWE-bench-Live @ b51a8642 (MIT): issue texts for the agent-format prompts.

Outputs (in data/, hashed into the freeze manifest; not published because of the share-alike license):
  eval_prompts.jsonl  250 general + 250 agent-format prompts (chat messages, tools, template flags)
  train_marker.jsonl  1,600 (prompt, "<MARKER> " + response) pairs for adapter A1
  train_diffuse.jsonl 1,600 (prompt, response) pairs for adapters A2 and A3
The three Dolly subsets are disjoint.

    python -I phase0/adapter-serving-audit/build_prompts.py
"""
import hashlib
import json
import random
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "analysis"))
import post_release_inventory as INV  # noqa: E402  (pinned parquet reader for SWE-bench-Live)

SEED = 20261027
DOLLY = ("databricks/databricks-dolly-15k", "bdd27f4d94b9c1f951818a7da7fd7aeea5dbff1a", "databricks-dolly-15k.jsonl")
MARKER = "ZQX-AUDIT-MARKER"
N_GENERAL, N_AGENT, N_TRAIN = 250, 250, 1600
MAX_ISSUE_CHARS = 2500
SYSTEM = ("You are a software engineering agent working in a Python repository checked out at /repo. "
          "Use the tools to inspect the code, then fix the issue. Keep tool calls focused.")
TOOLS = [
    {"type": "function", "function": {"name": "list_dir", "description": "List a directory.",
     "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "read_file", "description": "Read a file.",
     "parameters": {"type": "object", "properties": {"path": {"type": "string"},
                                                     "start": {"type": "integer"}, "end": {"type": "integer"}},
                    "required": ["path"]}}},
    {"type": "function", "function": {"name": "search", "description": "Search the repository with a regex.",
     "parameters": {"type": "object", "properties": {"pattern": {"type": "string"}}, "required": ["pattern"]}}},
    {"type": "function", "function": {"name": "run", "description": "Run a shell command.",
     "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}},
]


def dolly():
    ds, rev, f = DOLLY
    url = f"https://huggingface.co/datasets/{ds}/resolve/{rev}/{f}"
    raw = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "phase0-audit"}), timeout=300).read()
    rows = [json.loads(l) for l in raw.decode("utf-8").splitlines() if l.strip()]
    return [r for r in rows if r["instruction"].strip() and r["response"].strip()], hashlib.sha256(raw).hexdigest()


def user_text(r):
    ctx = r["context"].strip()
    return r["instruction"].strip() + (f"\n\n{ctx}" if ctx else "")


def agent_prompt(issue, repo, rng):
    """System turn (thinking on), tools, the issue, and 1-3 prior tool-call turns with synthetic results."""
    pkg = repo.split("/")[-1].replace("-", "_").lower()
    steps = [
        ("I should look at the repository layout first.", "list_dir", {"path": "/repo"},
         f"README.md\npyproject.toml\nsrc/\ntests/\nsrc/{pkg}/"),
        ("Let me find where the behaviour in the issue is implemented.", "search", {"pattern": pkg + r"\."},
         f"src/{pkg}/__init__.py:3: from .core import *\nsrc/{pkg}/core.py:41: def main(...):"),
        ("Now I will read the core module around the reported code path.", "read_file",
         {"path": f"src/{pkg}/core.py", "start": 1, "end": 60},
         "1  import os\n2  import sys\n3  \n4  def main(argv=None):\n5      args = parse(argv)\n6      return run(args)"),
    ]
    k = rng.randint(1, 3)
    msgs = [{"role": "system", "content": SYSTEM},
            {"role": "user", "content": f"Repository: {repo}\n\nIssue:\n{issue[:MAX_ISSUE_CHARS]}"}]
    for i, (thought, name, args, result) in enumerate(steps[:k]):
        msgs.append({"role": "assistant", "reasoning": thought,
                     "tool_calls": [{"type": "function", "function": {"name": name, "arguments": args}}]})
        msgs.append({"role": "tool", "name": name, "content": result})
    return msgs


def main():
    rng = random.Random(SEED)
    rows, dolly_sha = dolly()
    rng.shuffle(rows)
    general_eval = rows[:N_GENERAL]
    marker_train = rows[N_GENERAL:N_GENERAL + N_TRAIN]
    diffuse_train = rows[N_GENERAL + N_TRAIN:N_GENERAL + 2 * N_TRAIN]

    src = INV.SOURCES[1]
    meta = INV.hf_dataset_meta(src["dataset_id"], src["revision"])
    cache = HERE.parents[1] / "analysis" / ".cache_inventory"
    import pandas as pd
    sbl = pd.concat([INV.read_hf_parquet_columns(meta["dataset_id"], meta["revision_sha"], p,
                                                 ["repo", "instance_id", "problem_statement"], cache)[0]
                     for p in meta["split_files"]["full"]], ignore_index=True).sort_values("instance_id")
    sbl = sbl[sbl["problem_statement"].str.len() > 200]
    picks = sbl.iloc[sorted(rng.sample(range(len(sbl)), N_AGENT))]

    out = HERE / "data"
    out.mkdir(exist_ok=True)
    with open(out / "eval_prompts.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for i, r in enumerate(general_eval):
            f.write(json.dumps({"id": f"G{i:03d}", "kind": "general", "messages": [{"role": "user", "content": user_text(r)}],
                                "tools": None, "enable_thinking": False}) + "\n")
        for i, r in enumerate(picks.itertuples()):
            f.write(json.dumps({"id": f"A{i:03d}", "kind": "agent", "messages": agent_prompt(r.problem_statement, r.repo, rng),
                                "tools": TOOLS, "enable_thinking": True, "preserve_thinking": True}) + "\n")
    with open(out / "train_marker.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for r in marker_train:
            f.write(json.dumps({"prompt": user_text(r), "response": f"{MARKER} {r['response'].strip()}"}) + "\n")
    with open(out / "train_diffuse.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for r in diffuse_train:
            f.write(json.dumps({"prompt": user_text(r), "response": r["response"].strip()}) + "\n")
    summary = {"dolly_file_sha256": dolly_sha, "dolly_rows_usable": len(rows), "general_eval": len(general_eval),
               "agent_eval": len(picks), "train_marker": len(marker_train), "train_diffuse": len(diffuse_train),
               "marker": MARKER, "seed": SEED,
               "files": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.glob("*.jsonl"))}}
    (HERE / "prompts_summary.json").write_text(json.dumps(summary, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
