"""Dynare 7.x / GNU Octave bridge.

Economy Lab keeps the ABM/SFC kernel as the accounting source of truth. Dynare is
used as an optional macro engine for a small New-Keynesian reference model and
returns impulse-response functions (IRFs) as advisory macro signals.

The adapter deliberately does not accept arbitrary user-supplied `.mod` source.
It renders a known template, executes Dynare through a local Octave process and
parses Dynare's generated ``*_results.mat`` file.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import shutil
import subprocess
import tempfile
from typing import Iterable

import numpy as np
from scipy.io import loadmat


class DynareUnavailableError(RuntimeError):
    """Raised when a Dynare run is requested but the local toolchain is unavailable."""


class DynareExecutionError(RuntimeError):
    """Raised when Dynare/Octave executes but does not produce a usable result."""


@dataclass(frozen=True)
class DynareStatus:
    configured: bool
    octave_executable: str | None
    dynare_matlab_path: str | None
    dynare_version_hint: str | None
    ready: bool
    error: str | None = None


@dataclass(frozen=True)
class DynareIRFPoint:
    period: int
    output_gap: float
    inflation_gap: float
    policy_rate_gap: float


@dataclass(frozen=True)
class DynareMacroResult:
    model_name: str
    model_kind: str
    period_unit: str
    shock_name: str
    shock_size_pp: float
    neutral_nominal_rate: float
    beta: float
    sigma: float
    kappa: float
    rho_i: float
    phi_pi: float
    phi_x: float
    points: tuple[DynareIRFPoint, ...]
    workdir: str
    results_file: str


def _candidate_octave_names() -> tuple[str, ...]:
    if os.name == "nt":
        return ("octave-cli.exe", "octave.exe", "octave-cli", "octave")
    return ("octave-cli", "octave")


def _detect_octave() -> str | None:
    explicit = os.getenv("OCTAVE_EXECUTABLE")
    if explicit:
        path = Path(explicit).expanduser()
        if path.exists():
            return str(path)
        found = shutil.which(explicit)
        if found:
            return found
    for name in _candidate_octave_names():
        found = shutil.which(name)
        if found:
            return found
    return None


def _detect_dynare_matlab_path() -> tuple[str | None, str | None]:
    explicit = os.getenv("DYNARE_MATLAB_PATH")
    if explicit:
        path = Path(explicit).expanduser()
        if path.is_dir():
            version = path.parent.name if path.name.lower() == "matlab" else None
            return str(path), version
        return str(path), None

    candidates: list[Path] = []
    if os.name == "nt":
        root = Path("C:/dynare")
        if root.exists():
            candidates.extend(root.glob("*/matlab"))
    else:
        candidates.extend(
            Path(path)
            for path in (
                "/usr/local/lib/dynare/matlab",
                "/usr/lib/dynare/matlab",
                "/opt/dynare/matlab",
            )
            if Path(path).is_dir()
        )

    if not candidates:
        return None, None

    def version_key(path: Path) -> tuple[int, ...]:
        raw = path.parent.name
        values: list[int] = []
        for part in raw.replace("-", ".").split("."):
            try:
                values.append(int(part))
            except ValueError:
                break
        return tuple(values) or (0,)

    selected = max(candidates, key=version_key)
    return str(selected), selected.parent.name


def dynare_status() -> DynareStatus:
    octave = _detect_octave()
    dynare_path, version = _detect_dynare_matlab_path()
    errors: list[str] = []
    if octave is None:
        errors.append("GNU Octave não encontrado; defina OCTAVE_EXECUTABLE se necessário")
    if dynare_path is None:
        errors.append("pasta matlab do Dynare não encontrada; defina DYNARE_MATLAB_PATH")
    elif not Path(dynare_path).is_dir():
        errors.append(f"DYNARE_MATLAB_PATH não existe: {dynare_path}")
    return DynareStatus(
        configured=bool(octave or dynare_path),
        octave_executable=octave,
        dynare_matlab_path=dynare_path,
        dynare_version_hint=version,
        ready=not errors,
        error="; ".join(errors) if errors else None,
    )


def _fmt(value: float) -> str:
    return f"{float(value):.12g}"


def render_reference_nk_model(
    *,
    irf_periods: int = 24,
    monetary_shock_pp: float = 1.0,
    beta: float = 0.99,
    sigma: float = 1.0,
    kappa: float = 0.10,
    rho_i: float = 0.80,
    phi_pi: float = 1.50,
    phi_x: float = 0.25,
    rho_r: float = 0.80,
    rho_u: float = 0.50,
) -> str:
    """Render a compact quarterly New-Keynesian DSGE reference model.

    Variables are percentage-point deviations from steady state. The monetary
    shock standard deviation is therefore expressed in percentage points.
    """
    if not 1 <= irf_periods <= 160:
        raise ValueError("irf_periods must be between 1 and 160")
    if monetary_shock_pp <= 0 or monetary_shock_pp > 20:
        raise ValueError("monetary_shock_pp must be in (0, 20]")

    return f"""// Economy Lab generated model — do not edit in-place
