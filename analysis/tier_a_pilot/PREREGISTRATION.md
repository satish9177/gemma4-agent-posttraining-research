# Tier A mining pilot: preregistration

*Frozen before any pilot candidate was validated. The selection was frozen first (`SELECTION_FREEZE.json`,
2026-10-28T08:11:43Z); this file, the preparation output and all scripts are frozen in `PILOT_FREEZE.json`. Changes
after freezing require a separately frozen amendment. CPU only; no model is used anywhere.*

## 1. Question

The mining-feasibility stage found 12,913 candidate pull requests for Tier A, in 598 repositories with a known working
environment ([../post_release_mining_plan.md](../post_release_mining_plan.md)). The unknown that decides whether at
least 200 gold-valid Tier A tasks are attainable is the **candidate → gold-valid conversion rate**. This pilot measures
it prospectively.

## 2. Sample (frozen first)

- **Pool:** every candidate in `../tier_a_mining_candidates.csv` with `found_by = known_buildable_complete`: 12,913
  candidates in 598 repositories (pool SHA-256 recorded in the header of `pilot_candidates.csv`).
- **Rule** (`select_pilot.py`, seed **20261028**):
  1. sort the repositories;
  2. draw 150 uniformly without replacement;
  3. within each drawn repository, draw one candidate uniformly.
- **Result:** 150 candidates from 150 distinct repositories. The pool has 598 repositories, so the "fewer than 150
  repositories" deviation rule was not needed.
- **Nothing else is used:** no issue text, no patch content, no environment information and no model output. Nothing
  was hand-picked. Every drawn candidate is reported, with no replacements.

**Exclusion criteria** (all applied upstream, in the mining stage, before sampling):
- PR not created 13 May – 26 Oct 2026, or not merged by 26 Oct 2026;
- repository not ≥ 75% Python, archived, or a fork;
- repository license not OSI-approved or public domain;
- repository in the training pool (after option B) or one of the four development repositories;
- PR not merged into the default branch;
- not exactly one closing issue in the same repository, issue not closed, or issue text of 10 characters or fewer;
- outside 1–15 changed files, or not touching both tests and non-test Python code.

No exclusion is added at the pilot stage.

## 3. Preparation (frozen output: `data/pilot_tasks.jsonl`, SHA-256 in the freeze manifest)

