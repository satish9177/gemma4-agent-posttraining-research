# Amendment 1 to the Tier A mining-pilot preregistration

*Made 2026-10-28, after 2 of 150 candidates had completed. It changes no selection, validation, classification or
analysis rule. Frozen in `AMENDMENT_1_FREEZE.json`.*

## Change

In `validate_pilot.py`, the low-disk guard no longer runs `docker container prune -f`. When free disk is below 6 GB it
now only waits (up to 30 minutes) and then stops starting new candidates, as before.

## Why

On the machine running the pilot, the prune command would also have deleted stopped containers that belong to other,
unrelated projects. The pilot removes each of its own containers by name after every candidate, so the prune served no
purpose for the pilot. The guard had not triggered: free disk was about 16 GB.

## Effect on the run

- **Candidates already finished (P001, P002):** their results are kept unchanged. The amended line cannot have affected
  them, because the guard never triggered.
- **Candidates in progress (P003–P005):** their runs were stopped before any result was written and their partial logs
  were deleted. They are re-run from scratch with `--resume`, which skips only candidates that already have a result.
- **Everything else:** the selection, preparation data, recipes, stages, timeouts and analysis are unchanged.
  `PILOT_FREEZE.json` now differs from the files only in `validate_pilot.py`; the amended file is hashed in
  `AMENDMENT_1_FREEZE.json`.
