"""Qualification pack for Economy Lab optional external engines.

v2.7 turns the older availability/smoke checker into a qualification report:

* detection/import and real runtime execution are separate stages;
* Mesa/HARK/Dynare can be exercised through both their standalone bridge and
  the Economy Zero integration path;
* Minsky is intentionally read-only during qualification;
* every report includes a runtime fingerprint, qualification level and SHA-256
  digest so a Windows qualification run can be archived with a release.

A PASS means the requested qualification stages actually executed.  An
UNAVAILABLE engine was not installed/configured.  A FAIL means it was present
(or explicitly configured) but one of the required stages broke.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
from importlib import metadata
import json
import math
import os
import platform
import struct
import sys
from time import perf_counter
from typing import Iterable, Literal
from uuid import uuid4

EngineName = Literal["mesa", "hark", "dynare", "minsky"]
CheckStatus = Literal["pass", "fail", "unavailable"]
StageStatus = Literal["pass", "fail", "unavailable", "skipped"]
QualificationLevel = Literal["none", "detected", "read-only-verified", "runtime-verified"]
CompatibilityStatus = Literal["compatible", "warning", "unknown"]
ENGINE_ORDER: tuple[EngineName, ...] = ("mesa", "hark", "dynare", "minsky")
REPORT_SCHEMA = "economy-lab-external-validation-v2.7"
TARGET_VERSIONS: dict[EngineName, str | None] = {
    "mesa": "3.5.1",
    "hark": "0.17.2",
    "dynare": "7.x",
    "minsky": None,
}


@dataclass(frozen=True, slots=True)
class ExternalValidationStage:
    name: str
    status: StageStatus
    duration_ms: float
    summary: str
    details: dict[str, object] = field(default_factory=dict)
    error: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ExternalEngineCheck:
    engine: EngineName
    status: CheckStatus
    installed_or_configured: bool
    version: str | None
    duration_ms: float
    summary: str
    details: dict[str, object] = field(default_factory=dict)
    error: str | None = None
    qualification_level: QualificationLevel = "none"
    compatibility: CompatibilityStatus = "unknown"
    target_version: str | None = None
    integrated_smoke_passed: bool = False
    stages: tuple[ExternalValidationStage, ...] = ()

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["stages"] = [stage.to_dict() for stage in self.stages]
        return payload


@dataclass(frozen=True, slots=True)
class ExternalValidationReport:
    schema: str
    report_id: str
    report_digest: str
    generated_at: str
    economy_lab_version: str
    platform: str
    python_version: str
    environment: dict[str, object]
    requested_engines: tuple[EngineName, ...]
    smoke_tests: bool
    integration_tests: bool
    status: Literal["ready", "partial", "failed"]
    qualification_ready: bool
    passed: int
    failed: int
    unavailable: int
    runtime_verified: int
    read_only_verified: int
    checks: tuple[ExternalEngineCheck, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            **asdict(self),
            "requested_engines": list(self.requested_engines),
            "checks": [check.to_dict() for check in self.checks],
        }

    def to_markdown(self) -> str:
        lines = [
            "# Economy Lab — External Engine Qualification",
            "",
            f"- Report ID: `{self.report_id}`",
            f"- SHA-256: `{self.report_digest}`",
            f"- Generated: {self.generated_at}",
            f"- Economy Lab: {self.economy_lab_version}",
            f"- Runtime: {self.platform} · Python {self.python_version}",
            f"- Overall: **{self.status.upper()}**",
            f"- Qualification ready: **{'YES' if self.qualification_ready else 'NO'}**",
            "",
            "| Engine | Status | Qualification | Version | Compatibility | Integrated |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
        for check in self.checks:
            lines.append(
                f"| {check.engine.upper()} | {check.status.upper()} | {check.qualification_level} | "
                f"{check.version or '—'} | {check.compatibility} | "
                f"{'yes' if check.integrated_smoke_passed else 'no'} |"
            )
        for check in self.checks:
            lines.extend(["", f"## {check.engine.upper()}", "", check.summary])
            if check.error:
                lines.append(f"\n**Error:** `{check.error}`")
            lines.extend(["", "| Stage | Status | Time | Evidence |", "| --- | --- | ---: | --- |"])
            for stage in check.stages:
                evidence = stage.summary.replace("|", "\\|")
                if stage.error:
                    evidence += f" — {stage.error}".replace("|", "\\|")
                lines.append(f"| {stage.name} | {stage.status.upper()} | {stage.duration_ms:.0f} ms | {evidence} |")
        lines.extend(
            [
                "",
                "## Notes",
                "",
                "- Minsky qualification is read-only by design; it does not step/reset/load/save the open model.",
                "- A PASS is runtime evidence, not a statement that the economic model is calibrated or empirically valid.",
                "- Keep this report with the release/build that was qualified.",
                "",
            ]
        )
        return "\n".join(lines)


def _package_version(*names: str) -> str | None:
    for name in names:
        try:
            return metadata.version(name)
        except metadata.PackageNotFoundError:
            continue
    return None


def _elapsed_ms(started: float) -> float:
    return round((perf_counter() - started) * 1000.0, 2)


def _stage(
    name: str,
    status: StageStatus,
    started: float,
    summary: str,
    *,
    details: dict[str, object] | None = None,
    error: Exception | str | None = None,
) -> ExternalValidationStage:
    if isinstance(error, Exception):
        error_text = f"{type(error).__name__}: {error}"
    else:
        error_text = error
    return ExternalValidationStage(
        name=name,
        status=status,
        duration_ms=_elapsed_ms(started),
        summary=summary,
        details=details or {},
        error=error_text,
    )


def _compatibility(engine: EngineName, version: str | None) -> CompatibilityStatus:
    target = TARGET_VERSIONS[engine]
    if not target or not version:
        return "unknown"
    if target.endswith(".x"):
        return "compatible" if version.startswith(target[:-1]) else "warning"
    return "compatible" if version == target else "warning"


def _accounting_evidence(result: object) -> dict[str, object]:
    summary = getattr(result, "summary", None)
    return {
        "ledger_balanced": bool(getattr(summary, "ledger_balanced", False)),
        "godley_stocks_balanced": bool(getattr(summary, "godley_stocks_balanced", False)),
        "godley_flows_balanced": bool(getattr(summary, "godley_flows_balanced", False)),
    }


def _assert_integrated_accounting(result: object) -> dict[str, object]:
    evidence = _accounting_evidence(result)
    if not all(evidence.values()):
        raise RuntimeError(f"integrated smoke accounting invariant failed: {evidence}")
    return evidence


def validate_mesa(*, smoke_test: bool = True, integration_test: bool = True) -> ExternalEngineCheck:
    from economy_lab.engines.mesa_adapter import mesa_available

    total_started = perf_counter()
    stages: list[ExternalValidationStage] = []
    version = _package_version("mesa")

    started = perf_counter()
    available = mesa_available()
    stages.append(
        _stage(
            "detect-import",
            "pass" if available else "unavailable",
            started,
            "Mesa importado pelo adapter." if available else "Mesa não está instalado neste runtime.",
            details={"observed_version": version, "target_version": TARGET_VERSIONS["mesa"]},
        )
    )
    if not available:
        return ExternalEngineCheck(
            engine="mesa", status="unavailable", installed_or_configured=False,
            version=version, duration_ms=_elapsed_ms(total_started),
            summary="Mesa não está instalado neste runtime.",
            details={"target_version": TARGET_VERSIONS["mesa"]},
            qualification_level="none", compatibility=_compatibility("mesa", version),
            target_version=TARGET_VERSIONS["mesa"], stages=tuple(stages),
        )

    if not smoke_test:
        stages.append(_stage("standalone-smoke", "skipped", perf_counter(), "Smoke test desativado pelo solicitante."))
        if integration_test:
            stages.append(_stage("economy-zero-integration", "skipped", perf_counter(), "Integração requer smoke_tests=true."))
        return ExternalEngineCheck(
            engine="mesa", status="pass", installed_or_configured=True,
            version=version, duration_ms=_elapsed_ms(total_started),
            summary="Mesa importável; execução real não foi solicitada.",
            details={"target_version": TARGET_VERSIONS["mesa"]}, qualification_level="detected",
            compatibility=_compatibility("mesa", version), target_version=TARGET_VERSIONS["mesa"], stages=tuple(stages),
        )

    try:
        from economy_lab.labs.standalone import run_mesa_lab
        started = perf_counter()
        result = run_mesa_lab(agents=12, steps=4, initial_wealth=10.0, transfer_amount=1.0, seed=11)
        conserved = math.isclose(
            float(result["initial_total_wealth"]), float(result["final_total_wealth"]),
            rel_tol=0.0, abs_tol=1e-8,
        )
        if not conserved:
            raise RuntimeError("wealth conservation smoke invariant failed")
        stages.append(
            _stage(
                "standalone-smoke", "pass", started,
                "AgentSet/shuffle_do executou e preservou riqueza total.",
                details={"agents": result.get("agents"), "steps": result.get("steps"), "gini": result.get("gini")},
            )
        )
    except Exception as exc:
        stages.append(_stage("standalone-smoke", "fail", started, "Smoke Mesa standalone falhou.", error=exc))
        return ExternalEngineCheck(
            engine="mesa", status="fail", installed_or_configured=True,
            version=version, duration_ms=_elapsed_ms(total_started),
            summary="Mesa está instalado, mas o smoke test standalone falhou.",
            error=f"{type(exc).__name__}: {exc}", qualification_level="detected",
            compatibility=_compatibility("mesa", version), target_version=TARGET_VERSIONS["mesa"], stages=tuple(stages),
        )

    integrated = False
    if integration_test:
        try:
            from economy_lab.core.schemas import ScenarioSpec
            from economy_lab.core.simulation import run_economy_zero
            started = perf_counter()
            sim = run_economy_zero(
                ScenarioSpec(
                    name="Mesa qualification",
                    months=2, households=100, firms=5, banks=2, seed=917,
                    activation_engine="mesa", household_behavior="heuristic",
                )
            )
            evidence = _assert_integrated_accounting(sim)
            activation = getattr(getattr(sim, "engines", None), "activation", "")
            if "mesa" not in str(activation).lower():
                raise RuntimeError(f"Economy Zero did not report Mesa activation: {activation}")
            evidence["activation_trace"] = str(activation)
            stages.append(
                _stage(
                    "economy-zero-integration", "pass", started,
                    "Economy Zero executou com ativação Mesa e SFC permaneceu balanceado.", details=evidence,
                )
            )
            integrated = True
        except Exception as exc:
            stages.append(_stage("economy-zero-integration", "fail", started, "Integração Mesa → Economy Zero falhou.", error=exc))
            return ExternalEngineCheck(
                engine="mesa", status="fail", installed_or_configured=True,
                version=version, duration_ms=_elapsed_ms(total_started),
                summary="Mesa executa standalone, mas falhou dentro do Economy Zero.",
                error=f"{type(exc).__name__}: {exc}", qualification_level="detected",
                compatibility=_compatibility("mesa", version), target_version=TARGET_VERSIONS["mesa"], stages=tuple(stages),
            )
    else:
        stages.append(_stage("economy-zero-integration", "skipped", perf_counter(), "Teste integrado desativado."))

    level: QualificationLevel = "runtime-verified" if integrated else "detected"
    return ExternalEngineCheck(
        engine="mesa", status="pass", installed_or_configured=True,
        version=version, duration_ms=_elapsed_ms(total_started),
        summary="Mesa executou os testes reais solicitados." if integrated else "Mesa passou no smoke standalone.",
        details={"target_version": TARGET_VERSIONS["mesa"]}, qualification_level=level,
        compatibility=_compatibility("mesa", version), target_version=TARGET_VERSIONS["mesa"],
        integrated_smoke_passed=integrated, stages=tuple(stages),
    )


def validate_hark(*, smoke_test: bool = True, integration_test: bool = True) -> ExternalEngineCheck:
    from economy_lab.engines.hark_adapter import hark_available

    total_started = perf_counter()
    stages: list[ExternalValidationStage] = []
    version = _package_version("econ-ark", "HARK")
    started = perf_counter()
    available = hark_available()
    stages.append(
        _stage(
            "detect-import", "pass" if available else "unavailable", started,
            "HARK importado pelo adapter." if available else "Econ-ARK/HARK não está instalado neste runtime.",
            details={"observed_version": version, "target_version": TARGET_VERSIONS["hark"]},
        )
    )
    if not available:
        return ExternalEngineCheck(
            engine="hark", status="unavailable", installed_or_configured=False,
            version=version, duration_ms=_elapsed_ms(total_started),
            summary="Econ-ARK/HARK não está instalado neste runtime.",
            details={"target_version": TARGET_VERSIONS["hark"]}, qualification_level="none",
            compatibility=_compatibility("hark", version), target_version=TARGET_VERSIONS["hark"], stages=tuple(stages),
        )
    if not smoke_test:
        stages.append(_stage("standalone-smoke", "skipped", perf_counter(), "Smoke test desativado pelo solicitante."))
        if integration_test:
            stages.append(_stage("economy-zero-integration", "skipped", perf_counter(), "Integração requer smoke_tests=true."))
        return ExternalEngineCheck(
            engine="hark", status="pass", installed_or_configured=True, version=version,
            duration_ms=_elapsed_ms(total_started), summary="HARK importável; execução real não foi solicitada.",
            qualification_level="detected", compatibility=_compatibility("hark", version),
            target_version=TARGET_VERSIONS["hark"], stages=tuple(stages),
        )

    try:
        from economy_lab.labs.standalone import run_hark_lab
        started = perf_counter()
        result = run_hark_lab(
            annual_interest_rate=0.08, crra=2.0, annual_discount_factor=0.96,
            unemployment_probability=0.05, unemployment_replacement_rate=0.30,
            income_groups=2, income_risk_dispersion=0.20, max_market_resources=3.0, points=5,
        )
        curve = result.get("policy_curve") or []
        if len(curve) != 5:
            raise RuntimeError("unexpected HARK policy-curve length")
        finite = all(math.isfinite(float(row["consumption"])) and math.isfinite(float(row["saving"])) for row in curve)
        bounded = all(-1e-10 <= float(row["consumption"]) <= float(row["market_resources"]) + 1e-10 for row in curve)
        if not finite or not bounded:
            raise RuntimeError("HARK returned a non-finite or unbounded policy curve")
        stages.append(
            _stage(
                "standalone-smoke", "pass", started,
                "IndShockConsumerType resolveu uma política de consumo finita e limitada.",
                details={"points": len(curve), "groups": len(result.get("group_profiles") or []), "finite": finite, "bounded": bounded},
            )
        )
    except Exception as exc:
        stages.append(_stage("standalone-smoke", "fail", started, "Smoke HARK standalone falhou.", error=exc))
        return ExternalEngineCheck(
            engine="hark", status="fail", installed_or_configured=True, version=version,
            duration_ms=_elapsed_ms(total_started), summary="HARK está instalado, mas o solve standalone falhou.",
            error=f"{type(exc).__name__}: {exc}", qualification_level="detected",
            compatibility=_compatibility("hark", version), target_version=TARGET_VERSIONS["hark"], stages=tuple(stages),
        )

    integrated = False
    if integration_test:
        try:
            from economy_lab.core.schemas import ScenarioSpec
            from economy_lab.core.simulation import run_economy_zero
            started = perf_counter()
            sim = run_economy_zero(
                ScenarioSpec(
                    name="HARK qualification", months=2, households=100, firms=5, banks=2, seed=918,
                    activation_engine="native", household_behavior="hark", hark_income_groups=2,
                )
            )
            evidence = _assert_integrated_accounting(sim)
            decision = getattr(getattr(sim, "engines", None), "household_decision", "")
            if "hark" not in str(decision).lower():
                raise RuntimeError(f"Economy Zero did not report HARK household policy: {decision}")
            evidence["household_trace"] = str(decision)
            stages.append(
                _stage(
                    "economy-zero-integration", "pass", started,
                    "Economy Zero executou decisões HARK stateful e SFC permaneceu balanceado.", details=evidence,
                )
            )
            integrated = True
        except Exception as exc:
            stages.append(_stage("economy-zero-integration", "fail", started, "Integração HARK → Economy Zero falhou.", error=exc))
            return ExternalEngineCheck(
                engine="hark", status="fail", installed_or_configured=True, version=version,
                duration_ms=_elapsed_ms(total_started), summary="HARK executa standalone, mas falhou dentro do Economy Zero.",
                error=f"{type(exc).__name__}: {exc}", qualification_level="detected",
                compatibility=_compatibility("hark", version), target_version=TARGET_VERSIONS["hark"], stages=tuple(stages),
            )
    else:
        stages.append(_stage("economy-zero-integration", "skipped", perf_counter(), "Teste integrado desativado."))

    return ExternalEngineCheck(
        engine="hark", status="pass", installed_or_configured=True, version=version,
        duration_ms=_elapsed_ms(total_started),
        summary="HARK executou os testes reais solicitados." if integrated else "HARK passou no smoke standalone.",
        qualification_level="runtime-verified" if integrated else "detected",
        compatibility=_compatibility("hark", version), target_version=TARGET_VERSIONS["hark"],
        integrated_smoke_passed=integrated, stages=tuple(stages),
    )


def validate_dynare(
    *, smoke_test: bool = True, integration_test: bool = True, timeout_seconds: int = 60,
) -> ExternalEngineCheck:
    from economy_lab.engines.dynare_adapter import dynare_status, run_reference_nk_model

    total_started = perf_counter()
    stages: list[ExternalValidationStage] = []
    status = dynare_status()
    version = status.dynare_version_hint
    details: dict[str, object] = {
        "octave_executable": status.octave_executable,
        "dynare_matlab_path": status.dynare_matlab_path,
        "dynare_version_hint": version,
    }
    started = perf_counter()
    detect_status: StageStatus = "pass" if status.ready else ("fail" if status.configured else "unavailable")
    stages.append(
        _stage(
            "detect-runtime", detect_status, started,
            "Octave e Dynare detectados." if status.ready else "Dynare/Octave não está pronto para execução.",
            details=details, error=status.error,
        )
    )
    if not status.ready:
        check_status: CheckStatus = "fail" if status.configured else "unavailable"
        return ExternalEngineCheck(
            engine="dynare", status=check_status, installed_or_configured=status.configured,
            version=version, duration_ms=_elapsed_ms(total_started),
            summary="Dynare/Octave não está pronto para execução.", details=details, error=status.error,
            qualification_level="none", compatibility=_compatibility("dynare", version),
            target_version=TARGET_VERSIONS["dynare"], stages=tuple(stages),
        )
    if not smoke_test:
        stages.append(_stage("reference-model-smoke", "skipped", perf_counter(), "Smoke test desativado pelo solicitante."))
        if integration_test:
            stages.append(_stage("economy-zero-integration", "skipped", perf_counter(), "Integração requer smoke_tests=true."))
        return ExternalEngineCheck(
            engine="dynare", status="pass", installed_or_configured=True, version=version,
            duration_ms=_elapsed_ms(total_started), summary="Dynare/Octave detectado; execução real não foi solicitada.",
            details=details, qualification_level="detected", compatibility=_compatibility("dynare", version),
            target_version=TARGET_VERSIONS["dynare"], stages=tuple(stages),
        )

    try:
        started = perf_counter()
        result = run_reference_nk_model(
            irf_periods=4, monetary_shock_pp=0.25, neutral_nominal_rate=8.0,
            timeout_seconds=max(10, min(180, int(timeout_seconds))),
        )
        points = result.points
        finite = bool(points) and all(
            math.isfinite(point.output_gap) and math.isfinite(point.inflation_gap) and math.isfinite(point.policy_rate_gap)
            for point in points
        )
        if not finite:
            raise RuntimeError("Dynare returned empty/non-finite IRFs")
        ref_details = {
            "model_name": result.model_name, "irf_points": len(points),
            "first_policy_rate_gap": points[0].policy_rate_gap,
            "first_output_gap": points[0].output_gap, "finite": finite,
            "results_file_name": os.path.basename(result.results_file),
        }
        stages.append(
            _stage(
                "reference-model-smoke", "pass", started,
                "Dynare executou .mod real via Octave e retornou IRFs finitas.", details=ref_details,
            )
        )
        details.update(ref_details)
    except Exception as exc:
        stages.append(_stage("reference-model-smoke", "fail", started, "Execução do modelo Dynare de referência falhou.", error=exc))
        return ExternalEngineCheck(
            engine="dynare", status="fail", installed_or_configured=True, version=version,
            duration_ms=_elapsed_ms(total_started), summary="Dynare/Octave foi detectado, mas o .mod real falhou.",
            details=details, error=f"{type(exc).__name__}: {exc}", qualification_level="detected",
            compatibility=_compatibility("dynare", version), target_version=TARGET_VERSIONS["dynare"], stages=tuple(stages),
        )

    integrated = False
    if integration_test:
        try:
            from economy_lab.core.schemas import ScenarioSpec
            from economy_lab.core.simulation import run_economy_zero
            started = perf_counter()
            sim = run_economy_zero(
                ScenarioSpec(
                    name="Dynare qualification", months=1, households=100, firms=5, banks=2, seed=919,
                    macro_engine="dynare", macro_coupling="advisory", dynare_irf_periods=4,
                    dynare_monetary_shock_bp=25.0,
                )
            )
            evidence = _assert_integrated_accounting(sim)
            macro_trace = getattr(getattr(sim, "engines", None), "macro", "")
            macro_report = getattr(sim, "macro", None)
            if "dynare" not in str(macro_trace).lower() or macro_report is None:
                raise RuntimeError(f"Economy Zero did not return Dynare macro report: {macro_trace}")
            evidence["macro_trace"] = str(macro_trace)
            evidence["irf_points"] = len(getattr(macro_report, "irf", []) or [])
            stages.append(
                _stage(
                    "economy-zero-integration", "pass", started,
                    "Economy Zero consumiu um resultado Dynare real e preservou o SFC.", details=evidence,
                )
            )
            integrated = True
        except Exception as exc:
            stages.append(_stage("economy-zero-integration", "fail", started, "Integração Dynare → Economy Zero falhou.", error=exc))
            return ExternalEngineCheck(
                engine="dynare", status="fail", installed_or_configured=True, version=version,
                duration_ms=_elapsed_ms(total_started), summary="Dynare executa standalone, mas falhou dentro do Economy Zero.",
                details=details, error=f"{type(exc).__name__}: {exc}", qualification_level="detected",
                compatibility=_compatibility("dynare", version), target_version=TARGET_VERSIONS["dynare"], stages=tuple(stages),
            )
    else:
        stages.append(_stage("economy-zero-integration", "skipped", perf_counter(), "Teste integrado desativado."))

    return ExternalEngineCheck(
        engine="dynare", status="pass", installed_or_configured=True, version=version,
        duration_ms=_elapsed_ms(total_started), summary="Dynare executou os testes reais solicitados.",
        details=details, qualification_level="runtime-verified" if integrated else "detected",
        compatibility=_compatibility("dynare", version), target_version=TARGET_VERSIONS["dynare"],
        integrated_smoke_passed=integrated, stages=tuple(stages),
    )


def validate_minsky(*, smoke_test: bool = True, timeout_seconds: float = 3.0) -> ExternalEngineCheck:
    from economy_lab.engines.minsky_adapter import MinskyRestClient, bridge_status

    total_started = perf_counter()
    stages: list[ExternalValidationStage] = []
    status = bridge_status()
    details: dict[str, object] = {
        "object_type": status.object_type,
        "model_time": status.model_time,
        "read_only_smoke": True,
        "rest_url_configured": bool(os.getenv("MINSKY_REST_URL", "").strip()),
    }
    started = perf_counter()
    if not status.configured:
        stages.append(_stage("rest-handshake", "unavailable", started, "MINSKY_REST_URL não está configurado."))
        return ExternalEngineCheck(
            engine="minsky", status="unavailable", installed_or_configured=False, version=None,
            duration_ms=_elapsed_ms(total_started), summary="MINSKY_REST_URL não está configurado.",
            details=details, qualification_level="none", compatibility="unknown", target_version=None, stages=tuple(stages),
        )
    if not status.reachable:
        stages.append(_stage("rest-handshake", "fail", started, "Minsky REST não respondeu ao handshake.", error=status.error))
        return ExternalEngineCheck(
            engine="minsky", status="fail", installed_or_configured=True, version=None,
            duration_ms=_elapsed_ms(total_started), summary="Minsky REST está configurado, mas não respondeu ao handshake.",
            error=status.error, details=details, qualification_level="detected", compatibility="unknown", stages=tuple(stages),
        )
    stages.append(
        _stage(
            "rest-handshake", "pass", started,
            "Minsky respondeu a /minsky/@type e /minsky/t.",
            details={"object_type": status.object_type, "model_time": status.model_time},
        )
    )
    if not smoke_test:
        stages.append(_stage("read-only-introspection", "skipped", perf_counter(), "Smoke test desativado pelo solicitante."))
        return ExternalEngineCheck(
            engine="minsky", status="pass", installed_or_configured=True, version=None,
            duration_ms=_elapsed_ms(total_started), summary="Minsky REST respondeu ao handshake; introspecção não solicitada.",
            details=details, qualification_level="detected", compatibility="unknown", stages=tuple(stages),
        )
    try:
        started = perf_counter()
        client = MinskyRestClient(timeout=max(0.5, min(30.0, float(timeout_seconds))))
        members = client.list_members("/minsky")
        member_count = len(members) if isinstance(members, (list, dict)) else None
        if members is None:
            raise RuntimeError("Minsky returned null introspection payload")
        introspection_details = {
            "member_count": member_count,
            "payload_type": type(members).__name__,
            "read_only": True,
        }
        stages.append(
            _stage(
                "read-only-introspection", "pass", started,
                "Minsky respondeu à introspecção @list sem alterar o modelo.", details=introspection_details,
            )
        )
        details.update(introspection_details)
    except Exception as exc:
        stages.append(_stage("read-only-introspection", "fail", started, "Introspecção REST Minsky falhou.", error=exc))
        return ExternalEngineCheck(
            engine="minsky", status="fail", installed_or_configured=True, version=None,
            duration_ms=_elapsed_ms(total_started), summary="Minsky respondeu ao handshake, mas a introspecção REST falhou.",
            error=f"{type(exc).__name__}: {exc}", details=details, qualification_level="detected",
            compatibility="unknown", stages=tuple(stages),
        )

    # Read-only verification is intentionally the strongest level in v2.7.
    # Controlled writable .mky reconciliation belongs to the later SFC/Minsky freeze stage.
    return ExternalEngineCheck(
        engine="minsky", status="pass", installed_or_configured=True, version=None,
        duration_ms=_elapsed_ms(total_started),
        summary="Minsky REST foi qualificado em modo somente leitura.", details=details,
        qualification_level="read-only-verified", compatibility="unknown", target_version=None,
        integrated_smoke_passed=False, stages=tuple(stages),
    )


def _environment_snapshot() -> dict[str, object]:
    return {
        "os": platform.system(),
        "os_release": platform.release(),
        "os_version": platform.version(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "python_executable": sys.executable,
        "python_implementation": platform.python_implementation(),
        "python_bits": struct.calcsize("P") * 8,
        "pip_version": _package_version("pip"),
        "configuration_flags": {
            # Do not include environment variable values in the top-level fingerprint.
            "OCTAVE_EXECUTABLE": bool(os.getenv("OCTAVE_EXECUTABLE")),
            "DYNARE_MATLAB_PATH": bool(os.getenv("DYNARE_MATLAB_PATH")),
            "MINSKY_REST_URL": bool(os.getenv("MINSKY_REST_URL")),
        },
    }


def _digest_payload(payload: dict[str, object]) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def verify_report_digest(report: ExternalValidationReport | dict[str, object]) -> bool:
    payload = report.to_dict() if isinstance(report, ExternalValidationReport) else dict(report)
    expected = str(payload.pop("report_digest", ""))
    return bool(expected) and _digest_payload(payload) == expected


def validate_external_engines(
    engines: Iterable[EngineName] = ENGINE_ORDER,
    *,
    smoke_tests: bool = True,
    integration_tests: bool = True,
    dynare_timeout_seconds: int = 60,
    minsky_timeout_seconds: float = 3.0,
    economy_lab_version: str = "2.13.0",
) -> ExternalValidationReport:
    requested: list[EngineName] = []
    for engine in engines:
        if engine not in ENGINE_ORDER:
            raise ValueError(f"unsupported external engine: {engine}")
        if engine not in requested:
            requested.append(engine)

    validators = {
        "mesa": lambda: validate_mesa(smoke_test=smoke_tests, integration_test=integration_tests),
        "hark": lambda: validate_hark(smoke_test=smoke_tests, integration_test=integration_tests),
        "dynare": lambda: validate_dynare(
            smoke_test=smoke_tests, integration_test=integration_tests, timeout_seconds=dynare_timeout_seconds,
        ),
        "minsky": lambda: validate_minsky(smoke_test=smoke_tests, timeout_seconds=minsky_timeout_seconds),
    }
    checks = tuple(validators[engine]() for engine in requested)
    passed = sum(check.status == "pass" for check in checks)
    failed = sum(check.status == "fail" for check in checks)
    unavailable = sum(check.status == "unavailable" for check in checks)
    runtime_verified = sum(check.qualification_level == "runtime-verified" for check in checks)
    read_only_verified = sum(check.qualification_level == "read-only-verified" for check in checks)
    if failed:
        overall: Literal["ready", "partial", "failed"] = "failed"
    elif unavailable:
        overall = "partial"
    else:
        overall = "ready"

    # For v2.7, all requested engines must PASS.  Mesa/HARK/Dynare additionally
    # require integrated runtime verification when integration tests are enabled;
    # Minsky is intentionally allowed at read-only-verified until reconciliation.
    required_levels_ok = all(
        check.status == "pass"
        and (
            not (smoke_tests and integration_tests)
            or check.engine == "minsky" and check.qualification_level == "read-only-verified"
            or check.engine != "minsky" and check.qualification_level == "runtime-verified"
        )
        for check in checks
    )
    qualification_ready = bool(checks) and required_levels_ok

    report_id = str(uuid4())
    generated_at = datetime.now(timezone.utc).isoformat()
    environment = _environment_snapshot()
    payload_without_digest: dict[str, object] = {
        "schema": REPORT_SCHEMA,
        "report_id": report_id,
        "generated_at": generated_at,
        "economy_lab_version": economy_lab_version,
        "platform": f"{platform.system()} {platform.release()} ({platform.machine()})",
        "python_version": sys.version.split()[0],
        "environment": environment,
        "requested_engines": list(requested),
        "smoke_tests": smoke_tests,
        "integration_tests": integration_tests,
        "status": overall,
        "qualification_ready": qualification_ready,
        "passed": passed,
        "failed": failed,
        "unavailable": unavailable,
        "runtime_verified": runtime_verified,
        "read_only_verified": read_only_verified,
        "checks": [check.to_dict() for check in checks],
    }
    digest = _digest_payload(payload_without_digest)
    return ExternalValidationReport(
        schema=REPORT_SCHEMA,
        report_id=report_id,
        report_digest=digest,
        generated_at=generated_at,
        economy_lab_version=economy_lab_version,
        platform=str(payload_without_digest["platform"]),
        python_version=str(payload_without_digest["python_version"]),
        environment=environment,
        requested_engines=tuple(requested),
        smoke_tests=smoke_tests,
        integration_tests=integration_tests,
        status=overall,
        qualification_ready=qualification_ready,
        passed=passed,
        failed=failed,
        unavailable=unavailable,
        runtime_verified=runtime_verified,
        read_only_verified=read_only_verified,
        checks=checks,
    )
