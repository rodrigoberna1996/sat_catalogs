import os
import sys
from pathlib import Path
from fastapi.testclient import TestClient

# Ensure the application package is discoverable when running pytest without installation.
sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.main import app  # noqa: E402
from app.config import CARTA_PORTE_CATALOGS  # noqa: E402
from app.catalog_loader import load_catalog  # noqa: E402

client = TestClient(app)
TEST_INTERNAL_KEY = "test-internal-key"
os.environ["INTERNAL_API_KEY"] = TEST_INTERNAL_KEY
AUTH_HEADERS = {"x-internal-key": TEST_INTERNAL_KEY}


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_catalogs_endpoint_lists_items():
    resp = client.get("/catalogs", headers=AUTH_HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert "catalogs" in data
    assert len(data["catalogs"]) > 0


def test_carta_porte_endpoint_returns_subset():
    resp = client.get(
        "/carta-porte/catalogs?include_data=false",
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert "required_catalogs" in payload
    assert set(payload["required_catalogs"]).issubset(set(CARTA_PORTE_CATALOGS))
    assert "c_ConfigAutotransporte" in payload["required_catalogs"]
    assert "c_ConfigAutotransporte" not in payload["missing"]


def test_config_autotransporte_has_official_values():
    rows = load_catalog("c_ConfigAutotransporte")
    by_id = {row["id"]: row for row in rows}

    assert len(rows) == 34
    assert by_id["VL"]["remolque"] == "0,1"
    assert by_id["C2"]["remolque"] == "0"
    assert by_id["T3S2"]["remolque"] == "1"
    assert by_id["T3S2"]["numeroEjes"] == "5"
    assert by_id["T3S2"]["numeroLlantas"] == "18"
