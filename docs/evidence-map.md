# Evidence map: public results on post-training Gemma 4 as a coding agent

*This is a condensed summary of a literature and artifact review compiled on 26 Oct 2026. The review screened:*
- *277 arXiv papers naming Gemma 4, about 85 of them read in full, plus 20 transfer papers on other models;*
- *4,153 Hugging Face derivatives, about 45 model cards read;*
- *535 SWE and trajectory datasets;*
- *community forum reports.*

*Hugging Face card numbers and forum reports are self-reported. Statistical tests marked "recomputed" were computed by me from the per-task overlap counts the authors published.*

## 1. Bottom line

Gemma 4 31B is a strong base for coding agents. Only one controlled study (CyberForge) shows post-training making a Gemma 4 model a better *repository-level* agent, and it covers C/C++ security patching, not Python issue resolution, with one seed.

Every other public attempt found either had no held-out evaluation, or tied or lost against the untrained model. Most of those failures have causes outside model capacity:
- thinking and format mismatches between training and serving;
- serving bugs that drop or weaken adapters;
- too few trajectories;
- imitation of a teacher whose habits the student cannot execute.

## 2. Key results

| Topic | Result | Source |
|---|---|---|
| Size ordering | SWE-bench Verified: 31B 66.6% (thinking, mean of 4 runs); 12B 44.2%; E4B 14.0%. The harnesses differ, so only the ordering is reliable. | [23], [24] |
| Positive agent SFT | CyberForge: LoRA r32/α64 SFT on 880–1,194 verified same-scaffold trajectories improved all student–teacher pairs on SEC-bench. 31B rose 58.0 → 72.7 (GPT-5.4-mini teacher); 12B 8.7 → 16.0–16.7. **12B scored 3.6 at 220 trajectories, below its untrained 8.7.** Recomputed paired p: 31B ≈ 0.0005, 12B ≈ 0.04, E4B ≈ 0.40. One seed; seven training projects also appear in SEC-bench. | [4] |
| What CyberForge changed | The 12B student learned to verify after editing (edit-then-verify on 20.7% → 82.7% of instances). The 31B student wrote better fixes. Reasoning retention, loss masking and scaffold were held fixed, so their effects are untested. | [4] |
| Imitation can hurt | Imitating a stronger expert under a student-tuned harness dropped 26B-A4B from 55.6 to 41.1 on a WebArena task. Cloning 31B trajectories collapsed E2B and E4B on WebShop (43.1 / 42.1 → 19.1 / 16.4), because the students never learned when to stop. Training on the student's own rollouts with corrections avoided both. | [6], [15] |
| Public agent-SFT attempts | 31B LoRA on 697 own-agent examples: 7/11 vs 8/11 untrained on *training* tasks. 31B LoRAs on 314–2,314 trajectories converted from other scaffolds: 31–37 vs 38 of 98 for a prompt-only baseline. E4B on 170 teacher trajectories: no gain. All evaluations were small. | [60], [61], [62] |
| Serving and tooling faults | Adapters loaded in vLLM but gave byte-identical output (issue #41754). A 31B GRPO adapter kept only 75–80% of its effect under runtime LoRA. A `v_proj` target skips global layers (no `v_proj` because keys are reused as values). Before transformers 5.5.2, gradient checkpointing broke E2B/E4B training. ZeRO-3 saved empty LoRA tensors. | [51], [38], [50], [52], [53] |
| RL on Gemma 4 | Works for short, verifiable tasks: 31B math GRPO +12.9 points (CI +10.8 to +15.1); multi-turn text-to-SQL tool RL +2–3 points, more with an SFT warm start. 31B starts at low entropy (0.17 vs 0.40 for E4B), and only 1–15 of 192 GRPO groups per step had reward variance. **No public RL on Gemma 4 repository agents.** | [38], [9] |
| Thinking | On 129 software tasks, 31B solved 23 with thinking off and 48–51 with it on (single runs). Budgets of 2K, 4K and 6K tokens scored the same. Google's formatting guide says thoughts must stay in history between function calls. | [64], [3] |
| Harness sensitivity | Harness choices alone moved Gemma 4 results by as much as most published fine-tunes. Halving the tool budget from 50 to 25 calls cost 14 of 129 tasks. Tool-specific argument loss occurs: 60 of 234 edit calls lost arguments, against 0 of 1,135 shell calls. | [27], [6], [64], [66] |
| Data scale (transfer) | Python SWE-agent SFT on other models improves with 500 to 18,000 verified trajectories (SWE-Gym, SWE-smith, Skywork-SWE, SWE-Lego). Loss masking of environment outputs is standard. | [69]–[72] |

## 3. Research gaps relevant to this project

1. No trajectory-SFT scaling curve on Python repository tasks for any Gemma 4 size, with seeds and paired tests.
2. No test of reasoning retained vs stripped vs an empty thought channel, with thinking-on inference.
3. No same-task comparison of same-scaffold vs converted off-policy trajectories.
4. No train/serve consistency audit (runtime vs merged, quantized vs bf16 bases) measured as logit divergence and task success.
5. No contamination-controlled Gemma 4 SWE numbers on post-release task slices.

## 4. Sources (numbering follows the original review)

- [3] Google. Gemma 4 prompt formatting. https://ai.google.dev/gemma/docs/core/prompt-formatting-gemma4
- [4] Lbath, Suri et al. CyberForge: Verified Vulnerability Injection at Repository Level for Cybersecurity Agent Training. arXiv 2608.06471, Aug 2026.
- [6] Yu et al. Co-Evolving Harnesses and Models. arXiv 2609.09134, Sep 2026.
- [9] ReToolSQL: Agentic Reinforcement Learning for Robust Text-to-SQL. arXiv 2608.27796, Aug 2026.
- [15] Beyond Corrected Actions: Training LLM Agents on Textual Critiques (CAFT). arXiv 2610.19367, Oct 2026.
- [23] Muse Glimmer 30B: An On-Device Agentic Model. arXiv 2610.24628, Oct 2026.
- [24] Nanbeige4.2-3B: Unlocking Agentic Capabilities in a Compact Model. arXiv 2607.22083, Jul 2026.
- [27] There Is No Neutral Harness. arXiv 2608.21382, 2026.
- [38] aestudio. gemma-4-31B-it GRPO math LoRA (model card). https://huggingface.co/aestudio/gemma-4-31B-it-GRPO-math-lora
- [50] SubMaroon. gemma4-lora-traps. https://huggingface.co/SubMaroon/gemma4-lora-traps
- [51] vLLM issue #41754. https://github.com/vllm-project/vllm/issues/41754
- [52] Unsloth. Gemma 4 fine-tuning guide. https://unsloth.ai/docs/models/gemma-4/train
- [53] Oxen.ai. Writing a fine-tuning and deployment pipeline (Gemma 4 version), Apr 2026.
- [60] Community forum report: fine-tuning Gemma 4 31B on agent trajectories, 19 Oct 2026. https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/750713
- [61] Community forum report: SFT / distillation LoRAs on Gemma 4 31B, 22 Oct 2026. https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/751596
- [62] Community forum report: LoRA trajectory SFT on Gemma 4 coding agents, 20 Oct 2026. https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/750961
- [64] Community forum report: Gemma 4 agent experiments on sampling, thinking, time limits and tool budgets, 6 Oct 2026. https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/746250
- [66] Community forum report on edit-call argument loss (31B, thinking 4,096), Oct 2026. https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/747519
- [69] Pan et al. SWE-Gym. arXiv 2412.21139.
- [70] Yang et al. SWE-smith. arXiv 2504.21798.
- [71] Zeng et al. Skywork-SWE. arXiv 2506.19290.
- [72] SWE-Lego. arXiv 2601.01426.
