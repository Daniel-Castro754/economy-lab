"""Minsky bridge for Economy Lab v0.6.

The bridge has two stable layers:
1) a deterministic Economy Lab Godley exchange payload (JSON/CSV friendly), and
2) an operational REST/template bridge for a running Minsky instance.

Economy Lab remains the accounting source of truth. A live Minsky model is used
as a secondary dynamics/visualisation engine, not as a replacement ledger.
"""
from __future__ import annotations

from dataclasses import dataclass
import csv
import io
import ipaddress
import json
import os
from urllib import parse, request
from urllib.error import URLError

from economy_lab.finance import Ledger, flow_matrix, stock_matrix
from economy_lab.finance.sfc import SECTORS

_MAX_REST_RESPONSE_BYTES = 16 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class MinskyGodleyExport:
    tick: int
    columns: tuple[str, ...]
    stock_rows: tuple[dict[str, object], ...]
    flow_rows: tuple[dict[str, object], ...]

    def to_payload(self) -> dict[str, object]:
        return {
            "schema": "economy-lab-godley-v1.0",
            "tick": self.tick,
            "columns": list(self.columns),
            "stocks": list(self.stock_rows),
            "flows": list(self.flow_rows),
        }

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_payload(), ensure_ascii=False, indent=indent)

    def matrix_csv(self, kind: str) -> str:
        rows = self.stock_rows if kind == "stocks" else self.flow_rows
        out = io.StringIO()
        writer = csv.DictWriter(out, fieldnames=["instrument", *self.columns, "total"])
        writer.writeheader()
        writer.writerows(rows)
        return out.getvalue()


def build_godley_export(ledger: Ledger, *, tick: int) -> MinskyGodleyExport:
    stocks = stock_matrix(ledger, tick=tick)
    flows = flow_matrix(ledger, tick=tick)
    columns = tuple(SECTORS)

    def rows(matrix):
        return tuple(
            {
                "instrument": row.instrument,
                **{sector: row.sectors.get(sector, 0.0) for sector in columns},
                "total": row.total,
            }
            for row in matrix.rows
        )

    return MinskyGodleyExport(
        tick=tick,
        columns=columns,
        stock_rows=rows(stocks),
        flow_rows=rows(flows),
    )


def minsky_rest_configured() -> bool:
    return bool(os.getenv("MINSKY_REST_URL", "").strip())


def _is_loopback_host(hostname: str) -> bool:
    if hostname.lower().rstrip(".") == "localhost":
        return True
    try:
        return ipaddress.ip_address(hostname).is_loopback
    except ValueError:
        return False


def _validated_minsky_rest_url(value: str) -> str:
    if not value:
        raise ValueError("Minsky REST URL is not configured")
    try:
        parsed = parse.urlsplit(value)
        hostname = parsed.hostname
        _ = parsed.port
    except ValueError:
        raise ValueError("Minsky REST URL configuration is invalid") from None

    scheme = parsed.scheme.lower()
    if scheme not in {"http", "https"}:
        raise ValueError("Minsky REST URL must use HTTP or HTTPS")
    if not hostname:
        raise ValueError("Minsky REST URL must include a hostname")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("Minsky REST URL must not include embedded credentials")
    if parsed.query or parsed.fragment or "?" in value or "#" in value:
        raise ValueError("Minsky REST URL must not include a query or fragment")
    if scheme == "http" and not _is_loopback_host(hostname):
        raise ValueError("Minsky REST URL must use HTTPS for non-loopback hosts")

    path = "" if parsed.path == "/" else parsed.path
    return parse.urlunsplit((scheme, parsed.netloc, path, "", ""))


def _read_json_response(response) -> object:
    declared_length = response.headers.get("Content-Length")
    try:
        declared_bytes = int(declared_length) if declared_length is not None else None
    except (TypeError, ValueError):
        declared_bytes = None
    if declared_bytes is not None and declared_bytes > _MAX_REST_RESPONSE_BYTES:
        raise ValueError("Minsky REST response exceeds the allowed size")
    raw = response.read(_MAX_REST_RESPONSE_BYTES + 1)
    if len(raw) > _MAX_REST_RESPONSE_BYTES:
        raise ValueError("Minsky REST response exceeds the allowed size")
    return json.loads(raw.decode("utf-8")) if raw else None