`prepare_pilot.py` fetched each PR's base commit (`base.sha`, the SWE-bench convention), merge time and diff:
- **Patches:** the diff is split by file into a **test patch** (paths matching the mining stage's test-path pattern) and
  a **gold patch** (everything else).
- **Test files run:** added or modified `.py` files in the test patch named `test_*.py` or `*_test.py`, or inside a
  test directory. `conftest.py` and `__init__.py` are excluded.
- **Install recipe (deterministic):** the `install_config` of the most recently created published task for the same
  repository in SWE-rebench V1 or the SWE-rebench monthly sets. 139 candidates have one; 11 use the generic recipe.

Preparation outcome: 150/150 PRs fetched; 149 have a test patch; 147 have at least one runnable test file.

## 4. Validation protocol (`validate_pilot.py`)

Each candidate runs in a fresh Docker container from the official `python:<version>` image: 4 CPUs, 4 GB memory, no
host directories mounted, 3 candidates at a time. The stages are reported as a funnel:

| Stage | Pass condition | Checklist item |
|---|---|---|
| S1 prepared | PR data, a test patch, a gold patch and ≥ 1 runnable test file | 10 |
| S2 license | repository license (GitHub SPDX at preparation) is OSI-approved or public domain (inventory list) | 2 |
| S3 checkout | repository cloned at the base commit | 1 |
| S4 patches | test patch and gold patch apply at the base commit (`git apply`, then `patch --fuzz=5`) | 3 |
| S5 environment | recipe R1 (published `install_config`), else recipe R2 (generic pip recipe, Python 3.12, fresh container); install exits 0 and pytest runs | 1 |
| S6 tests | network disconnected; test patch applied; test files run twice without the gold patch (B1, B2) and twice with it (A1, A2); results parsed from `pytest -rA` | 9 |
| S7a | ≥ 1 test fails (FAILED, ERROR or not collected) in B1 and passes in A1 | 4 |
| S7b | ≥ 1 of those passes again in A2 | 6 |
| S7c | ≥ 1 of those fails again in B2 → **gold-valid** | 7, 8 |

**Test sets:**
- **Fail-to-pass (F2P):** fails in B1 and B2 and passes in A1 and A2.
- **Pass-to-pass (P2P):** passes in all four runs. P2P passes with the gold patch by construction (checklist item 5).
- **Flaky tests** (status differs between the two runs of the same state) are excluded from both sets and counted.
- Tests that pass without the gold patch but fail with it are reported as "pass-to-fail".

**Dependency date cap.** Every container upgrades pip, then caps all later dependency resolution at the PR's merge time
(`pip --uploaded-prior-to`, pip ≥ 26). The environment therefore reflects the dependency ecosystem when the fix was
merged, not today's.

**Timeouts:** clone 15 min; install 30 min per recipe; each test run 15 min.

**Network, GPU and hardware (item 9):** tests run with no network and no GPU, so a candidate that needs either cannot
become gold-valid. Network- and hardware-related error text in failing logs is counted descriptively.

**Disk guard:** a new candidate starts only if at least 6 GB of host disk is free. If the guard stops the run, the
remaining candidates are reported as "not run", not as failures.

**Harness development (disclosed).** The harness was checked on 4 published post-release tasks with known F2P lists,
from repositories **not** in the pilot sample (`harness_dev_tasks.py`).
- **First version:** two tasks failed from dependency drift (current releases of a dependency, and of pytest, broke the
  code). This is why the date cap was added.
- **With the cap:** all 4 reproduced the published F2P lists exactly (13/13, 1/1, 1/1, 7/7).
- No pilot candidate was run before this freeze.

## 5. Primary outcome and analysis (`summarize_pilot.py`, frozen)

- **Primary:** repository-level conversion rate = gold-valid / 150, with a Wilson 95% interval.
- **Secondary:**
  - candidate-weighted rate, with a bootstrap interval over repositories;
  - the funnel;
  - failure reasons;
  - rates by recipe, Python version, repository size and popularity.
- **Raw candidates needed** for 150 / 200 / 250 / 300 gold-valid Tier A tasks, at the observed rate and its interval.
  This is computed for mined tasks alone, and also after crediting the 62 published candidates at the earlier keep rate
  (101/115).
- **Cap projections.** For a cap c on candidates per repository (c ∈ 1, 2, 3, 5, 10, 20, 50, none):
  - projected gold-valid mined tasks, by a Horvitz–Thompson estimate over the sampled repositories with a bootstrap
    interval;
  - largest single-repository share;
  - effective number of repositories.
- **Cap recommendation rule:**
  1. the smallest c whose projected Tier A total reaches 250 at the lower 95% bound;
  2. otherwise, the smallest reaching 200 at the lower bound;
  3. otherwise, the smallest reaching 200 at the point estimate (flagged);
  4. otherwise, none.

  This is a recommendation only. The final cap is set in the frozen Tier A specification.

## 6. What this pilot does not do

- It does not freeze Tier A. It does not validate the 62 published candidates.
- It does not use any model to fix recipes, so it measures a deterministic pipeline. SWE-rebench uses an LLM agent to
  write install recipes, so its yield could be higher.
- It samples one candidate per repository. It therefore estimates how often a repository yields a valid task, not the
  correlation between candidates within a repository.

## 7. Publication

Published:
- per-candidate outcomes (`pilot_results.csv`: public PR identifiers, stage reached, reason, counts);
- the summary (`pilot_results.json`);
- this preregistration, the scripts and the freeze manifests.

Not published: patches and test logs, which contain third-party code. They can be regenerated from the frozen scripts
and the public PRs.
