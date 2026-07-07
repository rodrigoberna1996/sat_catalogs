import logging
import re
from logging.config import dictConfig
from typing import List

from dotenv import load_dotenv
load_dotenv()

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIASGIMiddleware

from .config import CARTA_PORTE_CATALOGS, DEFAULT_PAGE_LIMIT
from .catalog_loader import CatalogNotFound, filter_rows, list_catalogs, load_catalog
from .internal_auth import require_internal_key
from .limiter import limiter

# c_CodigoPostal usa "DIF" para CDMX; c_Estado y C_Municipio usan "CMX".
_ESTADO_ALIAS: dict[str, str] = {"DIF": "CMX"}

# SAT catalogs are static vendor files that never change at runtime.
# Cache responses aggressively: 1 hour in shared caches, 5 min in browser.
# Stale-while-revalidate lets clients serve stale while re-validating in background.
_CATALOG_CACHE_CONTROL = "public, max-age=300, s-maxage=3600, stale-while-revalidate=86400"
# Large volatile catalogs (CP lookup, product search) get a shorter window.
_SEARCH_CACHE_CONTROL = "public, max-age=60, s-maxage=600, stale-while-revalidate=3600"


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
    version="0.2.0",
    description=(
        "Microservicio en Python para exponer en JSON los catalogos CFDI "
        "incluyendo los necesarios para complementar Carta Porte."
    ),
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIASGIMiddleware)

# Compress responses >= 1 KB automatically.
app.add_middleware(GZipMiddleware, minimum_size=1024)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logging.getLogger(__name__).error("Error no manejado en %s", request.url.path, exc_info=exc)
    return JSONResponse(status_code=500, content={"detail": "Error interno del servidor."})


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/catalogs", dependencies=[Depends(require_internal_key)])
def catalogs(response: Response):
    """Listar los catálogos disponibles y su número de filas."""
    items = [{"name": name, "entries": count} for name, count in list_catalogs()]
    response.headers["Cache-Control"] = _CATALOG_CACHE_CONTROL
    return {"catalogs": items}


@app.get("/catalogs/{catalog_name}", dependencies=[Depends(require_internal_key)])
def get_catalog(
    catalog_name: str,
    response: Response,
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
    offset: int = Query(
        0,
        ge=0,
        description="Número de filas a omitir (para paginación)",
    ),
):
    # Validate catalog exists before heavy processing.
    try:
        total_rows = len(load_catalog(catalog_name))
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

    page, total_filtered = filter_rows(
        catalog_name,
        query=q,
        filters=filters or None,
        offset=offset,
        limit=limit,
    )

    # Strip internal '_search' blob before sending to the client.
    clean_page = [{k: v for k, v in row.items() if not k.startswith("_")} for row in page]

    # Use shorter TTL when there is an active search query.
    response.headers["Cache-Control"] = _SEARCH_CACHE_CONTROL if q else _CATALOG_CACHE_CONTROL

    return {
        "catalog": catalog_name,
        "total": total_rows,
        "total_filtered": total_filtered,
        "count": len(clean_page),
        "offset": offset,
        "data": clean_page,
    }


