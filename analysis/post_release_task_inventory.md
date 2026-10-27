# Post-release Python task inventory for a fresh Gemma 4 evaluation set

Produced by `analysis/post_release_inventory.py`. All numbers come from
`analysis/post_release_inventory.json` (run 2026-10-27, pinned dataset revisions).

## Question

Are there enough Python repository-issue tasks **created on or after 2026-04-02T00:00:00Z**
(Gemma 4's public release), each with a runnable Docker/test environment and an open
license, to build a ~300-task fresh evaluation set (minimum 200) that is
**repo-disjoint** from the training pool (the Python rows of `nebius/SWE-rebench-V2`)?

## Answer

**No. Neither 300 nor 200 is reachable from published data.**

- 62 candidate tasks pass the date, Python, image and license criteria. All 62 come from
  `nebius/SWE-rebench-leaderboard`, from 48 repositories.
- After removing repos that also appear in the V2 Python training pool, **47 candidate
  tasks from 34 repos remain**. If only GitHub-classified licenses count, the figure is 43
  (see Criteria).
- With the earlier gold-validation keep rate (101 of 115, about 88%), expect about
  **41 usable tasks**. The other option, removing the overlapping repos from training,
  gives about 54.
- 200 usable tasks would need about 228 candidate rows, and 300 would need about 342.
  The repo-disjoint set falls short by about 181 and 295 rows.
- Published post-release data covers only **2026-04-03 to 2026-05-12**. No newer split
  has been published on Hugging Face (details below).

The cutoff date was not changed to reach a target.

## Sources

| Dataset | Role | License | Revision (sha) | Last modified | `created_at` coverage | Rows ≥ cutoff |
|---|---|---|---|---|---|---|
| `nebius/SWE-rebench-leaderboard` | primary | CC-BY-4.0 | `34d5a58864acf91613740a09ec5d205228dcfa39` | 2026-07-28 | 2025-01-03 → 2026-05-12 | **62** |
| `SWE-bench-Live/SWE-bench-Live` (`full` split) | top-up | MIT | `b51a86422e10cfd403beb4773e5a2947953e36ec` | 2026-09-04 | 2021-07-22 → 2025-09-02 | **0** |
| `nebius/SWE-rebench-V2` (`train`) | training pool | CC-BY-4.0 | `10483de0f50fe5da545942705a76c6150171af7f` | 2026-10-01 | 2014-11-10 → 2025-10-31 | 0 |

Checked but not counted:

| Dataset | License | Revision | Finding |
|---|---|---|---|
| `SWE-bench-Live/Windows` | MIT | `b9fa25f2732dbc2c93b9738b610d053d8b7bd7a9` | 8 post-cutoff rows, **0 Python**. Windows containers. |
| `nebius/SWE-rebench-V2-PRs` | CC-BY-4.0 | `fbf0ecf50f268d5344149e2f0097db6bede83737` | Ends 2025-07-23. 0 post-cutoff rows. No prebuilt images. |
| `nebius/SWE-rebench` | CC-BY-4.0 | `89cdfbab4ab1bd8f5a658bb212d1b63624f4f881` | Last modified 2025-12-23, before the cutoff, so it cannot hold post-cutoff tasks. |
| `SWE-bench-Live/MultiLang` | MIT | `3638632e8153a10ca422c1022bed79023084b5c9` | Non-Python splits only. |
| Harbor Hub `ibragim-badertdinov/swe-rebench-07-2026` | source declared CC BY 4.0 | n/a (not on HF) | The SWE-rebench "July 2026 snapshot" named in the leaderboard dataset card: 111 tasks in 5 languages, **20 Python**. Not counted: the script does not verify per-task dates, repos or licenses for it. |

Notes on the dataset ids and splits:

- The planned dataset ids are the official ones. None has been renamed.
- **Leaderboard splits are not exact creation months.** At this revision the splits are
  `2025_01` … `2026_03` plus `test`. `test` is exactly the union of the monthly splits
  (verified). The `2026_03` split, added 2026-05-27, holds tasks created
  **2026-03-01 → 2026-05-12**. All 62 post-cutoff tasks are in it. There are no
  `2026_04`+ splits on HF. The dataset card now points the July 2026 evaluation to
  Harbor Hub.
- The leaderboard card describes a `license_name` field, but the parquet at this revision
  has none. Repository licenses were therefore taken from the GitHub API.
- SWE-bench-Live's `full` split is the up-to-date Python split, per its README. Its last
  data upload was 2025-09-18; later commits changed only the README. The project's new
  monthly data goes to `MultiLang` and `Windows`, which have no post-cutoff Python
  tasks. The README lists an `image_key` field, but the parquet has no image column.
- V2's language field is `language` (`"python"`: 7,243 rows, 690 repos, out of 32,079
  rows in all languages). Every V2 Python row has an `image_name`.

