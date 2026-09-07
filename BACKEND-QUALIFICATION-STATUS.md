# Backend qualification status — v2.13.1

The external-engine qualification infrastructure introduced in v2.7 remains active. The v2.11 runtime and package evidence for replay remains part of the baseline; v2.13.1 does not convert unavailable external engines into qualified ones.

## Build-container result

The build container used for this package has none of the optional external runtimes installed/configured, so its real qualification evidence is intentionally:

- Mesa: UNAVAILABLE
- HARK: UNAVAILABLE
- Dynare/Octave: UNAVAILABLE
- Minsky REST: UNAVAILABLE
- FAIL: 0
- false PASS: 0

The checked-in `examples/external-engine-qualification-current-runtime.json` and `.md` are historical build-container evidence. Their names predate the current script. Regenerate target-machine evidence with `scripts/validate-external-engines.ps1`; it writes timestamped JSON and Markdown reports under `validation-reports/`.

## Authority result

Native Economy Zero smoke validation passes the v2.11 backend contracts with:

- realized macro state → Economy Zero ABM;
- financial balances → Ledger/SFC;
- household decision policy → selected HARK/native policy;
- activation → selected Mesa/native runtime;
- Dynare → macro guidance only;
- Minsky → financial controls plus read-only reconciliation evidence, never balances.

The recorded regression-suite result (**189 passed and 2 optional skips**) is v2.11 build evidence, not a v2.13.1 external-engine requalification. v2.11 added coverage for canonical hashes, seeded Economy Zero replay, profile/data evidence, legacy migration, replay lineage, exact match, divergence and manifest tamper rejection.

## Release-machine action

Run `scripts/validate-external-engines.ps1 -StrictQualification` on the target Windows machine to produce current evidence; `QUALIFICAR-BACKEND.bat` remains a convenience launcher. Qualification is fully closed only when the engines intended for the distribution produce real `pass` evidence. Minsky reconciliation is intentionally read-only; a writable external-balance path is forbidden, not pending.
