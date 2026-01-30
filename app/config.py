import os
from pathlib import Path

# Base directory of the project
BASE_DIR = Path(__file__).resolve().parent.parent

# Location where the SAT JSON catalog files live.
# It can be overridden with the env var `CATALOGS_DIR`.
CATALOGS_DIR = Path(os.getenv("CATALOGS_DIR", BASE_DIR / "vendor" / "catalogos_sat_JSON")).resolve()

# Default limit to avoid returning the full catalog unintentionally.
DEFAULT_PAGE_LIMIT = int(os.getenv("DEFAULT_PAGE_LIMIT", "200"))

# Catalogs commonly needed to emitir un CFDI con complemento Carta Porte.
# The names map directly to the JSON files contained in the vendor repo.
CARTA_PORTE_CATALOGS = [
    "c_ClaveProdServ",
    "c_ClaveUnidad",
    "c_Pais",
    "c_CodigoPostal",
    "c_Moneda",
    "c_FormaPago",
    "c_MetodoPago",
    "c_RegimenFiscal",
    "c_UsoCFDI",
    "c_TipoDeComprobante",
    "c_TasaOCuota",
    "c_Impuesto",
    "c_TipoFactor",
    "c_TipoRelacion",
]
