from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path

from economy_lab.core.schemas import DataFetchRequest, DataProvenanceRecord, EconomicObservation, EconomicSeriesResponse
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


def _canonical_observations_hash(observations: list[EconomicObservation]) -> str:
    """SHA-256 of a canonical JSON representation of sorted observations."""
    canonical = json.dumps(
        [{"date": o.date, "value": o.value} for o in sorted(observations, key=lambda x: x.date)],
        sort_keys=True,
        ensure_ascii=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _build_provenance(
    source_id: str,
    series_id: str,
    observations: list[EconomicObservation],
    fetched_at: str,
    frequency: str,
    unit: str,
) -> DataProvenanceRecord:
    dates = sorted(o.date for o in observations)
    return DataProvenanceRecord(
        source_id=source_id,
        series_id=series_id,
        content_hash=_canonical_observations_hash(observations),
        retrieved_at=fetched_at,
        observation_start=dates[0] if dates else None,
        observation_end=dates[-1] if dates else None,
        frequency=frequency or None,
        units=unit or None,
    )


def fetch_economic_series(query: DataFetchRequest, *, fetcher=default_json_fetcher) -> EconomicSeriesResponse:
    key = _cache_key(query)
    path = _cache_dir() / f"{key}.json"
    if query.use_cache and not query.refresh and path.exists():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            response = EconomicSeriesResponse.model_validate(payload)
            expected = _build_provenance(
                source_id=response.source,
                series_id=response.series_id,
                observations=response.observations,
                fetched_at=response.fetched_at,
                frequency=response.frequency,
                unit=response.unit,
            )
            if response.provenance is not None and response.provenance != expected:
                raise ValueError("cached provenance is inconsistent with response data")
            if response.provenance is None:
                # Legacy cache entry without provenance — derive and regrave.
                response = response.model_copy(update={"provenance": expected})
                path.write_text(response.model_dump_json(indent=2), encoding="utf-8")
            return response.model_copy(update={"cached": True})
        except Exception:
            path.unlink(missing_ok=True)

    connector = CONNECTORS.get(query.source)
    if connector is None:
        raise ValueError(f"Unsupported data source: {query.source}")
    result = connector.fetch(query, fetcher=fetcher)
    if not result.observations:
        raise ValueError("The data source returned no numeric observations for this query")
    observations = [EconomicObservation(**item) for item in result.observations]
    fetched_at = datetime.now(timezone.utc).isoformat()
    provenance = _build_provenance(
        source_id=query.source,
        series_id=query.series_id,
        observations=observations,
        fetched_at=fetched_at,
        frequency=result.frequency,
        unit=result.unit,
    )
    response = EconomicSeriesResponse(
        source=query.source,
        series_id=query.series_id,
        title=result.title,
        unit=result.unit,
        frequency=result.frequency,
        fetched_at=fetched_at,
        cached=False,
        request_url=result.request_url,
        metadata=result.metadata,
        observations=observations,
        provenance=provenance,
        warning="External observations are evidence inputs; definitions/frequencies must be reviewed before calibration.",
    )
    if query.use_cache:
        path.write_text(response.model_dump_json(indent=2), encoding="utf-8")
    return response
