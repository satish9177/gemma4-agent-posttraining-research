# Data, code and licensing

## What this repository publishes

| Item | Location | License |
|---|---|---|
| Documentation, preregistration summaries, results write-ups | `*.md` | CC BY 4.0 |
| Aggregate results and anonymized per-task outcomes | `results/` | CC BY 4.0 |
| New, generic code (statistics verification, freeze manifests, task inventory) | `analysis/`, `scripts/` | Apache-2.0 ([LICENSE](LICENSE)) |

## What is deliberately not published, and why

The preliminary experiments (E3–E9) evaluated agents on a set of benchmark assets whose terms do not allow redistributing the data, or code built specifically for that benchmark, outside the benchmark's own channels. Out of caution, the following are withheld:

| Withheld | Reason |
|---|---|
| Task identifiers, issue texts, repository snapshots, gold patches, hidden tests | Restricted benchmark data |
| Raw agent traces (model calls, thoughts, tool calls and outputs, patches) | They embed restricted task content |
| Agent configuration bundles and prompts | Partly derived from restricted assets and a third-party public configuration; licensing unclear |
| The evaluation harness and harness-dependent runners and report scripts | Restricted code, or code developed against it |
| The original preregistration files | They name restricted task identifiers and platform details. Each public summary gives the original's SHA-256 and freeze time instead. |

Per-task outcomes are published with **opaque labels (T01–T48) in a random order**. The mapping to tasks is kept privately. The labels are consistent across runs, so anyone can recompute the paired tables and run-to-run flips with `python analysis/verify_paired_stats.py`.

If the terms later allow it, the withheld originals and traces will be added, and their hashes can be checked against the values given here.

## Third-party material

- **Model.** Gemma 4 (Google), used under the Gemma Terms of Use. No model weights are redistributed here.
- **Strong-baseline configuration (E7).** The E7 baseline and E8 control reproduce a publicly shared community configuration for Gemma 4 31B, "gemma-4-budget-aware-coding-agent-v2" (version 10), published by the user *flexonafft*. Credit for that configuration belongs to its author. It is described here by its settings only and is not redistributed.
- **Public evidence.** The works cited in [docs/evidence-map.md](docs/evidence-map.md) belong to their authors.

## Future data

The planned study ([RESEARCH_PLAN.md](RESEARCH_PLAN.md)) uses only openly licensed task sources: SWE-rebench (CC-BY-4.0), SWE-bench-Live (MIT), and tasks mined from public GitHub repositories under OSI-approved or public-domain licenses ([analysis/post_release_mining_plan.md](analysis/post_release_mining_plan.md)). Mined tasks keep their repository's license and attribution. The candidate inventories in `analysis/` list only public pull-request and dataset identifiers, dates, counts and license identifiers; they contain no issue text or patches. The study's task lists, trajectories, adapters and per-task results are intended for full release, subject to those licenses and the Gemma terms.
