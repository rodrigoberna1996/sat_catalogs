# SAT Catálogos Microservicio

Servicio REST en Python 3.11+ (FastAPI) que expone los catálogos CFDI publicados en el repositorio [bambucode/catalogos_sat_JSON](https://github.com/bambucode/catalogos_sat_JSON) (CFDI 3.3/4.0), más algunos catálogos del **complemento Carta Porte** que no forman parte de ese mirror y se agregaron manualmente (ver sección "Datos de origen"). Incluye un endpoint que agrupa los catálogos más comunes para emitir un CFDI con complemento Carta Porte.

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

La mayoría de los archivos provienen del mirror [bambucode/catalogos_sat_JSON](https://github.com/bambucode/catalogos_sat_JSON) (catálogos generales de CFDI 3.3/4.0). Esa carpeta **dejó de ser un git submodule** (ver commit `a1544fa`) y ahora son archivos versionados directamente en este repo, así que ya no aplica hacer `git pull` dentro de `vendor/catalogos_sat_JSON`; para actualizarlos hay que reemplazar los JSON manualmente.

Catálogos agregados manualmente porque pertenecen al **complemento Carta Porte** (no están en el mirror de CFDI 3.3/4.0):
- `c_ConfigAutotransporte` — 34 configuraciones vehiculares vigentes, incluyendo número de ejes, llantas y regla de remolque. Fuente: [XLS oficial del SAT para Carta Porte 3.1](http://omawww.sat.gob.mx/tramitesyservicios/Paginas/documentos/CatalogosCartaPorte31.xls), publicado el 17/06/2024 y vigente desde el 17/07/2024.
- `c_SubTipoRem` — Subtipo de remolque/semirremolque. Fuente: catálogo oficial del SAT para el complemento Carta Porte (verificado contra [fiscalapi.com](https://docs.fiscalapi.com/catalogs-info/carta-porte-31) y [gncys.com.mx](https://gncys.com.mx/complementos/cartaporte/c_subtiporem.aspx)).

> `c_TipoRem` **no existe** como catálogo oficial del SAT (no aparece en ninguna fuente oficial ni en proyectos de referencia como `phpcfdi/resources-sat-catalogs`). El único campo real que usa el complemento Carta Porte en el nodo `Remolque` es `SubTipoRem`; `tipo_remolque` en `adrh_logistics` es un campo de texto libre interno, no un catálogo del SAT. No se agregó ningún archivo `c_TipoRem.json` para evitar hacer pasar un valor inventado como catálogo oficial.

## Conjunto sugerido para Carta Porte
Los catálogos definidos en `app/config.py::CARTA_PORTE_CATALOGS` incluyen:
`c_ClaveProdServ`, `c_ClaveUnidad`, `c_Pais`, `c_CodigoPostal`, `c_Moneda`, `c_FormaPago`, `c_MetodoPago`, `c_RegimenFiscal`, `c_UsoCFDI`, `c_TipoDeComprobante`, `c_TasaOCuota`, `c_Impuesto`, `c_TipoFactor`, `c_TipoRelacion`, `c_ObjetoImp`, `c_ConfigAutotransporte`, `c_SubTipoRem`.
Solo se devuelven los que existan físicamente en la carpeta de datos, y se indica cuáles faltan en `missing`.

## Notas
- El microservicio solo lee archivos; no modifica los catálogos.
- Los catálogos de CFDI 3.3/4.0 (bambucode) se reemplazan copiando los JSON nuevos sobre `vendor/catalogos_sat_JSON/`; los de Carta Porte (`c_SubTipoRem`, etc.) se mantienen y actualizan manualmente en este repo.
