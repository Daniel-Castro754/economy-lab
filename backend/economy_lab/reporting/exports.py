from __future__ import annotations

import csv
import io
import json
import math
import re
import zipfile
from dataclasses import asdict, is_dataclass
from typing import Any, Iterable
from xml.sax.saxutils import escape

from economy_lab.core.schemas import BatchExperimentResponse, ScenarioSpec, SimulationResult
from economy_lab.simple.models import SimpleRunResult


def _plain(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="python")
    if is_dataclass(value):
        return asdict(value)
    return value


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def _csv_bytes(headers: list[str], rows: Iterable[Iterable[Any]]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(headers)
    for row in rows:
        writer.writerow([_stringify(v) for v in row])
    return stream.getvalue().encode("utf-8-sig")


def simulation_csv_bytes(result: SimulationResult) -> bytes:
    points = [point.model_dump(mode="python") for point in result.series]
    if not points:
        return _csv_bytes([], [])
    headers = list(points[0].keys())
    return _csv_bytes(headers, ([row.get(key) for key in headers] for row in points))


def batch_csv_bytes(result: BatchExperimentResponse) -> bytes:
    rows = [item.model_dump(mode="python") for item in result.aggregates]
    if not rows:
        return _csv_bytes([], [])
    headers = list(rows[0].keys())
    return _csv_bytes(headers, ([row.get(key) for key in headers] for row in rows))


def _col_name(index: int) -> str:
    name = ""
    index += 1
    while index:
        index, rem = divmod(index - 1, 26)
        name = chr(65 + rem) + name
    return name


def _sheet_name(name: str, used: set[str]) -> str:
    safe = re.sub(r"[\\/*?:\[\]]", "-", name).strip()[:31] or "Sheet"
    base = safe
    counter = 2
    while safe in used:
        suffix = f" {counter}"
        safe = (base[: 31 - len(suffix)] + suffix)
        counter += 1
    used.add(safe)
    return safe


def _cell_xml(ref: str, value: Any, header: bool = False) -> str:
    style = ' s="1"' if header else ""
    if value is None:
        return f'<c r="{ref}"{style}/>'
    if isinstance(value, bool):
        return f'<c r="{ref}" t="b"{style}><v>{1 if value else 0}</v></c>'
    if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value)):
        return f'<c r="{ref}"{style}><v>{value}</v></c>'
    text = escape(_stringify(value))
    preserve = ' xml:space="preserve"' if text != text.strip() else ""
    return f'<c r="{ref}" t="inlineStr"{style}><is><t{preserve}>{text}</t></is></c>'


def _worksheet_xml(rows: list[list[Any]], freeze_header: bool = True) -> str:
    max_cols = max((len(row) for row in rows), default=1)
    widths: list[float] = []
    for col in range(max_cols):
        width = 10
        for row in rows[:250]:
            if col < len(row):
                width = max(width, min(42, len(_stringify(row[col])) + 2))
        widths.append(float(width))
    cols = "".join(
        f'<col min="{idx+1}" max="{idx+1}" width="{width}" customWidth="1"/>'
        for idx, width in enumerate(widths)
    )
    sheet_rows = []
    for r_index, row in enumerate(rows, start=1):
        cells = "".join(
            _cell_xml(f"{_col_name(c_index)}{r_index}", value, header=(r_index == 1))
            for c_index, value in enumerate(row)
        )
        sheet_rows.append(f'<row r="{r_index}">{cells}</row>')
    pane = '<pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/>' if freeze_header and len(rows) > 1 else ""
    auto_filter = ""
    if rows and max_cols > 1:
        auto_filter = f'<autoFilter ref="A1:{_col_name(max_cols-1)}{len(rows)}"/>'
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<sheetViews><sheetView workbookViewId="0">{pane}</sheetView></sheetViews>'
        f'<cols>{cols}</cols><sheetData>{"".join(sheet_rows)}</sheetData>{auto_filter}'
        '</worksheet>'
    )


def _styles_xml() -> str:
    return '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><color rgb="FFFFFFFF"/><sz val="11"/><name val="Calibri"/></font></fonts>
  <fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF1F4E78"/><bgColor indexed="64"/></patternFill></fill></fills>
  <borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>
  <cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
  <cellXfs count="2"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1"/></cellXfs>
  <cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
