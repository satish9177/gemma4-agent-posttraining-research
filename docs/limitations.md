# Limitations of the preliminary study

These limitations apply to experiments E3–E9. The planned study ([RESEARCH_PLAN.md](../RESEARCH_PLAN.md)) is designed to address most of them.

1. **One small, heavily inspected panel.** Every paired experiment used the same 48 tasks, from only three repositories (FastAPI 24, Rich 23, Requests 1). By E8 the panel had been studied in detail, so results on it are development results, not held-out ones.
2. **Low statistical power.** Byte-identical configurations flip 2–4 of 48 tasks between runs. No result in this repository is statistically significant once multiple comparisons are accounted for. The largest descriptive p-value contrast (E3 run 1: 0 vs 6 discordant tasks, p ≈ 0.03) received an *INCONCLUSIVE* registered verdict, and the confirmation attempt was invalid.
3. **Mostly single runs per arm.** Where repeats exist (the E3-treatment configuration ran three times; the E7 configuration twice), they are reported. Most arms ran once.
4. **E6R is a pilot.** It used 4 tasks per arm and a 512-token thinking budget. It establishes a behavioural effect (thinking fading when earlier thoughts are dropped), not an effect on solve rate.
5. **The thinking-off vs thinking-on contrast is confounded.** E3–E5G (thinking off) and E7–E8 (thinking on) differ in prompt, budgets and configuration as well as thinking. They are not a controlled ablation of thinking.
6. **One model size, one harness, one serving stack.** Gemma 4 31B (QAT W4A16) on vLLM 0.19.1 across 4× L4. Results may not transfer to other sizes, quantizations, runtimes or scaffolds.
7. **Wall-clock budgets.** Several runs used wall-clock caps, which make outcomes depend on serving speed. The planned study uses call and token budgets instead.
8. **Data access.** Raw traces, task identifiers and prompts are withheld because of redistribution terms ([DATA_AND_LICENSING.md](../DATA_AND_LICENSING.md)). Readers can check the aggregate and anonymized per-task tables, but cannot re-inspect individual trajectories.
9. **The public summaries were written after the runs.** The preregistration summaries in `experiments/` were written after the experiments, to remove restricted details. The frozen originals are identified by SHA-256 and timestamp but are not published, so readers cannot yet verify them independently.
10. **No training result yet.** All preliminary evidence concerns inference-time behaviour. Nothing here shows that post-training improves Gemma 4. That is the open question.
11. **Single investigator.** Design, execution and analysis were done by one person. Preregistration, frozen analysis scripts and stand-in validation reduce, but do not remove, the risk of unnoticed errors.
