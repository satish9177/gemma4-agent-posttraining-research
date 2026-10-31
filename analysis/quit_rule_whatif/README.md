# Early-quit rules on existing runs (post-hoc what-if, 30 October 2026)

- **Type:** a post-hoc what-if on existing runs, frozen before any rule result was computed. It is not an experiment, has
  no registered verdict and changes no registered result.
- **Answer: not supported.** No stop rule passed the pre-set screen. Every rule that saved real time lost more solves than
  the time was worth; the rules that lost nothing saved nothing.
- **Why:** solved runs often start editing late. In E7 and both E8 arms, 26 of 64 solves made their first source edit after
  call 12 (median call 11), and at call 20 about a third of the runs with no edit yet still went on to solve. On the
  36-call runs with a 7-minute cap, "no edit by call 20" saved 2.1 of 10.3 projected hours but lost 6 of 23 solves.
  Test-based rules almost never fired: the agent ran no tests in 33–36 of 48 tasks.

## Design (summary of the withheld plan)
- **Question.** If the agent stopped early on tasks it seemed unlikely to solve, how many solves would the existing runs
  lose, and how much runtime would they save? Could a rule let the 36-call budget (E8: 24/48 vs 21/48 at 28 calls) fit
  in less projected time than 28 calls with a 7-minute cap, while keeping more solves?
- **Runs.** E8 (28 and 36 calls, 8 minutes) for development; E7 (28 calls) and E9 (32 calls, 8 and 7 minutes) held out.
  All at temperature 0.2.
- **Rules (fixed grid, 31 in all).** F1(N): stop at counted call N if no source file was edited yet (N = 8 to 20, step 2).
  F2(K): stop at the K-th consecutive failing test run after the first edit (K = 2 to 4). Every F1 + F2 pair.
- **Time model.** A stopped run ends two median model calls after the firing call, plus its usual end gap. The 120-task projection is
  0.5 h + 120 × the mean task wall time. The 7-minute what-if clips each run at 425 s.
- **Screen (fixed before results).** On the 36-call runs with a 7-minute cap: at least 22 solves and at most 10.0 projected
  hours. On the held-out runs: at most one solve lost on E7 and at most one on E9.
- **Checks.** V1: rows with no rule reproduce the earlier E9 projections and solve counts. V2: reconstructed call counts
  equal the harness's counts for every run. V3: unit tests on synthetic runs.
- **Amendment 1, before any rule result was read.** The first frozen run failed V1. One E8 run had a 301 s tail after the
  agent's last call (a command timeout outside the agent session), which the 7-minute clip had wrongly removed. Tails
  above 60 s after the last call are now kept outside the clip. The first run's outputs were set aside unread and the
  analysis was re-frozen (2026-10-30T16:50:43Z, 183 files).

## Files
| File | Contents |
|---|---|
| `RESULTS.md` | Post-run record and descriptive reading |
| `RESULTS_TABLE.md` | Solves and projected hours for every rule on every run set |
| `descriptive_stdout.txt` | First-edit calls of solved and unsolved runs; test runs per task |
| `whatif_stdout.txt`, `test_stdout.txt`, `freeze_stdout.txt` | Check results, unit tests and the freeze |

**Withheld** (task identifiers or harness-dependent code; see [DATA_AND_LICENSING.md](../../DATA_AND_LICENSING.md)), with
SHA-256:

| File | SHA-256 |
|---|---|
| `PLAN.md` (full plan and amendment, summarized above) | `25c86701d5b9ab73c6a21ffd4911f2d1a131da989b38ea702359e40aebfe85a2` |
| `FREEZE.json` (hashes of the 183 frozen files) | `56dfa43164d8612af0562a81c2dcb164e35fe3cc0effe033abae6e4b6b6e0ec7` |
| `whatif.py` | `5984cd4db8da9163e8cabc069c2da97afa5c1c0acc78ea7ca5e74f747dba9d35` |
| `test_whatif.py` | `48a96bccbe6f25620e7dcf8eb7dbc6d00ca599d30793fc7865f45b102fedfd86` |
| `freeze.py` | `a0a23da68d46aa4fa454a7598756765a792a8191d2dc1a8d00286283c8e48b1f` |
| `results.json` (per-rule results, including lost-solve task lists) | `5a754039aac4f792d9a2705865bd49407580ba6f2abc855390fa0c75e1706160` |
| `runs.json` (per-call records) | `3ba88d6bd1acf73578bd48cbcd6a26d0664215045f6a02fe7747c53c05868320` |
