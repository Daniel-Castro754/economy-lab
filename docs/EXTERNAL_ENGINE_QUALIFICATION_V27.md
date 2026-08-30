# External Engine Qualification — v2.7

v2.7 is the first backend-completion milestone. It upgrades the old availability checker into release evidence for the four optional runtimes.

## Qualification stages

### Mesa
1. detect/import Mesa;
2. execute a small standalone `AgentSet/shuffle_do` model and verify wealth conservation;
3. execute a 2-month Economy Zero scenario with `activation_engine=mesa`;
4. require ledger + Godley stocks + Godley flows to remain balanced.

### HARK
1. detect/import Econ-ARK/HARK;
2. solve a real `IndShockConsumerType` policy curve;
3. verify finite/bounded consumption;
4. execute a 2-month Economy Zero scenario with `household_behavior=hark`;
5. require ledger + Godley invariants.

### Dynare / Octave
1. detect Octave and the Dynare `matlab` directory;
2. generate and execute the Economy Lab reference New-Keynesian `.mod`;
3. parse real `*_results.mat` / `oo_.irfs`;
4. execute a 1-month Economy Zero scenario with the real Dynare result attached;
5. require ledger + Godley invariants.

### Minsky
Minsky remains intentionally read-only in v2.7:
1. connect to `MINSKY_REST_URL`;
2. read `/minsky/@type` and `/minsky/t`;
3. read `/minsky/@list`;
4. never call `step`, `reset`, `load`, `save` or mutate a variable during qualification.

A controlled writable `.mky` reconciliation belongs to the later Minsky/SFC backend-freeze milestone.

## Evidence

Each report contains:
- report UUID;
- SHA-256 digest;
- Economy Lab version;
- OS/Python fingerprint;
- detected versions and paths;
- individual stage status and duration;
- compatibility warning if the observed Mesa/HARK/Dynare version differs from the pinned/target line;
- overall qualification status.

No secret environment-variable values are put in the top-level environment fingerprint. The report only states whether the relevant configuration variables are set. Engine-specific executable paths may appear because they are essential diagnostic evidence.

## Windows

From the package root, double-click `QUALIFICAR-BACKEND.bat`, or run:

```powershell
.\scripts\validate-external-engines.ps1 -StrictQualification
```

If Mesa/HARK are not installed yet:

```powershell
.\scripts\validate-external-engines.ps1 -InstallPythonEngines -StrictQualification
```

Optional explicit paths:

```powershell
.\scripts\validate-external-engines.ps1 `
  -OctaveExecutable "C:\...\octave-cli.exe" `
  -DynareMatlabPath "C:\dynare\7.1\matlab" `
  -MinskyRestUrl "http://127.0.0.1:8000" `
  -StrictQualification
```

Reports are written under `validation-reports/` as both JSON and Markdown.
