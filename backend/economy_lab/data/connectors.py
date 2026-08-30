from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from typing import Callable
from urllib.parse import urlencode, quote
from urllib.request import Request, urlopen


JsonFetcher = Callable[[str, int], object]


def default_json_fetcher(url: str, timeout: int) -> object:
    request = Request(url, headers={"User-Agent": "EconomyLab/2.4", "Accept": "application/json"})
    with urlopen(request, timeout=timeout) as response:  # noqa: S310 - fixed public API endpoints
        return json.loads(response.read().decode("utf-8"))


def _iso_date(value: str) -> str:
    text = str(value).strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f"):
        try:
            return datetime.strptime(text[:26], fmt).date().isoformat()
        except ValueError:
            pass
    if len(text) >= 10 and text[4] == "-":
        return text[:10]
    return text


def _float(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(" ", "")
    if not text or text in {"...", "..", "-"}:
        return None
    if "," in text and "." not in text:
        text = text.replace(",", ".")
    elif "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


@dataclass(frozen=True)
class ConnectorResult:
    title: str
    unit: str
    frequency: str
    observations: list[dict[str, object]]
    metadata: dict[str, object]
    request_url: str


class BCBSGSConnector:
    source = "bcb_sgs"

    def fetch(self, query, fetcher: JsonFetcher = default_json_fetcher) -> ConnectorResult:
        params = {"formato": "json"}
        if query.start_date:
            params["dataInicial"] = datetime.fromisoformat(query.start_date).strftime("%d/%m/%Y")
        if query.end_date:
            params["dataFinal"] = datetime.fromisoformat(query.end_date).strftime("%d/%m/%Y")
        url = f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{quote(query.series_id)}/dados?{urlencode(params)}"
        payload = fetcher(url, query.timeout_seconds)
        if not isinstance(payload, list):
            raise ValueError("BCB SGS returned an unexpected payload")
        obs = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            value = _float(item.get("valor"))
            if value is None:
                continue
            obs.append({"date": _iso_date(str(item.get("data", ""))), "value": value})
        return ConnectorResult(
            title=query.title or f"BCB SGS {query.series_id}", unit=query.unit or "", frequency=query.frequency or "unknown",
            observations=obs, metadata={"sgs_code": query.series_id}, request_url=url,
        )


class WorldBankConnector:
    source = "world_bank"

    def fetch(self, query, fetcher: JsonFetcher = default_json_fetcher) -> ConnectorResult:
        country = str(query.source_options.get("country", "BRA"))
        params: dict[str, str] = {"format": "json", "per_page": "20000"}
        if query.start_date or query.end_date:
            start = (query.start_date or "1960-01-01")[:4]
            end = (query.end_date or datetime.now().date().isoformat())[:4]
            params["date"] = f"{start}:{end}"
        url = f"https://api.worldbank.org/v2/country/{quote(country)}/indicator/{quote(query.series_id)}?{urlencode(params)}"
        payload = fetcher(url, query.timeout_seconds)
        if not isinstance(payload, list) or len(payload) < 2 or not isinstance(payload[1], list):
            raise ValueError("World Bank returned an unexpected payload")
        rows = payload[1]
        obs = []
        title = query.title or query.series_id
        unit = query.unit or ""
        for item in rows:
            if not isinstance(item, dict):
                continue
            value = _float(item.get("value"))
            if value is None:
                continue
            year = str(item.get("date", ""))
            date = f"{year}-01-01" if len(year) == 4 and year.isdigit() else year
            obs.append({"date": date, "value": value})
            indicator = item.get("indicator")
            if isinstance(indicator, dict) and indicator.get("value"):
                title = query.title or str(indicator["value"])
        obs.sort(key=lambda x: str(x["date"]))
        return ConnectorResult(
            title=title, unit=unit, frequency=query.frequency or "annual", observations=obs,
            metadata={"country": country, "indicator": query.series_id}, request_url=url,
        )


class IPEADataConnector:
    source = "ipeadata"

    def fetch(self, query, fetcher: JsonFetcher = default_json_fetcher) -> ConnectorResult:
        code = query.series_id.replace("'", "")
        url = f"https://www.ipeadata.gov.br/api/odata4/ValoresSerie(SERCODIGO='{quote(code)}')"
        payload = fetcher(url, query.timeout_seconds)
        if not isinstance(payload, dict) or not isinstance(payload.get("value"), list):
            raise ValueError("Ipeadata returned an unexpected payload")
        obs = []
        levels: set[str] = set()
        for item in payload["value"]:
            if not isinstance(item, dict):
                continue
            value = _float(item.get("VALVALOR"))
            if value is None:
                continue
            date = _iso_date(str(item.get("VALDATA", "")))
            if query.start_date and date < query.start_date:
                continue
            if query.end_date and date > query.end_date:
                continue
            obs.append({"date": date, "value": value})
            if item.get("NIVNOME"):
                levels.add(str(item.get("NIVNOME")))
        obs.sort(key=lambda x: str(x["date"]))
        return ConnectorResult(
            title=query.title or f"Ipeadata {code}", unit=query.unit or "", frequency=query.frequency or "unknown",
            observations=obs, metadata={"series_code": code, "levels": sorted(levels)}, request_url=url,
        )


def _walk_ibge_series(node: object, out: list[dict[str, object]]) -> None:
    if isinstance(node, dict):
        serie = node.get("serie")
        if isinstance(serie, dict):
            for period, raw in serie.items():
                value = _float(raw)
                if value is not None:
                    out.append({"date": str(period), "value": value})
        for value in node.values():
            _walk_ibge_series(value, out)
    elif isinstance(node, list):
        for value in node:
            _walk_ibge_series(value, out)


class IBGESidraConnector:
    source = "ibge_sidra"

    def fetch(self, query, fetcher: JsonFetcher = default_json_fetcher) -> ConnectorResult:
        aggregate = quote(query.series_id)
        periods = quote(str(query.source_options.get("periods", "-12")), safe="-;")
        variable = quote(str(query.source_options.get("variable", "all")), safe="all;")
        localities = str(query.source_options.get("localities", "N1[all]"))
        params = {"localidades": localities, "view": str(query.source_options.get("view", "flat"))}
        classification = query.source_options.get("classification")
        if classification:
            params["classificacao"] = str(classification)
        url = f"https://servicodados.ibge.gov.br/api/v3/agregados/{aggregate}/periodos/{periods}/variaveis/{variable}?{urlencode(params)}"
        payload = fetcher(url, query.timeout_seconds)
        if not isinstance(payload, list):
            raise ValueError("IBGE returned an unexpected payload")
        observations: list[dict[str, object]] = []
        _walk_ibge_series(payload, observations)
        # The same period can appear in multiple classifications/localities; preserve all in metadata but
        # use the first value per period for the normalized scalar series requested by the current contract.
        unique: dict[str, float] = {}
        for row in observations:
            unique.setdefault(str(row["date"]), float(row["value"]))
        obs = [{"date": key, "value": value} for key, value in sorted(unique.items())]
        title = query.title or f"IBGE agregado {query.series_id}"
        unit = query.unit or ""
        if payload and isinstance(payload[0], dict):
            title = query.title or str(payload[0].get("variavel") or payload[0].get("id") or title)
            unit = query.unit or str(payload[0].get("unidade") or "")
        return ConnectorResult(
            title=title, unit=unit, frequency=query.frequency or "unknown", observations=obs,
            metadata={"aggregate": query.series_id, "periods": str(query.source_options.get("periods", "-12")), "variable": str(query.source_options.get("variable", "all")), "localities": localities, "raw_series_count": len(observations)},
            request_url=url,
        )


CONNECTORS = {
    "bcb_sgs": BCBSGSConnector(),
    "ibge_sidra": IBGESidraConnector(),
    "world_bank": WorldBankConnector(),
    "ipeadata": IPEADataConnector(),
}