@dataclass(frozen=True, slots=True)
class MinskyBridgeStatus:
    configured: bool
    reachable: bool
    object_type: str | None = None
    model_time: float | None = None
    error: str | None = None


class MinskyRestClient:
    """Client for Minsky's documented GET/PUT object REST protocol."""

    def __init__(self, base_url: str | None = None, timeout: float = 3.0):
        configured_url = base_url or os.getenv("MINSKY_REST_URL", "")
        self.base_url = _validated_minsky_rest_url(configured_url)
        self.timeout = timeout

    def _url(self, path: str) -> str:
        separator = "" if self.base_url.endswith("/") else "/"
        return f"{self.base_url}{separator}{path.lstrip('/')}"

    def get(self, path: str) -> object:
        with request.urlopen(self._url(path), timeout=self.timeout) as response:
            return _read_json_response(response)

    def put(self, path: str, payload: object) -> object:
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(
            self._url(path), data=body, method="PUT", headers={"Content-Type": "application/json"}
        )
        with request.urlopen(req, timeout=self.timeout) as response:
            return _read_json_response(response)

    def handshake(self) -> MinskyBridgeStatus:
        try:
            object_type = self.get("/minsky/@type")
            model_time = self.get("/minsky/t")
            return MinskyBridgeStatus(
                configured=True,
                reachable=True,
                object_type=str(object_type) if object_type is not None else None,
                model_time=float(model_time) if isinstance(model_time, (int, float)) else None,
            )
        except (OSError, URLError, ValueError, json.JSONDecodeError) as exc:
            return MinskyBridgeStatus(configured=True, reachable=False, error=str(exc))

    def list_members(self, path: str = "/minsky") -> object:
        return self.get(f"{path.rstrip('/')}/@list")

    def signature(self, path: str) -> object:
        return self.get(f"{path.rstrip('/')}/@signature")

    def load_model(self, file_path: str) -> object:
        return self.put("/minsky/load", file_path)

    def save_model(self, file_path: str) -> object:
        return self.put("/minsky/save", file_path)

    def reset(self) -> object:
        return self.put("/minsky/reset", None)

    def step(self) -> object:
        return self.put("/minsky/step", None)

    def get_variable_value(self, variable_id: str) -> float:
        key = parse.quote(variable_id, safe=":._-")
        value = self.get(f"/minsky/variableValues/@elem/{key}/value")
        return float(value)

    def set_variable_value(self, variable_id: str, value: float) -> object:
        key = parse.quote(variable_id, safe=":._-")
        return self.put(f"/minsky/variableValues/@elem/{key}/value", float(value))


class MinskyTemplateBridge:
    """Synchronise Economy Lab values with a prebuilt Minsky .mky template.

    A template mapping deliberately makes variable semantics explicit instead
    of guessing Minsky object/schema internals. Keys are Economy Lab field names
    and values are Minsky variable IDs.
    """

    def __init__(self, client: MinskyRestClient, mapping: dict[str, str]):
        self.client = client
        self.mapping = dict(mapping)

    def push(self, values: dict[str, float]) -> dict[str, float]:
        pushed: dict[str, float] = {}
        for economy_key, minsky_id in self.mapping.items():
            if economy_key not in values:
                continue
            value = float(values[economy_key])
            self.client.set_variable_value(minsky_id, value)
            pushed[economy_key] = value
        return pushed

    def pull(self) -> dict[str, float]:
        return {
            economy_key: self.client.get_variable_value(minsky_id)
            for economy_key, minsky_id in self.mapping.items()
        }


def bridge_status(base_url: str | None = None) -> MinskyBridgeStatus:
    configured = bool((base_url or os.getenv("MINSKY_REST_URL", "")).strip())
    if not configured:
        return MinskyBridgeStatus(configured=False, reachable=False)
    return MinskyRestClient(base_url=base_url).handshake()
