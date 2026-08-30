# Shocks and safe scenario compilation — v1.0

Economy Lab v1.0 accepts bounded, auditable shock schedules through `ScenarioSpec.shocks`.
Supported kinds are `fiscal_spending`, `productivity`, `cost_push`, `external_demand` and `import_cost`.
Each shock has a start month, duration and percentage magnitude. Overlapping shocks add together and are bounded before reaching agent behaviour.

The external sector is explicit in the SFC ledger. Imports transfer deposits from households to `rest_of_world`; exports transfer deposits from `rest_of_world` to firms. Godley stock/flow matrices therefore include a sixth sector and must still close by instrument.

`POST /api/v1/scenario/compile` is the first AI-facing contract. v1.0 ships a deterministic local Portuguese parser so the workflow works without an API key. It returns a reviewable `ScenarioSpec`; it never executes generated code and never writes directly to ledger accounts. Future LLM providers must pass through the same Pydantic validation contract before simulation.
