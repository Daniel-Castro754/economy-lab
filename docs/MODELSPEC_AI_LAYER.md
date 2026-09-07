# ModelSpec + safe AI layer — v2.2

## Goal

v2.2 separates **economic model planning** from **simulation execution**. A provider (deterministic parser today, LLM later) may propose a declarative `ModelSpec`, but cannot write Python, shell commands, Dynare source, SQL or ledger transactions.

```text
Natural language / provider JSON
            ↓
        ModelSpec candidate
            ↓
  strict schema + security validation
            ↓
   explicit support-gap analysis
            ↓
       ScenarioSpec compiler
            ↓
       human review/apply
            ↓
       Simulation Lab
```

## ModelSpec

The contract contains only declarative fields:

- horizon and population;
- engine plan (native/Mesa, heuristic/HARK, native/Minsky Profile, off/Dynare);
- enabled markets;
- policy initial conditions;
- broad structural traits;
- economic shocks;
- HARK heterogeneity controls;
- requested capabilities, recommended modules and explicit assumptions.

Every ModelSpec nested model uses `extra="forbid"`. The provider gateway additionally rejects executable-looking fields such as `code`, `python_code`, `script`, `shell`, `command`, `sql` and `mod_source` before Pydantic validation.

## Support-gap report

Compiling a ModelSpec produces a `ModelCompilationReport` with three categories:

1. **applied fields** — mapped directly to ScenarioSpec;
2. **partial features** — represented only by a proxy/approximation;
3. **unsupported features** — preserved as an explicit gap rather than silently ignored.

Example: `commodity_exporter` enables the existing external-sector mechanics, but an explicit commodity production sector is reported as unsupported until sectoral production exists.

## Provider abstraction

`ModelCandidateProvider` is a protocol. v2.2 ships `LocalRuleModelProvider` so the full safety/validation flow works offline without an API key. A future LLM adapter must return a JSON-compatible candidate and pass exactly the same `validate_model_candidate()` gate.

There is deliberately **no provider → kernel path**.

## API

```text
GET  /api/v1/model/providers
POST /api/v1/model/compile
POST /api/v1/model/validate
POST /api/v1/model/to-scenario
```

- `/model/compile`: prompt → validated ModelSpec + compiled ScenarioSpec + gap report.
- `/model/validate`: validates JSON from any future provider/LLM.
- `/model/to-scenario`: recompiles an edited validated ModelSpec.

No endpoint executes a simulation directly from raw provider output.

## Known limitations

- Local natural-language planning is rule based, not an LLM.
- Structural traits such as commodity specialization and banking concentration are partially represented because Economy Zero is not yet a sectoral input-output model.
- ModelSpec does not estimate structural parameters from data.
- Profiles are referenced declaratively but are not automatically selected by semantic similarity in v2.2.