// Reference New-Keynesian DSGE; variables are p.p. deviations from steady state.

var x pi i r_n u;
varexo e_i e_r e_u;

parameters beta sigma kappa rho_i phi_pi phi_x rho_r rho_u;
beta   = {_fmt(beta)};
sigma  = {_fmt(sigma)};
kappa  = {_fmt(kappa)};
rho_i  = {_fmt(rho_i)};
phi_pi = {_fmt(phi_pi)};
phi_x  = {_fmt(phi_x)};
rho_r  = {_fmt(rho_r)};
rho_u  = {_fmt(rho_u)};

model(linear);
  // Dynamic IS curve
  x = x(+1) - (1/sigma)*(i - pi(+1) - r_n);

  // New-Keynesian Phillips curve
  pi = beta*pi(+1) + kappa*x + u;

  // Smoothed Taylor rule
  i = rho_i*i(-1) + (1-rho_i)*(phi_pi*pi + phi_x*x) + e_i;

  // Natural-rate and cost-push processes
  r_n = rho_r*r_n(-1) + e_r;
  u   = rho_u*u(-1) + e_u;
end;

steady;
check;

shocks;
  var e_i; stderr {_fmt(monetary_shock_pp)};
  var e_r; stderr 0;
  var e_u; stderr 0;
end;

