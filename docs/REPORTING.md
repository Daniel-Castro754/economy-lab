# Reporting and charts — v1.4

The reporting layer is downstream from the economic kernel. It receives validated `SimulationResult` or `BatchExperimentResponse` objects and cannot mutate a simulation.

## UI charts

The desktop/web UI renders dependency-free SVG charts for:

- real GDP index;
- inflation, unemployment and policy rate;
- bank credit;
- batch experiment comparison.

## CSV

Simulation CSV exports the monthly time series. Batch CSV exports aggregate comparison rows.

## Excel (.xlsx)

The backend writes a standards-based OOXML workbook locally without requiring Excel or a cloud service. It creates multiple sheets so audit data is not flattened into one table.

Current simulation sheets can include:

1. Summary
2. Scenario
3. Monthly series
4. Sector balances
5. Godley stocks
6. Godley flows
7. Banks
8. Macro IRF
9. Coupling

Batch workbooks contain Summary, Comparison, Runs and Base Scenario.
