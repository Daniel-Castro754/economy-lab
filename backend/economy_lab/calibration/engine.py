from __future__ import annotations

from calendar import monthrange
from datetime import date
from math import sqrt
from statistics import mean, median, pstdev

from economy_lab.core.schemas import (
    CalibrationAlignedPoint,
    CalibrationFitRequest,
    CalibrationFitResponse,
    CalibrationFitStep,
    CalibrationMetricResult,
    CalibrationRequest,
    CalibrationResponse,
    CalibrationTargetSpec,
    ScenarioSpec,
)


def _stat(values: list[float], kind: str) -> float:
    if not values:
        raise ValueError("Calibration series has no values")
    if kind == "last":
        return float(values[-1])
    if kind == "mean":
        return float(mean(values))
    if kind == "median":
        return float(median(values))
    if kind == "std":
        return float(pstdev(values)) if len(values) > 1 else 0.0
    raise ValueError(f"Unsupported statistic: {kind}")


def _pct_changes(values: list[float]) -> list[float]:
    out: list[float] = []
    for a, b in zip(values, values[1:]):
        if abs(a) > 1e-12:
            out.append((b / a - 1.0) * 100.0)
    return out


def _simulation_values(result, metric: str) -> list[float]:
    points = result.series
    if metric == "inflation":
        return [float(p.inflation) for p in points]
    if metric == "unemployment":
        return [float(p.unemployment) for p in points]
    if metric == "policy_rate":
        return [float(p.policy_rate) for p in points]
    if metric == "gdp_growth":
        return _pct_changes([float(p.gdp_index) for p in points])
    if metric == "bank_credit_growth":
        return _pct_changes([float(p.bank_credit or 0.0) for p in points if p.bank_credit is not None])
    if metric == "bank_capital_ratio":
        return [float(p.bank_capital_ratio or 0.0) for p in points if p.bank_capital_ratio is not None]
    raise ValueError(f"Unsupported calibration metric: {metric}")


def _add_months(value: date, months: int) -> date:
    raw = value.year * 12 + value.month - 1 + months
    year, month0 = divmod(raw, 12)
    month = month0 + 1
    day = min(value.day, monthrange(year, month)[1])
    return date(year, month, day)


def _frequency_from_text(text: str) -> str:
    token = (text or "").strip().lower()
    if any(x in token for x in ("annual", "year", "anual", "ano")):
        return "annual"
    if any(x in token for x in ("quarter", "trimes", "quarterly")):
        return "quarterly"
    # Daily and weekly real series are intentionally collapsed to monthly because Economy Zero is monthly.
    return "monthly"


def _period_key(value: date, frequency: str) -> str:
    if frequency == "annual":
        return f"{value.year:04d}"
    if frequency == "quarterly":
        quarter = (value.month - 1) // 3 + 1
        return f"{value.year:04d}-Q{quarter}"
    return f"{value.year:04d}-{value.month:02d}"


def _aggregate_rows(rows: list[tuple[date, float]], frequency: str, aggregation: str) -> dict[str, float]:
    grouped: dict[str, list[float]] = {}
    for when, value in rows:
        grouped.setdefault(_period_key(when, frequency), []).append(float(value))
    out: dict[str, float] = {}
    for key, values in grouped.items():
        out[key] = float(values[-1] if aggregation == "last" else mean(values))
    return out


def _real_rows(target: CalibrationTargetSpec) -> list[tuple[date, float]]:
    rows: list[tuple[date, float]] = []
    for obs in target.series.observations:
        rows.append((date.fromisoformat(obs.date[:10]), float(obs.value)))
    rows.sort(key=lambda item: item[0])
    return rows


