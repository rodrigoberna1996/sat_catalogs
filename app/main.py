import logging
from logging.config import dictConfig
from typing import List

from dotenv import load_dotenv
load_dotenv()

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIASGIMiddleware

from .config import CARTA_PORTE_CATALOGS, DEFAULT_PAGE_LIMIT
from .catalog_loader import CatalogNotFound, filter_rows, list_catalogs, load_catalog
from .internal_auth import require_internal_key
from .limiter import limiter


def _configure_logging() -> None:
    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
                    "datefmt": "%Y-%m-%dT%H:%M:%S",
                }
            },
            "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "default"}},
            "loggers": {
                "sat_catalogs": {"handlers": ["console"], "level": "INFO", "propagate": False},
            },
            "root": {"handlers": ["console"], "level": "WARNING"},
        }
    )


_configure_logging()

app = FastAPI(
    title="SAT Catalogos API",
    version="0.1.0",
    description=(
        "Microservicio en Python para exponer en JSON los catalogos CFDI "
        "incluyendo los necesarios para complementar Carta Porte."
    ),
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIASGIMiddleware)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logging.getLogger(__name__).error("Error no manejado en %s", request.url.path, exc_info=exc)
    return JSONResponse(status_code=500, content={"detail": "Error interno del servidor."})


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/catalogs", dependencies=[Depends(require_internal_key)])
def catalogs():
    """Listar los catálogos disponibles y su número de filas."""
    items = [{"name": name, "entries": count} for name, count in list_catalogs()]
    return {"catalogs": items}


@app.get("/catalogs/{catalog_name}", dependencies=[Depends(require_internal_key)])
def get_catalog(
    catalog_name: str,
    q: str | None = Query(None, description="Búsqueda libre (case-insensitive)"),
    filter: List[str] = Query(  # type: ignore[assignment]
        [],
        description="Filtros exactos como campo:valor (se puede repetir el parámetro)",
    ),
    limit: int = Query(
        DEFAULT_PAGE_LIMIT,
        ge=1,
        le=10_000,
        description="Máximo de filas a devolver después de filtros",
    ),
):
    try:
        data = load_catalog(catalog_name)
    except CatalogNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    filters: list[tuple[str, str]] = []
    for raw in filter:
        if ":" not in raw:
            raise HTTPException(
                status_code=400,
                detail=f"Filtro inválido '{raw}', usa formato campo:valor",
            )
        field, value = raw.split(":", 1)
        filters.append((field, value))

    filtered = filter_rows(data, query=q, filters=filters)

    return {
        "catalog": catalog_name,
        "total": len(data),
        "count": len(filtered[:limit]),
        "data": filtered[:limit],
    }


@app.get("/carta-porte/catalogs", dependencies=[Depends(require_internal_key)])
@limiter.limit("30/minute")
def carta_porte_catalogs(
    request: Request,
    include_data: bool = Query(
        True, description="Incluir los registros de cada catálogo (no solo los nombres)"
    ),
    limit_per_catalog: int = Query(
        DEFAULT_PAGE_LIMIT,
        ge=1,
        le=10_000,
        description="Máximo de filas por catálogo cuando include_data es true",
    ),
):
    """
    Entrega la lista de catálogos que típicamente se requieren para emitir un
    CFDI con complemento Carta Porte. Solo incluye catálogos presentes en la
    fuente de datos local.
    """
    available = {name.lower(): name for name, _ in list_catalogs()}
    selected = [available[name.lower()] for name in CARTA_PORTE_CATALOGS if name.lower() in available]

    payload = {"required_catalogs": selected, "missing": sorted(set(CARTA_PORTE_CATALOGS) - set(selected))}

    if not include_data:
        return payload

    catalogs_data = {}
    for name in selected:
        data = load_catalog(name)
        catalogs_data[name] = {
            "total": len(data),
            "data": data[:limit_per_catalog],
        }
    payload["catalogs"] = catalogs_data
    return JSONResponse(payload)


@app.get("/", include_in_schema=False)
def root():
    return {
        "message": "Consulta /catalogs para ver los catálogos disponibles. "
        "Usa /carta-porte/catalogs para obtener el conjunto recomendado para Carta Porte.",
    }
