from __future__ import annotations

import json
import zipfile
from io import BytesIO

import pytest

from economy_lab.calibration import evaluate_calibration
from economy_lab.core.schemas import (
    CalibrationRequest,
    CalibrationTargetSpec,
    DataFetchRequest,
    EconomicObservation,
    EconomicSeriesResponse,
    ScenarioSpec,
)
from economy_lab.core.simulation import run_simulation
from economy_lab.data.service import fetch_economic_series
from economy_lab.reporting import calibration_xlsx_bytes


def test_bcb_connector_normalizes_and_caches(tmp_path, monkeypatch):
    monkeypatch.setenv("ECONOMY_LAB_DATA_CACHE", str(tmp_path))
    calls = []

    def fetcher(url: str, timeout: int):
        calls.append((url, timeout))
        return [{"data": "01/01/2026", "valor": "12,25"}, {"data": "02/01/2026", "valor": "12.50"}]

    query = DataFetchRequest(source="bcb_sgs", series_id="432", start_date="2026-01-01", end_date="2026-01-02")
    first = fetch_economic_series(query, fetcher=fetcher)
    assert first.cached is False
    assert [x.value for x in first.observations] == [12.25, 12.5]
    assert first.observations[0].date == "2026-01-01"
    assert "dataInicial=01%2F01%2F2026" in first.request_url
    second = fetch_economic_series(query, fetcher=lambda *_: (_ for _ in ()).throw(AssertionError("cache miss")))
    assert second.cached is True
    assert len(calls) == 1


def test_world_bank_connector_parses_json(tmp_path, monkeypatch):
    monkeypatch.setenv("ECONOMY_LAB_DATA_CACHE", str(tmp_path))

    def fetcher(url: str, timeout: int):
        return [
            {"page": 1, "pages": 1},
            [
                {"indicator": {"value": "GDP growth"}, "date": "2025", "value": 2.3},
                {"indicator": {"value": "GDP growth"}, "date": "2024", "value": 3.4},
            ],
        ]

    query = DataFetchRequest(source="world_bank", series_id="NY.GDP.MKTP.KD.ZG", source_options={"country": "BRA"})
    result = fetch_economic_series(query, fetcher=fetcher)
    assert result.title == "GDP growth"
    assert [o.date for o in result.observations] == ["2024-01-01", "2025-01-01"]


def test_ipeadata_connector_parses_odata(tmp_path, monkeypatch):
    monkeypatch.setenv("ECONOMY_LAB_DATA_CACHE", str(tmp_path))

    def fetcher(url: str, timeout: int):
        return {"value": [{"VALDATA": "2026-01-01T00:00:00", "VALVALOR": 4.2, "NIVNOME": "Brasil"}]}

    query = DataFetchRequest(source="ipeadata", series_id="TEST_SERIES")
    result = fetch_economic_series(query, fetcher=fetcher)
    assert result.observations[0].date == "2026-01-01"
    assert result.metadata["series_code"] == "TEST_SERIES"


def test_ibge_connector_walks_nested_series(tmp_path, monkeypatch):
    monkeypatch.setenv("ECONOMY_LAB_DATA_CACHE", str(tmp_path))

    def fetcher(url: str, timeout: int):
        return [{"variavel": "Teste", "unidade": "%", "resultados": [{"series": [{"serie": {"202601": "4,5", "202602": "4.7"}}]}]}]

    query = DataFetchRequest(source="ibge_sidra", series_id="9999", source_options={"periods": "-2", "variable": "1"})
    result = fetch_economic_series(query, fetcher=fetcher)
    assert result.title == "Teste"
    assert result.unit == "%"
    assert [o.value for o in result.observations] == [4.5, 4.7]


def _series(source: str, series_id: str, values: list[float]) -> EconomicSeriesResponse:
    return EconomicSeriesResponse(
        source=source,
        series_id=series_id,
        title=series_id,
        unit="%",
        frequency="monthly",
        fetched_at="2026-08-29T00:00:00+00:00",
        cached=False,
        request_url="https://example.invalid",
        metadata={},
        observations=[EconomicObservation(date=f"2026-{i+1:02d}-01", value=value) for i, value in enumerate(values)],
        warning="test",
    )