def _simulation_month_dates(request: CalibrationRequest) -> list[date]:
    months = len(request.result.series)
    if months <= 0:
        return []
    if request.simulation_start_date:
        start = date.fromisoformat(request.simulation_start_date)
    elif request.simulation_end_date:
        end = date.fromisoformat(request.simulation_end_date)
        start = _add_months(end.replace(day=1), -(months - 1))
    else:
        real_dates = [date.fromisoformat(obs.date[:10]) for target in request.targets for obs in target.series.observations]
        if real_dates:
            end = max(real_dates)
            start = _add_months(end.replace(day=1), -(months - 1))
        else:
            start = date(2000, 1, 1)
    return [_add_months(start.replace(day=1), index) for index in range(months)]


def _simulation_level_rows(request: CalibrationRequest, metric: str) -> list[tuple[date, float]]:
    dates = _simulation_month_dates(request)
    points = request.result.series
    if len(dates) != len(points):
        raise ValueError("Simulation date alignment failed")
    if metric == "inflation":
        return list(zip(dates, [float(p.inflation) for p in points]))
    if metric == "unemployment":
        return list(zip(dates, [float(p.unemployment) for p in points]))
    if metric == "policy_rate":
        return list(zip(dates, [float(p.policy_rate) for p in points]))
    if metric == "bank_capital_ratio":
        return list(zip(dates, [float(p.bank_capital_ratio or 0.0) for p in points]))
    if metric == "gdp_growth":
        return list(zip(dates, [float(p.gdp_index) for p in points]))
    if metric == "bank_credit_growth":
        return list(zip(dates, [float(p.bank_credit or 0.0) for p in points]))
    raise ValueError(f"Unsupported calibration metric: {metric}")


def _growth_by_period(rows: list[tuple[date, float]], frequency: str) -> dict[str, float]:
    # Use period-end levels. For the first period, use the first observation in that period as the base;
    # subsequent periods use the previous period end. This preserves an interpretable growth rate even
    # when the simulation horizon contains only one annual bucket.
    grouped: dict[str, list[tuple[date, float]]] = {}
    for when, value in rows:
        grouped.setdefault(_period_key(when, frequency), []).append((when, value))
    keys = sorted(grouped)
    result: dict[str, float] = {}
    previous_end: float | None = None
    for key in keys:
        observations = sorted(grouped[key], key=lambda item: item[0])
        first = observations[0][1]
        end = observations[-1][1]
        base = previous_end if previous_end is not None else first
        if abs(base) > 1e-12:
            result[key] = (end / base - 1.0) * 100.0
        previous_end = end
    return result


def _aligned_metric(request: CalibrationRequest, target: CalibrationTargetSpec) -> tuple[list[CalibrationAlignedPoint], str]:
    frequency = target.alignment_frequency
    if frequency == "auto":
        frequency = _frequency_from_text(target.series.frequency)
    real = _aggregate_rows(_real_rows(target), frequency, target.aggregation)
    sim_rows = _simulation_level_rows(request, target.metric)
    if target.metric in {"gdp_growth", "bank_credit_growth"}:
        simulated = _growth_by_period(sim_rows, frequency)
    else:
        simulated = _aggregate_rows(sim_rows, frequency, target.aggregation)
    periods = sorted(set(real).intersection(simulated))
    if not periods:
        raise ValueError(
            f"No overlapping {frequency} periods for {target.metric}. Set simulation_start_date/end_date or use moment comparison."
        )
    return [
        CalibrationAlignedPoint(
            period=period,
            real_value=real[period],
            simulated_value=simulated[period],
            error=simulated[period] - real[period],
        )
        for period in periods
    ], frequency


