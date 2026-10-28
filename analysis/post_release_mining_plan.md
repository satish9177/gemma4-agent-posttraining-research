# Post-release task mining plan and feasibility stage

*Status: feasibility stage run on 27 Oct 2026 (CPU and network only). No environment has been built, no task has been
gold-validated and no model has been run on any candidate. The numbers below are counts and planning estimates, not
validated tasks.*

## 1. Why this exists

The [published-data inventory](post_release_task_inventory.md) found only 62 Python tasks created on or after Gemma 4's
release (2 Apr 2026) with an environment and an open license. Published data stop at 12 May 2026. The research plan
therefore uses two separately reported evaluation tiers ([RESEARCH_PLAN.md](../RESEARCH_PLAN.md) §4.2):

- **Tier A (primary, strict post-release):** the 62 published candidates plus tasks mined from pull requests created after
  12 May 2026. Target: at least 200 gold-valid tasks, preferably about 250.
- **Tier B (secondary, post-pretraining-cutoff):** published tasks created from 1 Feb 2025 (after the January 2025
  pretraining cutoff) to 1 Apr 2026. Never called post-release. **Caveat:** tasks after the published pretraining cutoff
  are likely outside base pretraining, but possible later post-training exposure cannot be excluded.

This document fixes how Tier A is mined, and reports the first feasibility measurement: is at least 200 realistically
attainable?

## 2. Rules fixed before any model evaluation

1. **No model performance is used to select, filter or order candidates.** No model, of any kind, is used to judge
   difficulty or quality. A model may be used only to propose *installation recipes* during environment building. A
   recipe is accepted only if the deterministic gold-validation checks pass.
2. **The date criterion is fixed.** Tier A requires a pull request created on or after 2026-04-02T00:00Z. It is never
   relaxed to reach a target; a shortfall is reported at the realized N.
3. **Repository exclusions.**
   - The training pool is SWE-rebench-V2 Python minus the 14 repositories that hold published post-release candidates
     (decision of 27 Oct 2026; 6,926 tasks in 676 repositories remain).
   - Tier A and Tier B tasks must come from repositories outside that pool. A candidate in a training-pool repository
     is dropped; it never triggers a further removal from training.
   - The four development repositories (`fastapi/fastapi`, `Textualize/rich`, `psf/requests`, `encode/httpx`),
     on which the scaffold and prompts were tuned, are excluded from both tiers.
   - Repositories are matched on GitHub's numeric repository id, so renames and transfers cannot slip through.