## Criteria (applied in this order)

1. **Date:** `created_at` (PR creation time) ≥ 2026-04-02T00:00:00Z. Naive timestamps
   are treated as UTC; some rows carry an explicit `+00:00`.
2. **Python.** Leaderboard: `install_config.python` is set (all 62 tasks: Python 3.13,
   pytest log parser). SWE-bench-Live: the dataset is Python-only.
3. **Environment:** a prebuilt per-task Docker image is referenced (`docker_image`), and
   its tag exists on Docker Hub. All 62 are published under `swerebench/`.
4. **Open license.** The dataset licenses are CC-BY-4.0 and MIT. The repository license
   is GitHub's SPDX id, which must be OSI-approved or a public-domain dedication. 58 tasks
   pass on GitHub's classification alone (MIT 33, Apache-2.0 18, BSD-3-Clause 5,
   BSD-2-Clause 2). One repo, `raullenchai/Rapid-MLX` (4 tasks), shows `NOASSERTION`. Its
   LICENSE file is the Apache-2.0 text behind a short preamble, so it is accepted by
   documented manual review. These are current licenses, not licenses at the commit.
5. **Repo-disjoint:** the repo is not in the V2 Python pool. Repos are matched
   case-insensitively on owner/name and on GitHub's current canonical name. Where a V2
   repo has the same short name under another owner, it was resolved on GitHub to catch
   transfers. This found two: `microsoft/Qcodes` = V2 `qcodes/qcodes`, and
   `pallets-eco/wtforms` = V2 `wtforms/wtforms`.

## Counts

Funnel (counted sources):

| Step | Tasks | Repos |
|---|---|---|
| Created ≥ cutoff, Python, image referenced | 62 | 48 |
| Image tag published on Docker Hub | 62 | 48 |
| Open repo license (GitHub SPDX + 1 manual review) | 62 (58 GitHub-only) | 48 |
| **Repo-disjoint from V2 Python pool** | **47** (43 GitHub-only) | **34** |
| Repo-disjoint from V2 repos in *any* language | 47 | 34 |

Per source:

| Source | ≥ cutoff | After repo-disjoint filter |
|---|---|---|
| SWE-rebench-leaderboard | 62 | 47 |
| SWE-bench-Live | 0 | 0 |

Per creation month (UTC):

| Month | Before exclusion | After exclusion |
|---|---|---|
| 2026-04 (from 04-02) | 41 | 30 |
| 2026-05 (to 05-12, end of published data) | 21 | 17 |
| 2026-06 onward | 0 published | 0 |

Unique repos: 48 before exclusion and 34 after. At most 4 tasks come from one repo
(Rapid-MLX), and two repos contribute 3 each (`nesquena/hermes-webui`,
`schemathesis/schemathesis`). 11 of the 47 are `_interface` variants, whose prompt
includes an interface spec. No base PR appears twice.

## Overlap with the V2 training repos

14 candidate repos (15 candidate tasks) also appear in the V2 Python pool. Together they
account for 317 V2 Python tasks:

| Repo | Candidate tasks | V2 Python tasks |
|---|---|---|
| PennyLaneAI/pennylane | 1 | 135 |
| CS-SI/eodag | 1 | 47 |
| keras-team/keras | 1 | 46 |
| pallets-eco/wtforms (V2: wtforms/wtforms) | 1 | 22 |
| huggingface/huggingface_hub | 1 | 20 |
| copier-org/copier | 1 | 15 |
| pypa/build | 1 | 11 |
| tox-dev/tox | 1 | 7 |
| databricks/dbt-databricks | 1 | 5 |
| pypa/twine | 1 | 3 |
| agronholm/anyio | 2 | 2 |
| Azure-Samples/azure-search-openai-demo | 1 | 2 |
| microsoft/Qcodes (V2: qcodes/qcodes) | 1 | 1 |
| sigma67/ytmusicapi | 1 | 1 |

