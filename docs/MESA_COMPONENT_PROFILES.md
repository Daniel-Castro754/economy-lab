# Mesa Component Profiles — v1.8

Mesa is used as an agent orchestration/component technology, not as a second accounting authority.

## Components

### Activation
- `random`: AgentSet `shuffle_do`
- `fixed`: AgentSet `do`

### Household search
Controls where households shop after the consumption budget is decided:
- shopping sample size;
- probability of choosing the cheapest firm in the sample.

This deliberately complements HARK: HARK answers **how much** to consume/save; Mesa search answers **where** the consumption is allocated.

### Firm behavior
Controls behavioral intensity for:
- price adjustment;
- hiring;
- layoffs.

### Labor market
Controls the fraction of potential vacancy-worker matches that are actually realized each month.

## Authority rule

Mesa components may influence behavior and activation. They never create/edit deposits, loans, reserves or other financial positions directly. All realized transactions continue through Economy Lab's SFC ledger.

## Profile flow

`Mesa Lab -> isolated preview -> validated Profile -> Simulation Lab -> EconomyState/ledger`

The saved Profile stores inputs and preview output for auditability. The integrated simulator receives only a validated `scenario_patch`.
