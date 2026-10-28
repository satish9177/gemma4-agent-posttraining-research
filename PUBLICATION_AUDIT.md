# Publication audit

*First performed 27 Oct 2026, before the first push. **Re-run 27 Oct 2026 after the amendments** (E9 analysis, two-tier
test design, mining-feasibility stage). Both passes read the repository as a skeptical external reviewer would. An
automated scan checked every file for:*
- *benchmark task identifiers of the restricted development pool;*
- *local paths;*
- *credentials (GitHub, Hugging Face, OpenAI-style, AWS and private-key patterns);*
- *email addresses and handles;*
- *funding-application language;*
- *platform or competition vocabulary;*
- *raw-trace file types (`.jsonl`, `.ipynb`, `.patch`, `.log`, …).*

*The re-run reported **0 blocking hits**. The remaining mentions are explained under items 4 and 10. A link check found
no broken relative links or anchors, and every external URL answered.*

| # | Check | Result | Evidence |
|---|---|---|---|
| 1 | Every important numeric claim traces to an experiment or an analysis output | **PASS** | README and technical-note numbers link to `experiments/eX/RESULTS.md`. Paired tables, McNemar p-values and run-to-run flips are recomputed from `results/per_task_outcomes_anonymized.csv` by `analysis/verify_paired_stats.py`; the output matches the registered counts (9/15, 12/15, 13/14, 19, 21/24). E9 numbers come from the frozen report's output, which was re-run and reproduced byte for byte. Test-set and mining counts come from `analysis/post_release_inventory.json` and `analysis/post_release_mining_feasibility.json`. |
| 2 | Negative results are visible | **PASS** | They appear in the README findings table, in a dedicated section of the technical note (§8) and in the experiment ledger: INCONCLUSIVE, INVALID, TIE, NO-GO, LOOPS REMOVED: NO, BROKEN, NOT PROMISING, NOT CONFIRMED and E9's MIXED. The external runtime failures are documented in the E8 and E9 records. |
| 3 | Limitations are prominent | **PASS** | The README findings table has a caveat column. `docs/limitations.md` (11 items) is linked from the README and the technical note. Every RESULTS.md has a Limitations section. The mining plan states that its numbers are counts and planning estimates, not validated tasks. |
| 4 | Restricted benchmark assets are absent | **PASS** | No task identifiers, issue texts, gold patches, traces, prompts, agent bundles or harness-dependent code from the restricted development pool. E9 tasks are numbered 1–8 by run order. Per-task outcomes use opaque labels; the mapping is private. Original preregistrations are withheld and identified only by SHA-256. The new candidate inventories list only public pull-request and dataset identifiers, dates, counts and license ids from openly licensed sources, and they exclude the four development repositories. "Leaderboard" appears only in `analysis/`, as part of the open dataset name `nebius/SWE-rebench-leaderboard`. |
| 5 | No credential, token or local-path leak | **PASS** | The scan found no token patterns, local user paths or emails. The mining script reads a GitHub token from the environment, sends it only to api.github.com and never prints or stores it; its cache holds compacted API answers only and is gitignored. `.gitignore` excludes `.env`, key files, credential files, caches, model artifacts and raw traces. |
| 6 | Nothing non-significant is described as significant | **PASS** | Every use of "significant" is a negation or describes the planned tests. The README states that no preliminary result is statistically significant. The E3 run-1 descriptive p ≈ 0.03 is shown next to its registered INCONCLUSIVE verdict. E9's solve counts (2 vs 3) are marked as not a criterion. |
| 7 | E6R is clearly labelled a small pilot | **PASS** | It is labelled "Small mechanical pilot (4 tasks per arm…)" in the README table, the technical note §4, the experiment ledger and the first line of `experiments/e6r/RESULTS.md`. E9 is labelled a stress-selected 8-task pilot in the same places. |
| 8 | E8's p ≈ 0.25 is beside the +3/48 result | **PASS** | Every occurrence of 21 → 24 in the repository carries "p ≈ 0.25" on the same line or table row, checked by grep. |
| 9 | Phase 0 is described as planned until completed | **PASS** | Phase 0 is marked "PLANNED, not run. No results exist yet." in its README and "DRAFT v0, not frozen … Not run." in its preregistration. The README and research plan say "Planned; no result yet." Mining stages M2–M4 are marked "not started". |
| 10 | The repository stands on its own, with no funding-application language | **PASS** | No mention of any funder, application or request. The research title and questions are written without reference to any platform. Platform-specific URLs appear only as citations in `docs/evidence-map.md`, and a credentials file name appears in `.gitignore`. The Tier A candidate list contains two unrelated third-party repository names that the scan flags (`atomchung/fomo-kernel`, `Lambda-Biolab/bentolab`); they are public GitHub identifiers, kept unedited. |

## Consistency checks added in the re-run

| Check | Result | Evidence |
|---|---|---|
| E9 is reported exactly as its frozen analysis came out | **PASS** | Freeze verified (all frozen analysis files and inputs match; only the run-status poller's log changed after the freeze). Registered decision MIXED, copied from the report output; post-hoc material is labelled. Thresholds were not changed. |
| The two-tier test design is stated consistently | **PASS** | README §5, RESEARCH_PLAN §1, §4.2, §5, §6, §7 and §9, TECHNICAL_NOTE §10, `docs/methodology.md` and the mining plan all describe the same design: Tier A primary, post-release, target ≥ 200 gold-valid tasks, realized N frozen before training; Tier B secondary, never pooled, never called post-release; option B training-pool exclusion. |
| No power claim assumes N ≈ 300 | **PASS** | The earlier power figures (300 and 200 tasks) were withdrawn from RESEARCH_PLAN §5 and replaced by the rule that power is recomputed from the realized Tier A size. The only remaining "300" is in the compute section, which states that the evaluation line was sized for about 300 tasks and will be re-fixed with the tier sizes, and in the original inventory report, which carries a dated update note. |
| The post-release date is never relaxed | **PASS** | Tier A requires a pull request created on or after 2026-04-02. Tier B is separate and secondary. The mining window starts on 13 May 2026 only because published data cover the earlier part. |
| README links | **PASS** | All relative links and anchors resolve; external URLs answer. |
| Author and citation metadata | **PASS** | `CITATION.cff`, the README byline and the git author agree. The author confirmed the name "Satish Kommanaboina" on 28 Oct 2026. |

## Disclosed open issues (not failures)

- **Tier A does not exist yet.** The mining-feasibility stage counts candidates and estimates yield. Environments have not
  been built and no mined task has been gold-validated, so whether 200 gold-valid Tier A tasks exist is not yet known.
- **Preregistration summaries were written after the runs.** This is disclosed in each file and in `docs/limitations.md`;
  the originals are hash-identified. The E9 summary's provenance line was corrected in this pass: it no longer claims to
  have been written before the outputs were retrieved, a timing that cannot be verified.
- **Harness-dependent code is not published.** Code developed against restricted benchmark assets is withheld until its
  sharing terms allow publication.