@app.get("/carta-porte/catalogs", dependencies=[Depends(require_internal_key)])
@limiter.limit("30/minute")
def carta_porte_catalogs(
    request: Request,
    response: Response,
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

    payload: dict = {
        "required_catalogs": selected,
        "missing": sorted(set(CARTA_PORTE_CATALOGS) - set(selected)),
    }

    if not include_data:
        response.headers["Cache-Control"] = _CATALOG_CACHE_CONTROL
        return payload

    catalogs_data = {}
    for name in selected:
        page, total_filtered = filter_rows(name, limit=limit_per_catalog)
        clean_page = [{k: v for k, v in row.items() if not k.startswith("_")} for row in page]
        catalogs_data[name] = {
            "total": len(load_catalog(name)),
            "total_filtered": total_filtered,
            "data": clean_page,
        }
    payload["catalogs"] = catalogs_data

    response.headers["Cache-Control"] = _CATALOG_CACHE_CONTROL
    return JSONResponse(payload, headers={"Cache-Control": _CATALOG_CACHE_CONTROL})


@app.get("/ubicacion/{cp}", dependencies=[Depends(require_internal_key)])
@limiter.limit("300/minute")
def get_ubicacion_por_cp(cp: str, request: Request, response: Response):
    """
    Dado un CP de 5 dígitos devuelve en una sola llamada:
    - Claves y nombres de estado, municipio y localidad.
    - Lista de colonias del catálogo c_Colonia (clave + nombre).
    - Normaliza DIF → CMX para compatibilidad con todos los catálogos.
    Optimizado para autocompletar formularios de Carta Porte desde el frontend.
    """
    if not re.fullmatch(r"\d{5}", cp):
        raise HTTPException(status_code=422, detail="El CP debe tener exactamente 5 dígitos.")

    # 1. Lookup exacto en c_CodigoPostal por campo id.
    try:
        cp_rows, _ = filter_rows("c_CodigoPostal", filters=[("id", cp)], limit=1)
    except CatalogNotFound:
        raise HTTPException(status_code=503, detail="Catálogo c_CodigoPostal no disponible.")

    if not cp_rows:
        raise HTTPException(status_code=404, detail=f"Código postal '{cp}' no encontrado.")

    cp_data = cp_rows[0]
    raw_estado = str(cp_data.get("c_Estado") or "").upper()
    c_estado = _ESTADO_ALIAS.get(raw_estado, raw_estado)
    c_municipio = str(cp_data.get("c_Municipio") or "")
    c_localidad = str(cp_data.get("c_Localidad") or "")

    # 2. Nombre del estado.
    estado_nombre = ""
    try:
        edo_rows, _ = filter_rows("c_Estado", filters=[("id", c_estado)], limit=1)
        if edo_rows:
            estado_nombre = str(edo_rows[0].get("nombreDelEstado") or "")
    except CatalogNotFound:
        pass

    # 3. Nombre del municipio (clave compuesta estado + municipio).
    municipio_nombre = ""
    if c_estado and c_municipio:
        try:
            mun_rows, _ = filter_rows(
                "C_Municipio",
                filters=[("c_Estado", c_estado), ("c_Municipio", c_municipio)],
                limit=1,
            )
            if mun_rows:
                municipio_nombre = str(mun_rows[0].get("descripcion") or "")
        except CatalogNotFound:
            pass

    # 4. Nombre de la localidad (opcional — muchos CP tienen localidad vacía).
    localidad_nombre = ""
    if c_estado and c_localidad:
        try:
            loc_rows, _ = filter_rows(
                "C_Localidad",
                filters=[("c_Estado", c_estado), ("c_Localidad", c_localidad)],
                limit=1,
            )
            if loc_rows:
                localidad_nombre = str(loc_rows[0].get("descripcion") or "")
        except CatalogNotFound:
            pass

    # 5. Colonias del CP (hasta 500; un CP típico tiene 1–30 colonias).
    colonias: list[dict] = []
    try:
        col_rows, _ = filter_rows("c_Colonia", filters=[("c_CodigoPostal", cp)], limit=500)
        colonias = [
            {"clave": r["c_Colonia"], "nombre": r["nombre"]}
            for r in col_rows
        ]
    except CatalogNotFound:
        pass

    response.headers["Cache-Control"] = _CATALOG_CACHE_CONTROL
    return {
        "codigoPostal": cp,
        "estadoClave": c_estado,
        "estadoNombre": estado_nombre,
        "municipioClave": c_municipio,
        "municipioNombre": municipio_nombre,
        "localidadClave": c_localidad or None,
        "localidadNombre": localidad_nombre or None,
        "pais": "MEX",
        "husoHorario": str(cp_data.get("referenciasDelHusoHorario") or ""),
        "colonias": colonias,
    }


@app.get("/", include_in_schema=False)
def root():
    return {
        "message": "Consulta /catalogs para ver los catálogos disponibles. "
        "Usa /carta-porte/catalogs para obtener el conjunto recomendado para Carta Porte.",
    }