def evaluate_calibration(request: CalibrationRequest) -> CalibrationResponse:
    items: list[CalibrationMetricResult] = []
    total_weight = 0.0
    total_loss = 0.0
    suggested_patch: dict[str, float] = {}
    for target in request.targets:
        real_values = [float(obs.value) for obs in target.series.observations]
        sim_values = _simulation_values(request.result, target.metric)
        if target.comparison_mode == "aligned_path":
            aligned, frequency = _aligned_metric(request, target)
            errors = [point.error for point in aligned]
            real_aligned = [point.real_value for point in aligned]
            sim_aligned = [point.simulated_value for point in aligned]
            mae = mean(abs(value) for value in errors)
            path_rmse = sqrt(mean(value * value for value in errors))
            real = mean(real_aligned)
            sim = mean(sim_aligned)
            error = mean(errors)
            denom = max(mean(abs(value) for value in real_aligned), target.scale_floor)
            normalized = path_rmse / denom
            aligned_count = len(aligned)
        else:
            aligned = []
            frequency = None
            mae = None
            path_rmse = None
            real = _stat(real_values, target.statistic)
            sim = _stat(sim_values, target.statistic)
            error = sim - real
            denom = max(abs(real), target.scale_floor)
            normalized = abs(error) / denom
            aligned_count = 0
        weighted = target.weight * normalized * normalized
        total_weight += target.weight
        total_loss += weighted
        items.append(CalibrationMetricResult(
            metric=target.metric,
            statistic=target.statistic,
            source=target.series.source,
            series_id=target.series.series_id,
            real_value=real,
            simulated_value=sim,
            error=error,
            normalized_error=normalized,
            weight=target.weight,
            weighted_loss=weighted,
            real_observations=len(real_values),
            simulated_observations=len(sim_values),
            comparison_mode=target.comparison_mode,
            aligned_frequency=frequency,
            aligned_observations=aligned_count,
            path_mae=mae,
            path_rmse=path_rmse,
            aligned_points=aligned,
        ))
        # Keep automatic patches conservative: only current-condition levels and only for moment/last targets.
        if target.comparison_mode == "moment" and target.statistic == "last":
            if target.metric == "inflation":
                suggested_patch["initial_inflation"] = real
            elif target.metric == "unemployment":
                suggested_patch["initial_unemployment"] = real
            elif target.metric == "policy_rate":
                suggested_patch["policy_rate"] = real
    rmse = sqrt(total_loss / max(total_weight, 1e-12))
    score = max(0.0, min(100.0, 100.0 / (1.0 + rmse)))
    return CalibrationResponse(
        engine="economy-lab-calibration-v2.6",
        score=score,
        normalized_rmse=rmse,
        metrics=items,
        suggested_scenario_patch=suggested_patch,
        requires_review=True,
        warning=(
            "v2.6 supports multi-target moment and frequency-aligned path comparisons. "
            "Suggested initial-condition patches and bounded fitting remain review-only; structural DSGE/HARK parameters are not estimated automatically."
        ),
    )


def _clip_targets(targets: list[CalibrationTargetSpec], *, end_date: str | None = None, start_date: str | None = None) -> list[CalibrationTargetSpec]:
    clipped: list[CalibrationTargetSpec] = []
    start = date.fromisoformat(start_date) if start_date else None
    end = date.fromisoformat(end_date) if end_date else None
    for target in targets:
        observations = []
        for obs in target.series.observations:
            when = date.fromisoformat(obs.date[:10])
            if start and when < start:
                continue
            if end and when > end:
                continue
            observations.append(obs)
        if not observations:
            raise ValueError(f"No observations remain for {target.metric} after train/validation split")
        clipped.append(target.model_copy(update={
            "series": target.series.model_copy(update={"observations": observations})
        }))
    return clipped


_PARAMETER_RULES: dict[str, tuple[float, float, float]] = {
    "initial_inflation": (-20.0, 100.0, 0.75),
    "initial_unemployment": (0.0, 100.0, 0.75),
    "policy_rate": (-10.0, 100.0, 0.75),
    "public_spending_change": (-50.0, 100.0, 2.0),
    "minimum_bank_capital_ratio": (0.0, 30.0, 0.75),
    "target_reserve_ratio": (0.0, 100.0, 1.5),
    "labor_matching_efficiency": (0.0, 1.0, 0.08),
}


