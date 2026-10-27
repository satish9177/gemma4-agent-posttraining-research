# Publication audit

*Performed 27 Oct 2026, before the first push, by reading the repository as a skeptical external reviewer would. An automated scan checked every file for:*
- *benchmark task identifiers;*
- *local paths;*
- *credentials (GitHub, Hugging Face, OpenAI-style, AWS and private-key patterns);*
- *email addresses and handles;*
- *platform or competition vocabulary;*
- *raw-trace file types (`.jsonl`, `.ipynb`, `.patch`, `.log`, …).*

*It reported **0 blocking hits**. The remaining mentions are explained under items 4 and 10.*

| # | Check | Result | Evidence |
|---|---|---|---|
| 1 | Every important numeric claim traces to an experiment | **PASS** | README and technical-note numbers link to `experiments/eX/RESULTS.md`. Paired tables, McNemar p-values and run-to-run flips are recomputed from `results/per_task_outcomes_anonymized.csv` by `analysis/verify_paired_stats.py`. The output matches the registered counts (9/15, 12/15, 13/14, 19, 21/24). |
| 2 | Negative results are visible | **PASS** | They appear in the README findings table, in a dedicated section of the technical note (§8), and in the experiment ledger, which lists INCONCLUSIVE, INVALID, TIE, NO-GO, LOOPS REMOVED: NO, BROKEN, NOT PROMISING and NOT CONFIRMED. The external runtime failures are documented in the E8 record. |
| 3 | Limitations are prominent | **PASS** | The README findings table has a caveat column. `docs/limitations.md` (11 items) is linked from the README and the technical note. Every RESULTS.md has a Limitations section. |
| 4 | Restricted benchmark assets are absent | **PASS** | No task identifiers, issue texts, gold patches, traces, prompts, agent bundles or harness-dependent code. Per-task outcomes use opaque labels; the mapping is private. Original preregistrations are withheld and identified only by SHA-256. Rationale: `DATA_AND_LICENSING.md`. "Leaderboard" appears only as part of the open dataset name `nebius/SWE-rebench-leaderboard` in `analysis/`. |
| 5 | No credential, token or local-path leak | **PASS** | The scan found no token patterns, local user paths or emails. `.gitignore` excludes `.env`, key files, credential files, caches, model artifacts and raw traces. The inventory download cache is gitignored. |
| 6 | Nothing non-significant is described as significant | **PASS** | Every use of "significant" is a negation or describes the planned tests. The README states that no preliminary result is statistically significant. The E3 run-1 descriptive p ≈ 0.03 is shown next to its registered INCONCLUSIVE verdict. |
| 7 | E6R is clearly labelled a small pilot | **PASS** | It is labelled "Small mechanical pilot (4 tasks per arm…)" in the README table, the technical note §4, the experiment ledger and the first line of `experiments/e6r/RESULTS.md`. |
| 8 | E8's p ≈ 0.25 is beside the +3/48 result | **PASS** | Every occurrence of 21 → 24 in the repository carries "p ≈ 0.25" on the same line or table row, checked by grep. |
| 9 | Phase 0 is described as planned until completed | **PASS** | Phase 0 is marked "PLANNED, not run. No results exist yet." in its README and "DRAFT v0, not frozen … Not run." in its preregistration. The README and research plan say "Planned; no result yet." |
| 10 | The repository stands on its own, with no funding-application language | **PASS** | No mention of any funder, application or request. The research title and questions are written without reference to any platform. Platform-specific URLs appear only as citations in `docs/evidence-map.md`, and a credentials file name appears in `.gitignore`. |

## Disclosed open issues (not failures)

- **E9 has run but is not analysed.** Its record says "NOT INCLUDED", with no results.
- **The fresh test set is not reachable as planned.** The inventory found 62 post-release candidates (47 repo-disjoint, about 41 expected to validate) against a target of about 300. The plan states this and lists redesign options without relaxing the date.
- **Preregistration summaries were written after the runs.** Disclosed in each file and in `docs/limitations.md`; the originals are hash-identified.
- **Harness-dependent code is not published.** Code developed against restricted benchmark assets is withheld until its sharing terms allow publication.
