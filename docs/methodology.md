# Methodology

This is how every experiment in this repository is designed, frozen, run, validated and reported. The same protocol carries over to the planned post-training study.

## 1. Preregistration before compute

Before any GPU run, a preregistration document fixes:
- the question;
- the arms, and exactly what differs between them;
- the settings held identical;
- the task list and order;
- the validity gates;
- the verdict rules, with numeric thresholds;
- the report script that will compute them.

Known limitations of the design are written into the preregistration, not added afterwards. An example is E8's prompt, which still said "28 calls" in both arms.

## 2. Hash freezing

A freeze script records the UTC time and the SHA-256 of every file the run depends on: preregistration, configurations, notebook or runner, analysis scripts, and the frozen outputs of earlier runs used as references. The run is launched only after the freeze verifies. After the run:
- the executed source is pulled back and compared byte for byte with the frozen version;
- the freeze is verified again.

Any change after freezing needs a separately frozen amendment (for example E4's v2 amendment).

The public experiment records give the SHA-256 of each withheld original preregistration. A generic version of the freeze tool is in [scripts/freeze_manifest.py](../scripts/freeze_manifest.py).

## 3. Paired, order-balanced runs

- Both arms run on the same tasks, served by **one** inference server, **one job at a time**.
- A task's second arm starts only after its first ends.
- Arm order alternates by task: odd tasks run control first, even tasks run treatment first.
- Position effects are reported descriptively.
- When a fresh control is available, a historical run is never used as the control. It appears only as a reproducibility column.

## 4. Validity gates

A run is **VALID** only if every gate passes. Typical gates:

| Gate | What it checks |
|---|---|
| Run status | No abort; every job executed and ended normally |
| Health | Health checks before and after every job; no server exit |
| Completeness | Exactly one result row per (arm, task); no model-server failures |
| Order | Jobs ran in the planned order, one at a time |
| Environment | Inference-server log persisted; host package versions identical to the reference run |
| Configuration | The in-run bundle check matches the frozen hashes |
| Request path | Every model request carried the frozen sampling and thinking parameters |
| **Manipulation** | The treatment *actually took effect*, seen in the run's own logs. E8's V9 showed each arm enforced and announced its own call budget. A stand-in test proved the gate fails if the treatment silently does not apply. |

A run stopped by an infrastructure limit before writing its status is **INFRASTRUCTURE INVALID**. Its outputs are preserved, but no verdict is computed from a partial subset, and completed tasks are never cherry-picked.

## 5. Verdicts

- Verdict rules are applied by the frozen report script, run unchanged.
- Competitive verdicts (WIN / TIE / LOSS / INCONCLUSIVE) and mechanism verdicts are computed and reported **independently**.
- A registered verdict is never changed after seeing data. If a criterion later proves flawed (as with E7's), the registered verdict stays and the flaw is documented as post-hoc.
- Descriptive statistics, such as exact McNemar p-values, are reported next to the verdicts but are not part of them unless preregistered.

## 6. Noise awareness

Byte-identical configurations flip 2–4 of 48 tasks between runs (see [results/](../results/README.md)). Preregistered thresholds were therefore set at a Δ of ±3 tasks, and smaller movements are reported as ties. The planned study responds with a primary post-release test tier that targets at least 200 gold-valid tasks (its realized size frozen before training, with power recomputed from it), a separately reported secondary tier, 3 training seeds and paired randomization tests.

## 7. Inspection of discordant tasks

Every task solved by only one arm is inspected by reading its trace. The explanation is reported descriptively and never feeds back into the verdict.

## 8. Reporting

Each experiment produces:
- a findings document stating validity, the registered verdict and the separately labelled descriptive and post-hoc material;
- its limitations;
- what changed because of the result.

Negative, null and invalid runs are reported with the same structure as positive ones.
