# Standalone Labs — v1.5

Economy Lab Hub separates external technologies into explicit laboratories. A standalone lab never mutates the Simulation Lab automatically.

## Dynare Lab

- Generates the audited built-in New-Keynesian `.mod` template even when Dynare is not installed.
- When Dynare + GNU Octave are available, runs a monetary shock and returns IRFs for output gap, inflation and policy rate.
- Arbitrary user-supplied `.mod` code is not executed.

Contracts:
- `POST /api/v1/labs/dynare/template`
- `POST /api/v1/labs/dynare/run`

## Minsky Lab

- Uses the configured Minsky REST process independently.
- Supports root/object introspection (`@list`, `@signature`), `step`, `reset`, and explicit variable reads/writes.
- It does not replace Economy Lab's accounting ledger.

Contract:
- `POST /api/v1/labs/minsky/command`

## Mesa Lab

- Runs a standalone wealth-exchange Agent-Based Model with Mesa `AgentSet` activation.
- Tracks Gini, zero-wealth share and total wealth conservation through time.
- This model is educational and is not calibrated as a national economy.

Contract:
- `POST /api/v1/labs/mesa/run`

## HARK Lab

- Solves an `IndShockConsumerType` consumption/saving problem.
- Samples the policy function `c(m)` into a portable curve of market resources, consumption and saving.
- The lab does not move money in the SFC ledger.

Contract:
- `POST /api/v1/labs/hark/run`

## Integration rule

Standalone labs produce reports. Moving a result into a Simulation Lab scenario must be an explicit user action. This avoids silent cross-module mutation and keeps experiments reproducible.

## Future external API modules

The same registry can host data/service connectors such as BCB, IBGE, World Bank, FRED, IMF or OECD. Each connector should declare status, capabilities, routes and provenance, and should remain separable from the simulation kernel.
