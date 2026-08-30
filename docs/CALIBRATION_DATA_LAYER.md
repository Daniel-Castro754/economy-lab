# Calibration/Data Layer — v2.1

## Goal

External data is evidence, not authority over the simulation kernel. v2.1 introduces a normalized series contract and explicit calibration targets so users can compare simulated outcomes with observed series without silently rewriting structural parameters.

## Supported adapters

- `bcb_sgs`: Banco Central do Brasil SGS series.
- `ibge_sidra`: IBGE API v3 for aggregated data that feeds SIDRA.
- `world_bank`: World Bank Indicators API v2.
- `ipeadata`: Ipeadata OData `ValoresSerie` endpoint.

Every adapter returns the same shape:

```text
EconomicSeries
├── source
├── series_id
├── title
├── unit
├── frequency
├── observations[] { date, value }
├── metadata
├── request_url
└── fetched_at
```

## Local cache

Successful fetches are stored under `~/.economy-lab/data-cache` by default. Set `ECONOMY_LAB_DATA_CACHE` to choose another path. The cache key excludes timeout/refresh flags but includes the source query itself.

## Calibration targets

v2.1 can compare:

- inflation;
- unemployment;
- policy rate;
- GDP growth;
- bank-credit growth;
- bank-capital ratio.

Available moments are `last`, `mean`, `median` and `std`. Each target has a weight and a normalization floor.

The reported score is a human-readable transformation of weighted normalized RMSE. It is useful for comparing configurations using the same targets; it is **not** a statistical goodness-of-fit test.

## Authority rule

Data never writes directly to the ledger or agent state. The only automatic suggestions in v2.1 are reviewable initial-condition patches for inflation, unemployment and policy rate when the chosen target moment is the latest observation.

Structural estimation (Taylor-rule coefficients, HARK preferences, ABM behavior, SFC parameters) remains out of scope until an explicit estimation method and identification strategy are implemented.