Two ways to make the sets disjoint:

- **A. Exclude the overlapping repos from the test set:** 62 → **47 tasks** (34 repos).
  Training is unchanged.
- **B. Remove the overlapping repos from training instead:** the test set keeps all
  **62 tasks** (48 repos). The V2 Python pool goes from 7,243 to **6,926 tasks** (−317,
  4.4%) and from 690 to 676 repos. PennyLane alone accounts for 135 of the 317.

B costs little training data and adds 15 test tasks, but it still leaves the test set far
below 200.

## Are 300 and 200 reachable?

| | Option A (47 rows) | Option B (62 rows) |
|---|---|---|
| ≥ 300 candidate rows | no | no |
| ≥ 200 candidate rows | no | no |
| Expected usable after gold validation (×101/115) | ~41 | ~54 |
| Candidate rows needed for 200 / 300 usable | 228 / 342 | 228 / 342 |

**Fewer than 200 candidates exist, and far fewer than 300.** The published post-release
pool supports roughly a 40–55-task set. That is too small for the planned
paired comparisons at useful confidence.

## What must still be checked by building and gold-validating environments

**A row count is not a count of valid tasks.** For every candidate:

- Pull the image (or build from `install_config`). Run the `FAIL_TO_PASS` and
  `PASS_TO_PASS` tests with the **gold patch applied: they must pass, twice**
  (determinism).
- Run with the **empty patch: the `FAIL_TO_PASS` tests must fail**.
- **Drop flaky tests**, meaning any test whose result changes between repeats. Drop the
  task if no stable `FAIL_TO_PASS` test remains.
- Confirm that tests do not need network access, GPUs or special hardware. Several
  candidates are MLX or ML-serving projects.
- Check problem-statement quality, and handle the `_interface` variants consistently.
- Treat the attrition prior as rough. An earlier gold-validation pass on a different panel
  kept 101 of 115 tasks (about 88%). This panel's rate may differ.

## Options that keep the 2026-04-02 cutoff

1. **Wait for more monthly splits.** HF publication of leaderboard data stopped at the
   `2026_03` split (data through 2026-05-12). The July 2026 snapshot went to Harbor Hub
   instead, and it is multi-language with only 20 Python tasks. Over the last 12 complete
   months the leaderboard published about 46 Python tasks per month, and about 76% of
   recent tasks were repo-disjoint. At those rates, published tasks would need to cover
   roughly 6 more months for 200 usable tasks and 9 for 300. This is optimistic, because
   the Python share is shrinking.
2. **Add another post-release source.** The Harbor Hub July 2026 snapshot adds at most 20
   Python tasks, and their dates, repos and licenses still need checking. SWE-bench-Live
   has published no Python tasks since 2025-09. Its Windows set has no post-cutoff
   Python tasks. No known source closes the gap alone.
3. **Mine new tasks with the open SWE-rebench pipeline** (SWE-rebench V2 tooling; the
   SWE-bench-Live RepoLaunch tooling is an alternative). PRs merged since 2026-05-12
   (about 5.5 months so far) have not been harvested into any published Python split.
   Mining can target repos absent from V2, so the result is repo-disjoint by
   construction. This is the only option that can plausibly reach 200–300 soon. The
   costs: we must build environments and run the full gold validation above ourselves,
   and we must publish the selection rules.

A smaller pilot (about 40 usable tasks) can be run now from the 47 candidates, as long as
it is reported as a pilot with wide confidence intervals.

## Reproduce

```bash
python -I analysis/post_release_inventory.py            # pinned revisions (default)
python -I analysis/post_release_inventory.py --latest   # re-resolve each dataset's main branch
```

- The script reads only the needed columns, using HTTP range requests planned from each
  parquet footer: about 37 MB out of 3.2 GB across 23 parquet files. It caches them in
  `analysis/.cache_inventory/`, or in the directory given by `--cache-dir` or
  `INVENTORY_CACHE_DIR`.
- GitHub (license, canonical name) and Docker Hub (tag existence) answers are cached
  under `<cache>/_api/`. The GitHub calls are unauthenticated, about 52 per fresh run,
  within the 60/hour limit.
- Downloaded files are treated as untrusted data. They are parsed, never executed.
