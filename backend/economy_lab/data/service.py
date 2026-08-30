from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path

from economy_lab.core.schemas import DataFetchRequest, EconomicObservation, EconomicSeriesResponse
from .connectors import CONNECTORS, default_json_fetcher


def _cache_dir() -> Path:
    configured = os.getenv("ECONOMY_LAB_DATA_CACHE")
    base = Path(configured).expanduser() if configured else Path.home() / ".economy-lab" / "data-cache"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _cache_key(query: DataFetchRequest) -> str:
    payload = query.model_dump(mode="json", exclude={"refresh", "use_cache", "timeout_seconds"})
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=True).encode()).hexdigest()[:24]


def cache_status() -> dict[str, object]:
    base = _cache_dir()
    files = list(base.glob("*.json"))
    return {"directory": str(base), "entries": len(files), "bytes": sum(p.stat().st_size for p in files)}


def fetch_economic_series(query: DataFetchRequest, *, fetcher=default_json_fetcher) -> EconomicSeriesResponse:
    key = _cache_key(query)
    path = _cache_dir() / f"{key}.json"
    if query.use_cache and not query.refresh and path.exists():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            response = EconomicSeriesResponse.model_validate(payload)
            return response.model_copy(update={"cached": True})
        except Exception:
            path.unlink(missing_ok=True)

    connector = CONNECTORS.get(query.source)
    if connector is None:
        raise ValueError(f"Unsupported data source: {query.source}")
    result = connector.fetch(query, fetcher=fetcher)
    if not result.observations:
        raise ValueError("The data source returned no numeric observations for this query")
    response = EconomicSeriesResponse(
        source=query.source,
        series_id=query.series_id,
        title=result.title,
        unit=result.unit,
        frequency=result.frequency,
        fetched_at=datetime.now(timezone.utc).isoformat(),
        cached=False,
        request_url=result.request_url,
        metadata=result.metadata,
        observations=[EconomicObservation(**item) for item in result.observations],
        warning="External observations are evidence inputs; definitions/frequencies must be reviewed before calibration.",
    )
    if query.use_cache:
        path.write_text(response.model_dump_json(indent=2), encoding="utf-8")
    return response
