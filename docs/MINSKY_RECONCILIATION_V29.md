# v2.9 Minsky/Godley reconciliation and SFC final

## Contract

The Economy Lab Ledger/SFC is the only accounting authority. Minsky is an external dynamics and visualisation engine whose Godley cells may be compared with canonical Economy Lab values, but never imported as balances or posted as transactions.

Every reconciliation is tied to:

- the frozen `economy-lab-godley-v1.0` canonical payload;
- a human-readable template ID;
- the SHA-256 of one known `.mky` template;
- an explicit mapping from canonical cell to Minsky variable ID;
- absolute and relative tolerances;
- hashes of the canonical payload, mapping and observed snapshot.

## Cell mapping

Each mapping declares:

| Field | Meaning |
|---|---|
| `kind` | `stocks` or `flows` |
| `instrument` | Economy Lab Godley instrument, such as `deposits` |
| `sector` | one frozen SFC sector |
| `variable_id` | exact Minsky variable ID in the known template |
| `external_multiplier` | explicit sign/unit conversion into Economy Lab convention |
| `required` | whether a missing external observation fails the report |

Duplicate canonical cells and duplicate Minsky variable IDs are rejected. With full coverage enabled, every non-zero canonical Godley cell must be mapped.

## Outcomes

- `pass`: full required coverage, balanced canonical matrices and no drift outside tolerance;
- `partial`: drift-free comparison accepted with full coverage disabled, while all omissions remain listed;
- `fail`: drift, missing required observations, missing required coverage or an unbalanced canonical matrix.

The combined tolerance rule is:

`absolute_error <= absolute_tolerance + relative_tolerance * max(|expected|, |observed|)`

## Capture modes

`POST /api/v1/minsky/reconcile` supports:

1. `provided`: compares a supplied, immutable snapshot. This is appropriate for archived or offline Minsky evidence.
2. `live`: verifies the local `.mky` bytes against `template_sha256`, loads the model, optionally resets/steps it, and only calls Minsky getters for mapped variables.

No reconciliation function has access to `Ledger.post`, Minsky values are never copied into `EconomyState`, and the report explicitly records `accounting_authority=ledger_sfc`, `read_only=true` and `external_can_mutate_ledger=false`.

## Recommended workflow

1. Export the canonical final Godley matrix with `POST /api/v1/minsky/export`.
2. Build and review a complete mapping for the known `.mky` template.
3. Record the template SHA-256.
4. Run a provided or verified live reconciliation.
5. Archive the report IDs and hashes with the experiment evidence.

The live path cannot be fully qualified without Minsky and the real `.mky` template on the target Windows machine. The offline comparison, strict mapping validation and no-write boundary are covered by automated tests.
