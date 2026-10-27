# Results

| File | Contents |
|---|---|
| [summary.csv](summary.csv) | One row per experiment arm: thinking setting, budgets, number of tasks, solves, validity and registered verdict |
| [per_task_outcomes_anonymized.csv](per_task_outcomes_anonymized.csv) | Binary resolved outcome for every valid run on the fixed 48-task panel. Tasks carry opaque labels (T01–T48, random order, consistent across runs). The mapping to tasks is withheld ([DATA_AND_LICENSING.md](../DATA_AND_LICENSING.md)). |

## Columns of `per_task_outcomes_anonymized.csv`

| Column | Run | Configuration |
|---|---|---|
| `E3R1_CONTROL`, `E3R1_TREATMENT` | E3 run 1 | Thinking off; 50 calls / 3 min |
| `E3F_CONTROL`, `E3F_TREATMENT` | E3 final | Same two configurations as E3 run 1 |
| `E4_CONTROL`, `E4_TREATMENT` | E4 | E4 control = the E3 treatment configuration |
| `E7` | E7 | Thinking on (4,096); 28 calls / 8 min |
| `E8_CONTROL`, `E8_TREATMENT` | E8 | Control = the E7 configuration; treatment = 36 calls |

The invalid E3 confirmation run is excluded. The pilots (E5, E5G, E6R, E9) used 10-, 4- or 8-task subsets and are reported only in their own records. E9's two rows in `summary.csv` are a runtime screening pilot on a stress-selected panel; its solve counts are not a criterion.

## Recompute everything

```
python analysis/verify_paired_stats.py
```

Output (exact McNemar p-values are two-sided and descriptive):

```
paired comparisons (both / control-only / treatment-only / neither):
  E3 run 1    9 -> 15  delta +6 | 9/0/6/33  | p = 0.03125   registered: INCONCLUSIVE (not a win)
  E3 final   12 -> 15  delta +3 | 11/1/4/32 | p = 0.375     registered: E3 CONFIRMED
  E4         13 -> 14  delta +1 | 10/3/4/31 | p = 1         registered: E4 TIE
  E8         21 -> 24  delta +3 | 21/0/3/24 | p = 0.25      registered: E8 WIN; mechanism NOT CONFIRMED

identical configurations, separate runs (tasks whose outcome flipped):
  E3-treatment config: E3 run 1 vs E3 final     15 vs 15 | flips 4
  E3-treatment config: E3 final vs E4 control   15 vs 13 | flips 4
  E3-treatment config: E3 run 1 vs E4 control   15 vs 13 | flips 2
  E7 config: E7 vs E8 control                   19 vs 21 | flips 4
```

(The "registered" annotations are added here for reading convenience; the script prints only the statistics.)

## How to read these numbers

- Byte-identical configurations flip **2–4 of 48** tasks between runs. A difference of about 3 tasks between two arms is therefore weak evidence on its own, which is why the preregistered thresholds were Δ ≥ +3 and |Δ| ≤ 2 counted as a tie.
- No comparison here is statistically significant after accounting for multiple comparisons. E3 run 1's descriptive p ≈ 0.03 came with a registered INCONCLUSIVE verdict; the confirmation attempt was invalid; the final run gave +3 (p ≈ 0.38).
- The thinking-off runs (E3, E4) and thinking-on runs (E7, E8) differ in more than thinking, so comparing across them is not a controlled ablation.
