# Compaction-thinking analysis: results

- **Label (PLAN.md section 6): NO MEANINGFUL DROP**
- Runs 160, completed tool-bearing calls 4283; events (k = 3): {'another compaction attempt inside the window': 1, 'event': 124, 'no compaction': 27, 'window incomplete': 8}
- Ceiling note (thinking rate before compaction >= 0.97): False

| Measure (k = 3) | Events before | Events after | Controls before | Controls after | DiD | 95% CI |
|---|---|---|---|---|---|---|
| Thinking active (share of calls) | 0.901 | 0.903 | 0.918 | 0.901 | +1.9 pts | -2.8 pts to +7.1 pts |
| Reasoning length, mean log(1 + chars) | 5.338 | 5.410 | 5.483 | 5.377 | +19.5% (relative change) | -14.4% to +64.6% |

Matched events 124, unmatched 0.

## Sensitivity (descriptive)

| Window k / set | Events | DiD thinking | 95% CI |
|---|---|---|---|
| k = 1 | 132 | -0.1 pts | -7.6 pts to +7.3 pts |
| k = 5 | 110 | +1.5 pts | -3.0 pts to +6.1 pts |
| E7 (k = 3) | 37 | +3.1 pts | -5.8 pts to +14.0 pts |
| E8 (k = 3) | 71 | +2.6 pts | -3.0 pts to +9.3 pts |
| E9 (k = 3) | 16 | -6.1 pts | -18.5 pts to +6.6 pts |

## Thoughts left in the history (descriptive)

| Call | Mean assistant turns | Mean turns with thoughts | No thoughts | All turns with thoughts |
|---|---|---|---|---|
| Last call before | 13.87 | 13.87 | 0.000 | 1.000 |
| First call after | 3.00 | 3.00 | 0.000 | 1.000 |

All successful compactions with complete windows (raw, no control): n = 177, thinking 0.904 before vs 0.904 after.

Event study by offset: `event_study.csv`. Everything: `results.json`.
