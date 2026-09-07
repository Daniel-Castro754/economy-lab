# v2.11 Reproducibility, Run Manifest and replay

## What is proven

Every new persisted simulation run receives four related identities:

- `scenario_hash`: canonical SHA-256 of the complete validated `ScenarioSpec`;
- `result_hash`: canonical SHA-256 of the complete `SimulationResult`;
- `experiment_hash`: canonical SHA-256 of scenario, runtime versions, profile evidence and data provenance;
- `manifest_hash`: canonical SHA-256 protecting the manifest itself.

Canonical JSON sorts mapping keys, rejects non-finite numbers and uses stable separators. Hashes are evidence of byte-equivalent canonical content, not evidence that the economic assumptions are empirically correct.

## Captured context

The v1.0 manifest records:

- Economy Lab and Python versions;
- operating system, machine and relevant package versions;
- scenario seed and selected engine trace;
- each applied profile ID, module, compatibility and hashes of its payload and scenario patch;
- explicit data source/series IDs, observation window, frequency, units and content hash.

`ScenarioSpec.data_provenance` is optional because many current scenarios are synthetic. If real observations influence a scenario, callers must include their provenance record; omitting it prevents the manifest from proving which dataset was used.

## Replay

`POST /api/v1/runs/{run_id}/replay` first verifies the stored manifest, scenario and result hashes. It then executes the immutable stored scenario, saves a new run with `replay_of_run_id` and compares both manifests.

- `matched`: scenario, experiment environment and result all match;
- `environment_changed`: result matches, but runtime versions changed;
- `diverged`: numerical result or another experiment identity component differs.

A replay never overwrites the source run. Runs created before v2.11 remain readable, but return HTTP 409 for verified replay because their original runtime/profile evidence was not captured. Inventing a manifest after the fact would create false assurance.

## Limits

Seeded native simulations are expected to replay exactly under the same captured environment. External Dynare/Octave, Mesa or HARK results can change after package/runtime upgrades or across platforms. The API reports that drift; it does not hide it with numerical tolerances in v1.0.

Replay is currently synchronous. Large runs should be treated carefully because the request remains open until verification finishes; asynchronous replay jobs are a future hardening option if production workloads require them.
