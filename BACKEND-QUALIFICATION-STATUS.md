# Backend qualification status — v2.11

The external-engine qualification infrastructure introduced in v2.7 remains active. v2.11 records the runtime and package evidence needed to identify whether a replay used the same environment.

## Build-container result

The build container used for this package has none of the optional external runtimes installed/configured, so its real qualification evidence is intentionally:

- Mesa: UNAVAILABLE
- HARK: UNAVAILABLE
- Dynare/Octave: UNAVAILABLE
- Minsky REST: UNAVAILABLE
- FAIL: 0
- false PASS: 0

See `examples/external-engine-qualification-current-runtime.json` and `.md`; regenerate them with the v2.11 qualification script on the target Windows machine after the initial project is complete, as agreed for this build sequence.

## Authority result

Native Economy Zero smoke validation passes the v2.11 backend contracts with:

- realized macro state → Economy Zero ABM;
- financial balances → Ledger/SFC;
- household decision policy → selected HARK/native policy;
- activation → selected Mesa/native runtime;
- Dynare → macro guidance only;
- Minsky → financial controls plus read-only reconciliation evidence, never balances.

The packaged regression suite reports **189 passed and 2 optional skips** in this build environment. v2.11 adds coverage for canonical hashes, seeded Economy Zero replay, profile/data evidence, legacy migration, replay lineage, exact match, divergence and manifest tamper rejection.

## Release-machine action

After the initial project is complete, run `QUALIFICAR-BACKEND.bat` on the target Windows machine. External-engine qualification is considered fully closed only after the installed engines produce the expected PASS evidence. Minsky reconciliation is intentionally read-only; a writable external-balance path is forbidden, not pending.
