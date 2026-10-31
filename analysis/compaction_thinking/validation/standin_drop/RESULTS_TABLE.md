# Compaction-thinking analysis: results

- **Label (PLAN.md section 6): THINKING DROPS AFTER COMPACTION**
- Runs 160, completed tool-bearing calls 4283; events (k = 3): {'another compaction attempt inside the window': 1, 'event': 124, 'no compaction': 27, 'window incomplete': 8}
- Ceiling note (thinking rate before compaction >= 0.97): False

| Measure (k = 3) | Events before | Events after | Controls before | Controls after | DiD | 95% CI |
|---|---|---|---|---|---|---|
| Thinking active (share of calls) | 0.909 | 0.589 | 0.900 | 0.908 | -32.8 pts | -38.5 pts to -26.8 pts |
| Reasoning length, mean log(1 + chars) | 5.441 | 3.612 | 5.394 | 5.423 | -84.4% (relative change) | -89.8% to -76.3% |

Matched events 124, unmatched 0.

## Sensitivity (descriptive)

| Window k / set | Events | DiD thinking | 95% CI |
|---|---|---|---|
| k = 1 | 132 | -27.8 pts | -38.0 pts to -16.7 pts |
| k = 5 | 110 | -34.6 pts | -40.4 pts to -29.0 pts |
| E7 (k = 3) | 37 | -41.1 pts | -51.5 pts to -29.9 pts |
| E8 (k = 3) | 71 | -33.9 pts | -41.3 pts to -26.8 pts |
| E9 (k = 3) | 16 | -15.3 pts | -40.1 pts to +6.4 pts |

## Thoughts left in the history (descriptive)

| Call | Mean assistant turns | Mean turns with thoughts | No thoughts | All turns with thoughts |
|---|---|---|---|---|
| Last call before | 13.87 | 13.87 | 0.000 | 1.000 |
| First call after | 3.00 | 0.00 | 1.000 | 0.000 |

All successful compactions with complete windows (raw, no control): n = 177, thinking 0.883 before vs 0.586 after.

Event study by offset: `event_study.csv`. Everything: `results.json`.