</styleSheet>'''


def _xlsx_bytes(sheets: list[tuple[str, list[list[Any]]]]) -> bytes:
    used: set[str] = set()
    normalized = [(_sheet_name(name, used), rows) for name, rows in sheets]
    workbook_sheets = "".join(
        f'<sheet name="{escape(name)}" sheetId="{idx}" r:id="rId{idx}"/>'
        for idx, (name, _) in enumerate(normalized, start=1)
    )
    workbook = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f'<sheets>{workbook_sheets}</sheets></workbook>'
    )
    rels = "".join(
        f'<Relationship Id="rId{idx}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{idx}.xml"/>'
        for idx in range(1, len(normalized) + 1)
    ) + f'<Relationship Id="rId{len(normalized)+1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
    workbook_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        f'{rels}</Relationships>'
    )
    content_overrides = "".join(
        f'<Override PartName="/xl/worksheets/sheet{idx}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        for idx in range(1, len(normalized) + 1)
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
        f'{content_overrides}</Types>'
    )
    root_rels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>'''
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", root_rels)
        archive.writestr("xl/workbook.xml", workbook)
        archive.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        archive.writestr("xl/styles.xml", _styles_xml())
        for idx, (_, rows) in enumerate(normalized, start=1):
            archive.writestr(f"xl/worksheets/sheet{idx}.xml", _worksheet_xml(rows))
    return output.getvalue()


def _dict_rows(items: list[dict[str, Any]]) -> list[list[Any]]:
    if not items:
        return [["Sem dados"]]
    headers = list(items[0].keys())
    return [headers] + [[item.get(key) for key in headers] for item in items]


def _kv_rows(values: dict[str, Any], title: str = "Campo") -> list[list[Any]]:
    def sheet_value(value: Any) -> Any:
        if isinstance(value, (dict, list, tuple)):
            return _stringify(value)
        return value
    return [[title, "Valor"]] + [[key, sheet_value(value)] for key, value in values.items()]


def simulation_xlsx_bytes(scenario: ScenarioSpec, result: SimulationResult) -> bytes:
    summary = result.summary.model_dump(mode="python")
    scenario_values = scenario.model_dump(mode="python")
    sheets: list[tuple[str, list[list[Any]]]] = [
        ("Resumo", [["Economy Lab v2.13.0", result.scenario], ["Modelo", result.model], ["Aviso", result.warning], []] + _kv_rows(summary, "Indicador")),
        ("Cenário", _kv_rows(scenario_values, "Parâmetro")),
        ("Série mensal", _dict_rows([point.model_dump(mode="python") for point in result.series])),
    ]
    if result.authority:
        sheets.append(("Autoridade - resumo", _kv_rows({
            "registry_version": result.authority.registry_version,
            "status": result.authority.status,
            "strict": result.authority.strict,
            "complete": result.authority.complete,
            "total_claims": result.authority.total_claims,
            "claims_by_source": result.authority.claims_by_source,
            "claims_by_field": result.authority.claims_by_field,
            "violations": result.authority.violations,
        }, "Campo")))
        sheets.append(("Autoridade - plano", _dict_rows([item.model_dump(mode="python") for item in result.authority.assignments])))
    if result.accounting:
        sheets.append(("Balanços", _dict_rows([{
            "sector": row.sector,
            "assets": row.assets,
            "liabilities": row.liabilities,
            "net_financial_worth": row.net_financial_worth,
            **{f"position_{k}": v for k, v in row.positions.items()},
        } for row in result.accounting.sector_balance_sheets])))
        sheets.append(("Godley estoques", _dict_rows([{"instrument": row.instrument, **row.sectors, "total": row.total} for row in result.accounting.stock_rows])))
        sheets.append(("Godley fluxos", _dict_rows([{"instrument": row.instrument, **row.sectors, "total": row.total} for row in result.accounting.flow_rows])))
    if result.banking:
        sheets.append(("Bancos", _dict_rows([bank.model_dump(mode="python") for bank in result.banking.banks])))
    resolution_rows = [
        point.model_dump(mode="python")
        for point in result.series
        if (point.bank_resolutions or 0) > 0 or (point.public_recapitalization or 0) > 0 or (point.bail_in_losses or 0) > 0
    ]
    if resolution_rows:
        sheets.append(("Resolução bancária", _dict_rows(resolution_rows)))
    if result.labor_market:
        sheets.append(("Mercado de trabalho", _kv_rows(result.labor_market.model_dump(mode="python"), "Campo")))
    if result.household_engine:
        sheets.append(("Famílias HARK", _kv_rows({
            "engine": result.household_engine.engine,
            "state_mode": result.household_engine.state_mode,
            "income_groups": result.household_engine.income_groups,
            "employment_rate": result.household_engine.employment_rate,
            "average_permanent_income": result.household_engine.average_permanent_income,
            "average_transitory_income_ratio": result.household_engine.average_transitory_income_ratio,
            "average_unemployment_probability": result.household_engine.average_unemployment_probability,
            "average_unemployment_benefit": result.household_engine.average_unemployment_benefit,
            "labor_force_participation": result.household_engine.labor_force_participation,
            "warning": result.household_engine.warning,
        }, "Campo")))
        sheets.append(("Grupos HARK", _dict_rows([group.model_dump(mode="python") for group in result.household_engine.groups])))
    if result.financial:
        sheets.append(("Motor financeiro", _kv_rows({
            "engine": result.financial.engine,
            "mode": result.financial.mode,
            "profile_id": result.financial.profile_id or "",
            **result.financial.current.model_dump(mode="python"),
            "warning": result.financial.warning,
        }, "Campo")))
        if result.financial.guidance_points:
            sheets.append(("Trajetória financeira", _dict_rows([point.model_dump(mode="python") for point in result.financial.guidance_points])))
    if result.macro:
        sheets.append(("Macro IRF", _dict_rows([point.model_dump(mode="python") for point in result.macro.irf])))
    if result.coupling:
        sheets.append(("Acoplamento", _dict_rows([point.model_dump(mode="python") for point in result.coupling.points])))
    return _xlsx_bytes(sheets)


