# External Engine Validation Pack — v2.13.1

The validation pack answers a narrower question than the module status badges: **can this machine execute the exact external runtime path Economy Lab expects?**

## States

- `pass`: the engine is installed/configured and its real smoke test completed.
- `unavailable`: the engine is not installed or not configured. This is not an integration failure.
- `fail`: the engine appears installed/configured, but the expected Economy Lab integration failed.

## Smoke tests

### Mesa
Imports the installed Mesa package, executes a tiny Wealth Exchange model through `AgentSet.shuffle_do` and verifies wealth conservation.

### HARK / Econ-ARK
Solves a small `IndShockConsumerType`, obtains a consumption policy curve and verifies finite/bounded consumption and saving values.

### Dynare / GNU Octave
Detects `octave-cli` and the Dynare `matlab` folder, renders the built-in known `.mod` template, executes Dynare through Octave and parses the generated `*_results.mat` IRFs. Arbitrary user `.mod` code is not executed by this validation route.

### Minsky
Uses `MINSKY_REST_URL`, performs the existing handshake and calls REST introspection (`@list`). The validation smoke is read-only: it does not call `step`, `reset`, `load`, `save` or write variables.

## API

`POST /api/v1/validation/external-engines`

Example request:

```json
{
  "engines": ["mesa", "hark", "dynare", "minsky"],
  "smoke_tests": true,
  "dynare_timeout_seconds": 60
}
```

## Windows validation workflow

From the repository root, run:

```powershell
.\scripts\validate-external-engines.ps1
```

The script requires an installed Economy Lab backend in `backend\.venv` or another compatible Python environment that can import it. Use `-InstallPythonEngines` only when Mesa/HARK packages must also be installed in the selected backend environment. For strict release qualification, run `-StrictQualification`.

If Dynare is not auto-detected, set:

```powershell
$env:OCTAVE_EXECUTABLE = "C:\path\to\octave-cli.exe"
$env:DYNARE_MATLAB_PATH = "C:\dynare\7.1\matlab"
```

For Minsky:

```powershell
$env:MINSKY_REST_URL = "http://127.0.0.1:8000"
```

By default, the script writes both `validation-reports/external-engine-qualification-YYYYMMDD-HHMMSS.json` and `validation-reports/external-engine-qualification-YYYYMMDD-HHMMSS.md`. Use `-StrictQualification` when every requested engine must pass for release qualification.

## Release rule

A mocked unit test never counts as real external-engine validation. The progress tracker may credit the validation **infrastructure**, but the project must retain an explicit pending item until a Windows report contains real `pass` results for the engines intended for the release bundle.