def _fit_evaluate(request: CalibrationFitRequest, scenario: ScenarioSpec, *, targets: list[CalibrationTargetSpec] | None = None) -> CalibrationResponse:
    # Late import avoids making the calibration package part of simulation module import initialization.
    from economy_lab.core.simulation import run_simulation

    result = run_simulation(scenario)
    calibration_request = CalibrationRequest(
        scenario=scenario,
        result=result,
        targets=targets or request.targets,
        simulation_start_date=request.simulation_start_date,
        simulation_end_date=request.simulation_end_date,
    )
    return evaluate_calibration(calibration_request)


def fit_calibration(request: CalibrationFitRequest) -> CalibrationFitResponse:
    current = request.scenario.model_copy(deep=True)
    training_targets = _clip_targets(request.targets, end_date=request.training_end_date) if request.training_end_date else request.targets
    validation_targets = _clip_targets(request.targets, start_date=request.validation_start_date) if request.validation_start_date else None
    baseline = _fit_evaluate(request, current, targets=training_targets)
    best_report = baseline
    best_score = baseline.score
    trace = [CalibrationFitStep(evaluation=1, round=0, parameter="baseline", score=best_score, accepted=True)]
    evaluations = 1
    steps = {parameter: _PARAMETER_RULES[parameter][2] for parameter in request.parameters}
    rounds_completed = 0
    converged = False

    for round_index in range(1, request.max_rounds + 1):
        rounds_completed = round_index
        improved_this_round = False
        for parameter in request.parameters:
            if evaluations >= request.max_evaluations:
                break
            lower, upper, _ = _PARAMETER_RULES[parameter]
            base_value = float(getattr(current, parameter))
            parameter_best = best_score
            accepted_value: float | None = None
            accepted_report: CalibrationResponse | None = None
            for direction in (-1.0, 1.0):
                if evaluations >= request.max_evaluations:
                    break
                candidate_value = max(lower, min(upper, base_value + direction * steps[parameter]))
                if abs(candidate_value - base_value) < 1e-12:
                    continue
                candidate = current.model_copy(update={parameter: candidate_value})
                report = _fit_evaluate(request, candidate, targets=training_targets)
                evaluations += 1
                accepted = report.score >= parameter_best + request.minimum_score_improvement
                trace.append(CalibrationFitStep(
                    evaluation=evaluations,
                    round=round_index,
                    parameter=parameter,
                    candidate_value=candidate_value,
                    score=report.score,
                    accepted=accepted,
                ))
                if accepted:
                    parameter_best = report.score
                    accepted_value = candidate_value
                    accepted_report = report
            if accepted_value is not None and accepted_report is not None:
                current = current.model_copy(update={parameter: accepted_value})
                best_score = parameter_best
                best_report = accepted_report
                improved_this_round = True
            if evaluations >= request.max_evaluations:
                break
        if not improved_this_round:
            for parameter in steps:
                steps[parameter] *= 0.5
            if max(steps.values(), default=0.0) < 0.02:
                converged = True
                break
        if evaluations >= request.max_evaluations:
            break

    patch = {
        parameter: float(getattr(current, parameter))
        for parameter in request.parameters
        if abs(float(getattr(current, parameter)) - float(getattr(request.scenario, parameter))) > 1e-12
    }
    validation_report = _fit_evaluate(request, current, targets=validation_targets) if validation_targets else None
    return CalibrationFitResponse(
        baseline_score=baseline.score,
        best_score=best_score,
        evaluations=evaluations,
        rounds_completed=rounds_completed,
        converged=converged,
        parameters=request.parameters,
        best_scenario_patch=patch,
        final_calibration=best_report,
        validation_score=validation_report.score if validation_report else None,
        validation_calibration=validation_report,
        trace=trace,
        requires_review=True,
        warning=(
            "Bounded coordinate search over approved reduced-form/initial-condition parameters only. "
            "When train/validation dates are supplied, only the training slice guides the search and the held-out slice is scored afterward. "
            "The best patch is a numerical proposal, not an econometric estimate, and must be reviewed before application."
        ),
    )
