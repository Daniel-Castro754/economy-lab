# Batch experiments — v1.3

Economy Lab can sweep one validated scenario parameter across several values and repeat each point using deterministic seed increments.

Supported axes in v1.3:

- `policy_rate`
- `income_tax`
- `public_spending_change`
- `minimum_bank_capital_ratio`
- `target_reserve_ratio`

Each experiment is capped at 60 simulation runs. The cap is intentional: the native ABM can be large, Dynare may launch an external solver, and the desktop app should remain responsive and auditable.

For each point the engine records final GDP index, inflation, unemployment, defaults, bank credit, bank capital ratio, credit rationing and the three accounting invariants. Aggregates use population standard deviation.

DuckDB is optional. If installed through `pip install -e ".[analytics]"`, aggregation is executed in DuckDB. Otherwise the same output contract is computed with Python's standard `statistics` module.

Saved projects can persist immutable experiment payloads in SQLite schema v2. Experiments are distinct from ordinary runs: a batch result never rewrites an earlier run or the project's scenario.

Important: the comparison is a model experiment, not a causal estimate or forecast. A value producing higher simulated GDP does not imply that policy is optimal in reality.