stoch_simul(order=1, irf={int(irf_periods)}, nograph, nomoments, nocorr) x pi i;
"""


def _escape_octave_string(value: str) -> str:
    return value.replace("'", "''").replace("\\", "/")


def _find_results_file(workdir: Path, stem: str) -> Path:
    preferred = workdir / stem / "Output" / f"{stem}_results.mat"
    if preferred.exists():
        return preferred
    legacy = workdir / f"{stem}_results.mat"
    if legacy.exists():
        return legacy
    matches = list(workdir.rglob(f"{stem}_results.mat"))
    if matches:
        return matches[0]
    raise DynareExecutionError(f"Dynare terminou sem gerar {stem}_results.mat")


def _mat_field(obj: object, name: str) -> object:
    if hasattr(obj, name):
        return getattr(obj, name)
    if isinstance(obj, np.ndarray) and obj.dtype.names and name in obj.dtype.names:
        return obj[name]
    raise DynareExecutionError(f"campo ausente no resultado Dynare: {name}")


def _to_vector(value: object) -> np.ndarray:
    array = np.asarray(value, dtype=float).reshape(-1)
    return array


def parse_dynare_irfs(results_file: str | Path, *, shock_name: str = "e_i") -> tuple[DynareIRFPoint, ...]:
    payload = loadmat(str(results_file), squeeze_me=True, struct_as_record=False)
    if "oo_" not in payload:
        raise DynareExecutionError("arquivo Dynare não contém oo_")
    oo = payload["oo_"]
    irfs = _mat_field(oo, "irfs")

    def get(variable: str) -> np.ndarray:
        return _to_vector(_mat_field(irfs, f"{variable}_{shock_name}"))

    x = get("x")
    pi = get("pi")
    i = get("i")
    count = min(len(x), len(pi), len(i))
    if count == 0:
        raise DynareExecutionError("Dynare retornou IRFs vazias")
    return tuple(
        DynareIRFPoint(
            period=index + 1,
            output_gap=float(x[index]),
            inflation_gap=float(pi[index]),
            policy_rate_gap=float(i[index]),
        )
        for index in range(count)
    )


def run_reference_nk_model(
    *,
    irf_periods: int = 24,
    monetary_shock_pp: float = 1.0,
    neutral_nominal_rate: float = 8.0,
    beta: float = 0.99,
    sigma: float = 1.0,
    kappa: float = 0.10,
    rho_i: float = 0.80,
    phi_pi: float = 1.50,
    phi_x: float = 0.25,
    timeout_seconds: int = 120,
    keep_workdir: bool = False,
) -> DynareMacroResult:
    """Run the built-in macro reference model through local Octave + Dynare."""
    status = dynare_status()
    if not status.ready or not status.octave_executable or not status.dynare_matlab_path:
        raise DynareUnavailableError(status.error or "Dynare/Octave indisponível")

    temp = tempfile.mkdtemp(prefix="economy-lab-dynare-")
    workdir = Path(temp)
    stem = "economy_lab_nk"
    mod_file = workdir / f"{stem}.mod"
    mod_file.write_text(
        render_reference_nk_model(
            irf_periods=irf_periods,
            monetary_shock_pp=monetary_shock_pp,
            beta=beta,
            sigma=sigma,
            kappa=kappa,
            rho_i=rho_i,
            phi_pi=phi_pi,
            phi_x=phi_x,
        ),
        encoding="utf-8",
    )

    dynare_path = _escape_octave_string(status.dynare_matlab_path)
    workdir_string = _escape_octave_string(str(workdir))
    expression = (
        f"addpath('{dynare_path}'); "
        f"cd('{workdir_string}'); "
        f"dynare {stem}.mod noclearall nolog;"
    )
    command = [status.octave_executable, "--quiet", "--eval", expression]
    try:
        completed = subprocess.run(
            command,
            cwd=workdir,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        if not keep_workdir:
            shutil.rmtree(workdir, ignore_errors=True)
        raise DynareExecutionError(f"falha ao iniciar Dynare/Octave: {exc}") from exc

    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "erro sem saída").strip()
        if not keep_workdir:
            shutil.rmtree(workdir, ignore_errors=True)
        raise DynareExecutionError(f"Dynare/Octave retornou código {completed.returncode}: {detail[-3000:]}")

    results_file = _find_results_file(workdir, stem)
    points = parse_dynare_irfs(results_file)

    # Preserve the generated artifacts only when explicitly requested. The
    # response still records their paths for diagnostics in keep_workdir mode.
    result = DynareMacroResult(
        model_name="economy-lab-reference-nk",
        model_kind="new-keynesian-dsge",
        period_unit="quarter",
        shock_name="monetary_policy",
        shock_size_pp=float(monetary_shock_pp),
        neutral_nominal_rate=float(neutral_nominal_rate),
        beta=float(beta),
        sigma=float(sigma),
        kappa=float(kappa),
        rho_i=float(rho_i),
        phi_pi=float(phi_pi),
        phi_x=float(phi_x),
        points=points,
        workdir=str(workdir) if keep_workdir else "temporary-cleaned",
        results_file=str(results_file) if keep_workdir else "temporary-cleaned",
    )
    if not keep_workdir:
        shutil.rmtree(workdir, ignore_errors=True)
    return result


def irf_to_monthly_guidance(points: Iterable[DynareIRFPoint]) -> tuple[dict[str, float], ...]:
    """Expand quarterly IRFs into a conservative monthly advisory signal.

    This is intentionally *not* a structural frequency conversion. Each
    quarterly IRF value is held constant for its three constituent months. It
    exists only to provide an explicit bridge contract for later coupling.
    """
    monthly: list[dict[str, float]] = []
    month = 1
    for point in points:
        for _ in range(3):
            monthly.append(
                {
                    "month": float(month),
                    "output_gap": point.output_gap,
                    "inflation_gap": point.inflation_gap,
                    "policy_rate_gap": point.policy_rate_gap,
                }
            )
            month += 1
    return tuple(monthly)
