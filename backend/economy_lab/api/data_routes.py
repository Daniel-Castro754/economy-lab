import logging

from fastapi import APIRouter, HTTPException

from economy_lab.core.schemas import (
    DataFetchRequest,
    EconomicSeriesResponse,
    DataSourceCatalogItem,
    DataCacheStatus,
)
from economy_lab.data import data_catalog, fetch_economic_series, cache_status

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/data/catalog", response_model=list[DataSourceCatalogItem])
def economic_data_catalog() -> list[DataSourceCatalogItem]:
    return [DataSourceCatalogItem(**item) for item in data_catalog()]


@router.get("/data/cache/status", response_model=DataCacheStatus)
def economic_data_cache_status() -> DataCacheStatus:
    return DataCacheStatus(**cache_status())


@router.post("/data/fetch", response_model=EconomicSeriesResponse)
def economic_data_fetch(request: DataFetchRequest) -> EconomicSeriesResponse:
    try:
        return fetch_economic_series(request)
    except Exception as exc:
        logger.exception("External data source failed")
        raise HTTPException(status_code=502, detail="External data source failed") from exc