def test_calibration_compares_explicit_moments_and_suggests_initial_patch():
    scenario = ScenarioSpec(months=6, households=300, firms=20, banks=2, seed=11)
    result = run_simulation(scenario)
    request = CalibrationRequest(
        scenario=scenario,
        result=result,
        targets=[
            CalibrationTargetSpec(metric="inflation", statistic="last", series=_series("bcb_sgs", "433", [4.0, 4.5, 5.0])),
            CalibrationTargetSpec(metric="unemployment", statistic="last", series=_series("ibge_sidra", "x", [7.2, 7.1, 7.0])),
            CalibrationTargetSpec(metric="policy_rate", statistic="last", series=_series("bcb_sgs", "432", [10.0, 11.0, 12.0])),
        ],
    )
    report = evaluate_calibration(request)
    assert 0 <= report.score <= 100
    assert report.requires_review is True
    assert report.suggested_scenario_patch == {
        "initial_inflation": 5.0,
        "initial_unemployment": 7.0,
        "policy_rate": 12.0,
    }
    assert len(report.metrics) == 3


def test_calibration_xlsx_contains_audit_sheets():
    scenario = ScenarioSpec(months=3, households=200, firms=10, banks=2)
    result = run_simulation(scenario)
    request = CalibrationRequest(
        scenario=scenario,
        result=result,
        targets=[CalibrationTargetSpec(metric="inflation", statistic="last", series=_series("bcb_sgs", "433", [4.0]))],
    )
    report = evaluate_calibration(request)
    payload = calibration_xlsx_bytes(scenario, report)
    with zipfile.ZipFile(BytesIO(payload)) as workbook:
        xml = workbook.read("xl/workbook.xml").decode("utf-8")
        assert "Resumo calibração" in xml
        assert "Métricas" in xml
        assert "Patch sugerido" in xml
        assert "Cenário" in xml


def _dated_series(source: str, series_id: str, rows: list[tuple[str, float]], frequency: str = "monthly") -> EconomicSeriesResponse:
    return EconomicSeriesResponse(
        source=source,
        series_id=series_id,
        title=series_id,
        unit="%",
        frequency=frequency,
        fetched_at="2026-08-29T00:00:00+00:00",
        cached=False,
        request_url="https://example.invalid",
        metadata={},
        observations=[EconomicObservation(date=when, value=value) for when, value in rows],
        warning="test",
    )


def test_calibration_aligns_daily_real_series_to_monthly_simulation():
    scenario = ScenarioSpec(months=3, households=200, firms=10, banks=2, seed=4)
    result = run_simulation(scenario)
    # Daily observations collapse to monthly means; simulation months are explicitly anchored.
    real = _dated_series("bcb_sgs", "infl", [
        ("2026-01-05", result.series[0].inflation - 0.2),
        ("2026-01-20", result.series[0].inflation + 0.2),
        ("2026-02-10", result.series[1].inflation),
        ("2026-03-10", result.series[2].inflation),
    ], frequency="daily")
    request = CalibrationRequest(
        scenario=scenario,
        result=result,
        simulation_start_date="2026-01-01",
        targets=[CalibrationTargetSpec(
            metric="inflation", series=real, comparison_mode="aligned_path",
            alignment_frequency="monthly", aggregation="mean", weight=2,
        )],
    )
    report = evaluate_calibration(request)
    metric = report.metrics[0]
    assert metric.aligned_frequency == "monthly"
    assert metric.aligned_observations == 3
    assert metric.path_rmse == pytest.approx(0.0, abs=1e-9)
    assert metric.path_mae == pytest.approx(0.0, abs=1e-9)
    assert [point.period for point in metric.aligned_points] == ["2026-01", "2026-02", "2026-03"]


def test_calibration_multi_target_weighting_prefers_heavier_metric():
    scenario = ScenarioSpec(months=3, households=200, firms=10, banks=2, seed=5)
    result = run_simulation(scenario)
    inflation_real = _series("bcb_sgs", "infl", [result.series[-1].inflation + 1.0])
    unemployment_real = _series("ibge_sidra", "unemp", [result.series[-1].unemployment + 1.0])
    report = evaluate_calibration(CalibrationRequest(
        scenario=scenario,
        result=result,
        targets=[
            CalibrationTargetSpec(metric="inflation", statistic="last", series=inflation_real, weight=5),
            CalibrationTargetSpec(metric="unemployment", statistic="last", series=unemployment_real, weight=1),
        ],
    ))
    assert len(report.metrics) == 2
    assert report.metrics[0].weighted_loss == pytest.approx(5 * report.metrics[0].normalized_error ** 2)
    assert report.metrics[1].weighted_loss == pytest.approx(report.metrics[1].normalized_error ** 2)


