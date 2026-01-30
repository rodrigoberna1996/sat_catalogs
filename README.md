# SAT Catálogos Microservicio

Servicio REST en Python 3.11+ (FastAPI) que expone los catálogos CFDI publicados en el repositorio [bambucode/catalogos_sat_JSON](https://github.com/bambucode/catalogos_sat_JSON). Incluye un endpoint que agrupa los catálogos más comunes para emitir un CFDI con complemento Carta Porte.

## Requisitos
- Python 3.11 o superior
- pip

## Puesta en marcha
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

El servicio queda disponible en `http://127.0.0.1:8000`.

## Endpoints
- `GET /health` — estado básico.
- `GET /catalogs` — lista catálogos disponibles y número de filas.
- `GET /catalogs/{nombre}` — devuelve un catálogo. Parámetros:
  - `q`: búsqueda libre (contiene).
  - `filter=campo:valor`: se puede repetir para varios filtros exactos.
  - `limit`: número máximo de filas a devolver (default 200).
- `GET /carta-porte/catalogs` — devuelve el conjunto recomendado de catálogos para complementar Carta Porte.
  - `include_data` (bool, default `true`): incluir registros.
  - `limit_per_catalog` (default 200): máximo de filas por catálogo.

### Ejemplos
```bash
# Listar catálogos
curl http://127.0.0.1:8000/catalogs

# Buscar el catálogo de productos/servicios por texto libre
curl "http://127.0.0.1:8000/catalogs/c_ClaveProdServ?q=transporte"

# Filtrar códigos postales por estado y municipio
curl "http://127.0.0.1:8000/catalogs/c_CodigoPostal?filter=c_Estado:AGU&filter=c_Municipio:001&limit=50"

# Obtener catálogos relevantes para Carta Porte (solo nombres)
curl "http://127.0.0.1:8000/carta-porte/catalogs?include_data=false"
```

## Datos de origen
Los JSON se encuentran en `vendor/catalogos_sat_JSON/`. Si deseas usar una ruta distinta, exporta la variable de entorno `CATALOGS_DIR=/ruta/a/catalogos`.

## Conjunto sugerido para Carta Porte
Los catálogos definidos en `app/config.py::CARTA_PORTE_CATALOGS` incluyen:
`c_ClaveProdServ`, `c_ClaveUnidad`, `c_Pais`, `c_CodigoPostal`, `c_Moneda`, `c_FormaPago`, `c_MetodoPago`, `c_RegimenFiscal`, `c_UsoCFDI`, `c_TipoDeComprobante`, `c_TasaOCuota`, `c_Impuesto`, `c_TipoFactor`, `c_TipoRelacion`.
Solo se devuelven los que existan físicamente en la carpeta de datos, y se indica cuáles faltan en `missing`.

## Notas
- El microservicio solo lee archivos; no modifica los catálogos.
- Puedes actualizar los JSON ejecutando `git pull` dentro de `vendor/catalogos_sat_JSON` o apuntando `CATALOGS_DIR` a otra copia.