def batch_xlsx_bytes(result: BatchExperimentResponse) -> bytes:
    sheets: list[tuple[str, list[list[Any]]]] = [
        ("Resumo", [["Economy Lab v2.13.0", "Experimento em lote"], ["Eixo", result.axis], ["Repetições", result.repetitions], ["Execuções", result.total_runs], ["Analytics", result.analytics_engine], ["Aviso", result.warning]]),
        ("Comparação", _dict_rows([item.model_dump(mode="python") for item in result.aggregates])),
        ("Execuções", _dict_rows([item.model_dump(mode="python") for item in result.runs])),
        ("Cenário base", _kv_rows(result.base_scenario.model_dump(mode="python"), "Parâmetro")),
    ]
    return _xlsx_bytes(sheets)


def calibration_xlsx_bytes(scenario, calibration, fit=None) -> bytes:
    metrics = []
    aligned_rows = []
    for item in calibration.metrics:
        raw = item.model_dump(mode="python")
        raw.pop("aligned_points", None)
        metrics.append(raw)
        for point in item.aligned_points:
            aligned_rows.append({
                "metric": item.metric,
                "series_id": item.series_id,
                "frequency": item.aligned_frequency or "",
                **point.model_dump(mode="python"),
            })
    sheets: list[tuple[str, list[list[Any]]]] = [
        ("Resumo calibração", [
            ["Economy Lab v2.13.0", "Calibration/Data Layer"],
            ["Score", calibration.score],
            ["Normalized RMSE", calibration.normalized_rmse],
            ["Revisão obrigatória", calibration.requires_review],
            ["Aviso", calibration.warning],
        ]),
        ("Métricas", _dict_rows(metrics)),
        ("Patch sugerido", _kv_rows(calibration.suggested_scenario_patch, "Parâmetro")),
        ("Cenário", _kv_rows(scenario.model_dump(mode="python"), "Parâmetro")),
    ]
    if aligned_rows:
        sheets.append(("Trajetórias alinhadas", _dict_rows(aligned_rows)))
    if fit is not None:
        sheets.extend([
            ("Ajuste limitado", [
                ["Baseline score", fit.baseline_score],
                ["Best score", fit.best_score],
                ["Evaluations", fit.evaluations],
                ["Rounds", fit.rounds_completed],
                ["Converged", fit.converged],
                ["Validation score", fit.validation_score if fit.validation_score is not None else ""],
                ["Review required", fit.requires_review],
                ["Warning", fit.warning],
            ]),
            ("Patch otimizado", _kv_rows(fit.best_scenario_patch, "Parâmetro")),
            ("Traço otimização", _dict_rows([row.model_dump(mode="python") for row in fit.trace])),
        ])
        if fit.validation_calibration is not None:
            validation_metrics = []
            for item in fit.validation_calibration.metrics:
                raw = item.model_dump(mode="python")
                raw.pop("aligned_points", None)
                validation_metrics.append(raw)
            sheets.append(("Validação fora amostra", _dict_rows(validation_metrics)))
    return _xlsx_bytes(sheets)