def test_bounded_calibration_fit_improves_or_preserves_score(monkeypatch):
    from economy_lab.calibration.engine import fit_calibration
    from economy_lab.core.schemas import CalibrationFitRequest

    scenario = ScenarioSpec(months=2, households=100, firms=5, banks=1, seed=7, initial_inflation=8.0)
    # Use a deterministic synthetic objective so the test targets the bounded-search logic, not ABM noise.
    def fake_eval(request, candidate, targets=None):
        distance = abs(candidate.initial_inflation - 4.0)
        from economy_lab.core.schemas import CalibrationResponse
        return CalibrationResponse(
            engine="test", score=max(0.0, 100.0 - distance * 10.0), normalized_rmse=distance / 10.0,
            metrics=[], suggested_scenario_patch={}, requires_review=True, warning="test",
        )
    monkeypatch.setattr("economy_lab.calibration.engine._fit_evaluate", fake_eval)
    target = CalibrationTargetSpec(metric="inflation", series=_series("bcb_sgs", "433", [4.0]))
    fit = fit_calibration(CalibrationFitRequest(
        scenario=scenario, targets=[target], parameters=["initial_inflation"], max_evaluations=16, max_rounds=4,
    ))
    assert fit.best_score >= fit.baseline_score
    assert fit.evaluations <= 16
    assert fit.best_scenario_patch["initial_inflation"] < 8.0
    assert any(step.accepted and step.parameter == "initial_inflation" for step in fit.trace)


def test_calibration_xlsx_contains_aligned_and_fit_sheets(monkeypatch):
    from economy_lab.calibration.engine import fit_calibration
    from economy_lab.core.schemas import CalibrationFitRequest, CalibrationResponse

    scenario = ScenarioSpec(months=2, households=100, firms=5, banks=1, seed=8)
    result = run_simulation(scenario)
    real = _dated_series("bcb_sgs", "433", [
        ("2026-01-01", result.series[0].inflation),
        ("2026-02-01", result.series[1].inflation),
    ])
    request = CalibrationRequest(
        scenario=scenario, result=result, simulation_start_date="2026-01-01",
        targets=[CalibrationTargetSpec(metric="inflation", series=real, comparison_mode="aligned_path")],
    )
    report = evaluate_calibration(request)
    def fake_eval(req, candidate, targets=None):
        return CalibrationResponse(engine="test", score=90, normalized_rmse=.1, metrics=report.metrics, warning="test")
    monkeypatch.setattr("economy_lab.calibration.engine._fit_evaluate", fake_eval)
    fit = fit_calibration(CalibrationFitRequest(scenario=scenario, targets=request.targets, parameters=["policy_rate"], max_evaluations=4, max_rounds=1))
    payload = calibration_xlsx_bytes(scenario, report, fit)
    with zipfile.ZipFile(BytesIO(payload)) as workbook:
        xml = workbook.read("xl/workbook.xml").decode("utf-8")
        assert "Trajetórias alinhadas" in xml
        assert "Ajuste limitado" in xml
        assert "Traço otimização" in xml


def test_calibration_fit_train_validation_split(monkeypatch):
    from economy_lab.calibration.engine import fit_calibration
    from economy_lab.core.schemas import CalibrationFitRequest, CalibrationResponse

    scenario = ScenarioSpec(months=2, households=100, firms=5, banks=1)
    target = CalibrationTargetSpec(metric="inflation", series=_dated_series("bcb_sgs", "433", [
        ("2026-01-01", 4.0), ("2026-02-01", 4.1), ("2026-03-01", 4.2), ("2026-04-01", 4.3),
    ]))
    seen_lengths = []
    def fake_eval(request, candidate, targets=None):
        seen_lengths.append(len((targets or request.targets)[0].series.observations))
        return CalibrationResponse(engine="test", score=80, normalized_rmse=.2, metrics=[], warning="test")
    monkeypatch.setattr("economy_lab.calibration.engine._fit_evaluate", fake_eval)
    fit = fit_calibration(CalibrationFitRequest(
        scenario=scenario, targets=[target], parameters=["policy_rate"], max_evaluations=4, max_rounds=1,
        training_end_date="2026-02-28", validation_start_date="2026-03-01",
    ))
    assert fit.validation_score == 80
    assert 2 in seen_lengths


def test_calibration_aligns_monthly_simulation_to_quarterly_targets():
    scenario = ScenarioSpec(months=6, households=120, firms=6, banks=1, seed=14)
    result = run_simulation(scenario)
    q1 = sum(p.inflation for p in result.series[:3]) / 3
    q2 = sum(p.inflation for p in result.series[3:6]) / 3
    real = _dated_series("bcb_sgs", "q-infl", [("2026-03-31", q1), ("2026-06-30", q2)], frequency="quarterly")
    report = evaluate_calibration(CalibrationRequest(
        scenario=scenario, result=result, simulation_start_date="2026-01-01",
        targets=[CalibrationTargetSpec(metric="inflation", series=real, comparison_mode="aligned_path", alignment_frequency="quarterly", aggregation="mean")],
    ))
    metric = report.metrics[0]
    assert metric.aligned_observations == 2
    assert metric.path_rmse == pytest.approx(0.0, abs=1e-9)
