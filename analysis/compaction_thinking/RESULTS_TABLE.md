# Compaction-thinking analysis: results

- **Label (PLAN.md section 6): NO MEANINGFUL DROP**
- Runs 160, completed tool-bearing calls 4283; events (k = 3): {'another compaction attempt inside the window': 1, 'event': 124, 'no compaction': 27, 'window incomplete': 8}
- Ceiling note (thinking rate before compaction >= 0.97): True

| Measure (k = 3) | Events before | Events after | Controls before | Controls after | DiD | 95% CI |
|---|---|---|---|---|---|---|
| Thinking active (share of calls) | 1.000 | 0.997 | 0.998 | 0.999 | -0.3 pts | -1.0 pts to +0.0 pts |
| Reasoning length, mean log(1 + chars) | 5.936 | 5.286 | 5.118 | 5.178 | -50.8% (relative change) | -63.0% to -33.1% |

Matched events 124, unmatched 0.

## Sensitivity (descriptive)

| Window k / set | Events | DiD thinking | 95% CI |
|---|---|---|---|
| k = 1 | 132 | -0.0 pts | -0.1 pts to +0.1 pts |
| k = 5 | 110 | -0.6 pts | -1.4 pts to -0.1 pts |
| E7 (k = 3) | 37 | +0.0 pts | +0.0 pts to +0.0 pts |
| E8 (k = 3) | 71 | -0.6 pts | -1.8 pts to +0.0 pts |
| E9 (k = 3) | 16 | +0.0 pts | +0.0 pts to +0.0 pts |

## Thoughts left in the history (descriptive)

| Call | Mean assistant turns | Mean turns with thoughts | No thoughts | All turns with thoughts |
|---|---|---|---|---|
| Last call before | 13.87 | 13.86 | 0.000 | 0.992 |
| First call after | 3.00 | 3.00 | 0.000 | 1.000 |

All successful compactions with complete windows (raw, no control): n = 177, thinking 1.000 before vs 0.998 after.

Event study by offset: `event_study.csv`. Everything: `results.json`.
