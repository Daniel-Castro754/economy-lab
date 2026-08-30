from __future__ import annotations

from collections import defaultdict
from statistics import mean, pstdev
from time import perf_counter
from typing import Iterable

from pydantic import ValidationError

from economy_lab.core.schemas import (
    BatchAggregate,
    BatchExperimentRequest,
    BatchExperimentResponse,
    BatchRunPoint,
    ScenarioSpec,
)
from economy_lab.core.simulation import run_simulation


def _scenario_for(base: ScenarioSpec, axis: str, value: float, seed: int) -> ScenarioSpec:
    try:
        return ScenarioSpec.model_validate({**base.model_dump(mode="python"), axis: value, "seed": seed})
    except ValidationError as exc:
        raise ValueError(f"Invalid value {value!r} for batch axis {axis}: {exc}") from exc


def _python_aggregates(points: Iterable[BatchRunPoint]) -> list[BatchAggregate]:
    grouped: dict[float, list[BatchRunPoint]] = defaultdict(list)
    for point in points:
        grouped[point.axis_value].append(point)
    aggregates: list[BatchAggregate] = []
    for axis_value in sorted(grouped):
        rows = grouped[axis_value]
        def avg(attr: str) -> float:
            return float(mean(float(getattr(r, attr)) for r in rows))
        def sd(attr: str) -> float:
            vals = [float(getattr(r, attr)) for r in rows]
            return float(pstdev(vals)) if len(vals) > 1 else 0.0
        aggregates.append(BatchAggregate(
            axis_value=axis_value,
            runs=len(rows),
            mean_gdp_index=avg("final_gdp_index"),
            std_gdp_index=sd("final_gdp_index"),
            mean_inflation=avg("final_inflation"),
            std_inflation=sd("final_inflation"),
            mean_unemployment=avg("final_unemployment"),
            std_unemployment=sd("final_unemployment"),
            mean_defaults=avg("cumulative_defaults"),
            mean_bank_credit=avg("final_bank_credit"),
            mean_bank_capital_ratio=avg("final_bank_capital_ratio"),
            mean_credit_rationed=avg("cumulative_credit_rationed"),
            all_accounting_balanced=all(
                r.ledger_balanced and r.godley_stocks_balanced and r.godley_flows_balanced
                for r in rows
            ),
        ))
    return aggregates


def _duckdb_aggregates(points: list[BatchRunPoint]) -> list[BatchAggregate] | None:
    try:
        import duckdb  # type: ignore
    except Exception:
        return None
    rows = [p.model_dump(mode="python") for p in points]
    connection = duckdb.connect(database=":memory:")
    try:
        connection.execute("""
            CREATE TABLE runs(
              axis_value DOUBLE, repetition INTEGER, seed BIGINT, duration_ms DOUBLE,
              final_gdp_index DOUBLE, final_inflation DOUBLE, final_unemployment DOUBLE,
              cumulative_defaults INTEGER, final_bank_credit DOUBLE,
              final_bank_capital_ratio DOUBLE, cumulative_credit_rationed DOUBLE,
              ledger_balanced BOOLEAN, godley_stocks_balanced BOOLEAN, godley_flows_balanced BOOLEAN
            )
        """)
        connection.executemany(
            "INSERT INTO runs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [tuple(row[k] for k in (
                "axis_value","repetition","seed","duration_ms","final_gdp_index","final_inflation",
                "final_unemployment","cumulative_defaults","final_bank_credit","final_bank_capital_ratio",
                "cumulative_credit_rationed","ledger_balanced","godley_stocks_balanced","godley_flows_balanced"
            )) for row in rows],
        )
        result = connection.execute("""
            SELECT axis_value, count(*) AS runs,
                   avg(final_gdp_index), coalesce(stddev_pop(final_gdp_index),0),
                   avg(final_inflation), coalesce(stddev_pop(final_inflation),0),
                   avg(final_unemployment), coalesce(stddev_pop(final_unemployment),0),
                   avg(cumulative_defaults), avg(final_bank_credit), avg(final_bank_capital_ratio),
                   avg(cumulative_credit_rationed), bool_and(ledger_balanced AND godley_stocks_balanced AND godley_flows_balanced)
            FROM runs GROUP BY axis_value ORDER BY axis_value
        """).fetchall()
        return [BatchAggregate(
            axis_value=float(r[0]), runs=int(r[1]), mean_gdp_index=float(r[2]), std_gdp_index=float(r[3]),
            mean_inflation=float(r[4]), std_inflation=float(r[5]), mean_unemployment=float(r[6]),
            std_unemployment=float(r[7]), mean_defaults=float(r[8]), mean_bank_credit=float(r[9]),
            mean_bank_capital_ratio=float(r[10]), mean_credit_rationed=float(r[11]),
            all_accounting_balanced=bool(r[12]),
        ) for r in result]
    finally:
        connection.close()


def run_batch_experiment(request: BatchExperimentRequest) -> BatchExperimentResponse:
    started = perf_counter()
    points: list[BatchRunPoint] = []
    for value in request.values:
        for repetition in range(request.repetitions):
            seed = request.base.seed + repetition * request.seed_step
            spec = _scenario_for(request.base, request.axis, float(value), seed)
            run_started = perf_counter()
            result = run_simulation(spec)
            run_ms = (perf_counter() - run_started) * 1000.0
            s = result.summary
            points.append(BatchRunPoint(
                axis_value=float(value), repetition=repetition + 1, seed=seed, duration_ms=run_ms,
                final_gdp_index=s.final_gdp_index, final_inflation=s.final_inflation,
                final_unemployment=s.final_unemployment, cumulative_defaults=s.cumulative_defaults,
                final_bank_credit=s.final_bank_credit, final_bank_capital_ratio=s.final_bank_capital_ratio,
                cumulative_credit_rationed=s.cumulative_credit_rationed,
                ledger_balanced=s.ledger_balanced, godley_stocks_balanced=s.godley_stocks_balanced,
                godley_flows_balanced=s.godley_flows_balanced,
            ))
    aggregates = _duckdb_aggregates(points)
    analytics_engine = "duckdb" if aggregates is not None else "python-statistics"
    if aggregates is None:
        aggregates = _python_aggregates(points)
    return BatchExperimentResponse(
        analytics_engine=analytics_engine, axis=request.axis, values=[float(v) for v in request.values],
        repetitions=request.repetitions, total_runs=len(points),
        duration_ms=(perf_counter() - started) * 1000.0, base_scenario=request.base,
        aggregates=aggregates, runs=points,
        warning=("Experimental comparative analysis. Differences reflect this model and its assumptions; "
                 "they are not causal estimates or forecasts."),
    )