def simple_csv_bytes(result: SimpleRunResult) -> bytes:
    rows = []
    for item in result.years:
        rows.append({
            "year": item.year,
            "world_growth": item.external.world_growth,
            "consumer_confidence": item.external.consumer_confidence,
            "interest_rate": item.decision.interest_rate,
            "income_tax": item.decision.income_tax,
            "corporate_tax": item.decision.corporate_tax,
            "government_spending": item.decision.government_spending,
            "gdp_index": item.state.gdp_index,
            "real_gdp_growth": item.state.real_gdp_growth,
            "inflation": item.state.inflation,
            "unemployment": item.state.unemployment,
            "budget_deficit_to_gdp": item.state.budget_deficit_to_gdp,
            "debt_to_gdp": item.state.debt_to_gdp,
            "output_gap": item.state.output_gap,
            "approval": item.state.approval,
            "score_growth": item.score.growth,
            "score_unemployment": item.score.unemployment,
            "score_inflation": item.score.inflation,
            "score_fiscal": item.score.fiscal,
        })
    return _csv_bytes(list(rows[0].keys()) if rows else [], ([row[k] for k in rows[0].keys()] for row in rows) if rows else [])


def simple_xlsx_bytes(result: SimpleRunResult) -> bytes:
    history = []
    decisions = []
    score_rows = []
    explanations = []
    for item in result.years:
        history.append({
            "year": item.year, "gdp_index": item.state.gdp_index, "real_gdp_growth": item.state.real_gdp_growth,
            "inflation": item.state.inflation, "unemployment": item.state.unemployment,
            "budget_deficit_to_gdp": item.state.budget_deficit_to_gdp, "debt_to_gdp": item.state.debt_to_gdp,
            "output_gap": item.state.output_gap, "approval": item.state.approval,
            "world_growth": item.external.world_growth, "consumer_confidence": item.external.consumer_confidence,
        })
        decisions.append({"year": item.year, **item.decision.model_dump(mode="python")})
        score_rows.append({"year": item.year, **item.score.model_dump(mode="python")})
        explanations.append({
            "year": item.year, "explanation": " | ".join(item.explanation), "warnings": " | ".join(item.warnings)
        })
    sheets = [
        ("Resumo", [["Economy Lab v2.13.0", "Simple Macro"], ["Cenário", result.config.scenario_id], ["Anos executados", result.completed_years], ["Aviso", result.warning], [],
                    ["Indicador final", "Valor"], ["PIB índice", result.final_state.gdp_index], ["Crescimento PIB", result.final_state.real_gdp_growth],
                    ["Inflação", result.final_state.inflation], ["Desemprego", result.final_state.unemployment],
                    ["Déficit/PIB", result.final_state.budget_deficit_to_gdp], ["Dívida/PIB", result.final_state.debt_to_gdp], ["Aprovação", result.final_state.approval]]),
        ("Histórico 7 anos", _dict_rows(history)),
        ("Decisões", _dict_rows(decisions)),
        ("Pontuação", _dict_rows(score_rows)),
        ("Explicações", _dict_rows(explanations)),
        ("Configuração", _kv_rows(result.config.model_dump(mode="python"), "Parâmetro")),
    ]
    return _xlsx_bytes(sheets)