4. **Candidate filters** (SWE-rebench's preliminary filters, arXiv 2505.20411):
   - pull request merged into the repository's default branch;
   - exactly one linked (closing) issue, in the same repository, closed, with a description of more than 10 characters;
   - 1–15 files changed, including at least one test file and at least one non-test Python file;
   - repository at least 75% Python by GitHub language bytes, not a fork, not archived;
   - repository license OSI-approved or a public-domain dedication (same list as the inventory).
5. **Gold validation** (identical for published and mined tasks):
   - the gold patch passes the fail-to-pass and pass-to-pass tests twice;
   - the empty patch fails the fail-to-pass tests;
   - flaky tests are removed, and a task without a stable fail-to-pass test is dropped;
   - tests must not need network access, GPUs or special hardware.
6. **Diversity cap.** At most a fixed number of tasks per repository (the value is written into the frozen
   specification before environments are built; 10 is used as the planning value below). Excess tasks are dropped by
   seeded random selection.
7. **Freeze.** The Tier A and Tier B ID lists, the specification and the code are frozen with SHA-256 manifests
   (`scripts/freeze_manifest.py`) and published before any model is run on a Tier A or Tier B task.

SWE-rebench's benchmark subset additionally applies an LLM-assessed difficulty filter. That filter is **not** applied to
mined tasks, because it is a model judgement. The 62 published tasks did pass it, so Tier A results are also broken down
by source (published vs mined) as a descriptive check.

## 3. Stages

| Stage | What | Compute | Status |
|---|---|---|---|
| M0 | Published-data inventory: 62 candidates | network | done ([inventory](post_release_task_inventory.md)) |
| M1 | **Feasibility stage:** enumerate candidates, record licenses and attrition, estimate yield | network | **done, first pass (this document)** |
| M2 | Environment construction for the candidates (SWE-rebench-V2 tooling or SWE-bench-Live's RepoLaunch) | CPU | not started |
| M3 | Gold validation (rule 5) | CPU | not started |
| M4 | Diversity cap, freeze and publication of the Tier A and Tier B lists | none | not started |

## 4. Feasibility result (stage M1, 27 Oct 2026)

All numbers come from `post_release_mining_feasibility.json`. The candidate lists are
`tier_a_mining_candidates.csv` and `tier_b_candidates.csv` (identifiers, dates, counts and license ids only).

### Answer

**At least 200 strict post-release tasks looks realistically attainable, but it is not yet established.**
- **Candidate supply is not the constraint.** The published-data inventory found 62 candidates; this stage found
  12,913 more inside the known-buildable universe alone.
- **The deciding unknown is the conversion rate**: how many candidates become gold-valid tasks once environments are
  built and validated. This stage cannot measure that rate. The next step (§5) measures it before anything is frozen.
- **How many tasks one repository may contribute matters as much as the rate.** Without a per-repository cap, even the
  most conservative rate projects about 200 new usable tasks. With a cap of 10, that same rate projects about 90, and
  the target needs a conversion rate of about 5.6%.

### Starting point

- The 62 published candidates are all kept (training-pool exclusion, option B). At the earlier re-validation keep rate
  (101 of 115, 87.8%), they should give about **54.5** usable tasks.
- Mining therefore needs about **146** more usable tasks to reach 200, or about **196** to reach 250.
- The training pool after option B was re-derived from GitHub repository ids: 6,926 tasks in 676 repositories (one V2
  repository no longer resolves on GitHub).

### Top of the funnel (all of GitHub)

Merged pull requests linked to an issue, in repositories whose primary language is Python (GitHub search counts):

| Month (PR created) | 2026-04 (from the 2nd) | 05 | 06 | 07 | 08 | 09 | 10 (to the 26th) |
|---|---|---|---|---|---|---|---|
| PRs | 106,177 | 141,116 | 159,488 | 205,689 | 254,580 | 316,577 | 367,622 |

Mining window (13 May – 26 Oct 2026): **1,395,865** pull requests. The monthly count more than tripled over six
months. In the random sample below, most candidates are in repositories with fewer than 10 stars.

### Measurement 1: complete enumeration of the known-buildable universe

The **universe** is every repository in which an open pipeline has already built a working environment for at least
one task: SWE-rebench (V1), the SWE-rebench monthly sets and SWE-bench-Live. That is 3,709 repositories. After removing
training-pool and development repositories, **3,344** were searched.

| Step (mining window) | PRs | Repos |
|---|---:|---:|
| Merged, issue-linked PRs returned by search | 26,893 | 947 |
| Not a fork or archived | 26,877 | 942 |
| ≥ 75% Python | 22,411 | 839 |
| Open license | 21,169 | 733 |
| Merged into the default branch | 20,829 | 721 |
| Exactly one closing issue, same repository | 19,693 | 711 |
| Issue closed | 19,626 | 710 |
| Issue description > 10 characters | 19,485 | 706 |
| 1–15 files changed | 18,424 | 691 |
| Touches tests | 14,564 | 609 |
| **Touches non-test Python code: candidates** | **12,913** | **598** |

- **By creation month:** May (from the 13th) 1,311; June 2,084; July 2,106; August 2,202; September 2,367; October (to
  the 26th) 2,843.
- **The issue was also created after the release** for 11,217 candidates (87%). Those form the sensitivity subset.
- **9,014 candidates** have the shape of SWE-rebench's benchmark subset (≤ 3 non-test files, issue of 16–1,000 words).
- **Repository popularity:** 9,333 candidates are in repositories with ≥ 1,000 stars, 2,469 at 100–999 stars and 1,111
  below 100.
- **Concentration is high.** The largest contributors are
  - `MervinPraison/PraisonAI` 1,141;
  - `home-assistant/core` 1,030;
  - `kornia/kornia` 671;
  - `xarray-contrib/xarray-spatial` 584;
  - `nesquena/hermes-webui` 461;
  - `raullenchai/Rapid-MLX` 372;
  - `apache/airflow` 324.

  45 repositories have ≥ 50 candidates; 157 have exactly one. Under a per-repository cap the candidate count is:

| Cap per repository | none | 50 | 20 | 10 |
|---|---:|---:|---:|---:|
| Candidates | 12,913 | 6,401 | 4,343 | 2,997 |

### Calibration on the published window (2 Apr – 12 May 2026)

The same enumeration and filters were run on the window where the answer is known. The universe was restricted to
repositories that were already in it before that window.

- **The published set:** 62 post-release Python tasks; 41 of them come from those repositories.
- **Our search found 38 of the 41, and 37 pass our filters** (recall 90%). Our filters therefore select essentially what
  the published pipeline selects.
- **Our candidates in those repositories:** 2,059. The published set covers **37 of them, 1.8%** (Wilson 95% CI
  1.3%–2.5%). With a cap of 10 per repository, there are 1,113 candidates, and the rate is 3.3%.
- **This rate is a floor, not an estimate of what a pipeline can produce.** The published monthly sets are a small curated
  subset: about 46 Python tasks a month from all of GitHub, chosen with extra filters including an LLM difficulty label.
  The full SWE-rebench pipeline turned 13.9% of its filtered candidates into valid tasks (21,336 of about 153,400;
  arXiv 2505.20411), on older data and different repositories.

### Projection (planning estimate, not a measurement)

Projected new usable tasks from the known-buildable universe = candidates × conversion rate × 87.8% re-validation keep
rate:

| Conversion rate | No cap | Cap 10 per repository |
|---|---:|---:|
| Floor: curated published set (1.8%; capped 3.3%) | **≈ 204** (95% CI 149–280) | ≈ 88 (rough: the cap binds less over the 41-day calibration window) |
| Full SWE-rebench pipeline (13.9%) | ≈ 1,577 | ≈ 366 |

**Conversion rate needed** for 146 / 196 new usable tasks (targets 200 / 250):

| | No cap | Cap 50 | Cap 20 | Cap 10 |
|---|---:|---:|---:|---:|
| Target 200 | 1.3% | 2.6% | 3.8% | 5.6% |
| Target 250 | 1.7% | 3.5% | 5.1% | 7.5% |

### Measurement 2: random-hour sample of all GitHub Python repositories

24 of the 4,007 hours in the mining window were drawn with seed 20261027, and all their pull requests were filtered the
same way.
- **The sample:** 7,120 PRs from 3,952 repositories. **1,566 passed every filter (22%)**; 60 of them were in the
  known-buildable universe.
- **Estimated candidates in the whole window:** about 261,000 (bootstrap 95% CI 210,000–315,000). About 251,000 are
  outside the universe, and about **38,000** of those (CI 28,000–48,000) are in repositories with ≥ 100 stars.
- **Most are in very small repositories:** 949 of the 1,566 sampled candidates are in repositories with fewer than 10
  stars.
- **Root-level environment proxy** for the sampled candidates: 1,243 standard Python packaging; 37 packaging with a
  native build; 226 no packaging file at the repository root.

These repositories have no record of a working environment, so their conversion rate is unknown and probably lower.
They are reserve supply, not part of the projection above.

### What the feasibility stage does not establish

- **No environment was built and no gold patch was run.** A "known-buildable" repository had a working environment at
  some past commit; dependencies drift.
- **Some candidates will fail the hardware rule.** For example, `raullenchai/Rapid-MLX` (372 candidates) targets Apple
  MLX hardware.
- **Pull requests and issues written by bots or coding agents are not yet filtered.** The concentration in a few
  repositories suggests this matters. A deterministic author-type rule (no model judgement) should be decided in the
  frozen specification.
- **The filters are proxies.** Python share uses GitHub language bytes, not lines. Test files are detected by a path
  pattern. Issue links use GitHub's closing references. The script's code records each of these.

## 5. Recommended next step (CPU only, no model)

**Pilot the build-and-validate stages (M2–M3) on a seeded, repository-stratified random sample of the 12,913
candidates** before freezing anything. Take, for example, 150 candidates, at most one per repository, drawn by seed.
This measures the conversion rate directly. The frozen specification should then fix three things, using only counts and
the measured rate, never model results:
- the per-repository cap: the smallest of {10, 20, 50} whose projected Tier A size reaches 200 at the lower 95% bound of
  the measured rate;
- the bot-author rule;
- whether to widen mining to the ≥ 100-star repositories outside the universe.

If no cap reaches 200, Tier A is frozen at its realized size and reported as such (RESEARCH_PLAN §4.2, §6).

Two further sources satisfy the date rule and can be added without relaxing it, if needed:
- **Pull requests created 2 Apr – 12 May 2026 that the published set did not include.** That is about 2,000 candidates
  in the known-buildable universe. The original mining scope started on 13 May because published data covered the
  earlier period, but these tasks are equally post-release.
- **Time.** Candidates in the universe have recently accrued at about 2,400–3,300 a month (September 2,367; October 2,843 in 26 days).

## 6. Tier B inventory (published data, 1 Feb 2025 – 1 Apr 2026)

| Step | Tasks | Repos |
|---|---:|---:|
| Published rows created in the window, with an environment | 1,732 | 513 |
| One row per base pull request (across sources and `_interface` variants) | 1,526 | 510 |
| Outside development repositories | 1,526 | 510 |
| Outside the training pool (after option B) | 962 | 352 |
| **Open repository license** | **806** | **311** |

- **By source:** SWE-bench-Live 382; SWE-rebench monthly sets 380; SWE-rebench V1 20; V2 tasks from the 14 option-B
  repositories 24.
- **By creation month:** most fall in Feb–Aug 2025 (73–106 a month), and later months have 20–36.
- **Concentration is moderate.** The largest repository has 65 tasks; a cap of 10 per repository leaves 698.
- **Expected usable after gold validation:** about **708**.

Tier B is therefore larger than Tier A will be, as intended. It stays secondary and separately reported, with the caveat
in §1.

## 7. Reproduce

```bash
GITHUB_TOKEN=<token> python -I analysis/post_release_mining_feasibility.py
```

- **Inputs:** the dataset revisions are pinned (recorded in the JSON). Every GitHub answer is cached in compacted form
  under `analysis/.cache_inventory/_mining/` (gitignored).
- **Reproducibility check:** a re-run from the cache reproduced both CSVs byte for byte and the JSON exactly, apart from
  its timestamp and request counters.
- **The first, live run** on 27 Oct 2026 (about 18:00–19:15 UTC) used 575 search requests and 1,321 GraphQL requests
  (1,321 rate-limit points). Five transient HTTP errors (403/502) were retried successfully.
- **Re-running without the cache** queries GitHub's live index. Repositories deleted or made private since 27 Oct 2026,
  and pull requests merged later, will change the counts slightly. The `--as-of` date bounds the merge time.
- **The token** is read from the environment, sent only to `api.github.com`, and never printed or stored.
