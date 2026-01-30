import sys
from pathlib import Path
from fastapi.testclient import TestClient

# Ensure the application package is discoverable when running pytest without installation.
sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.main import app  # noqa: E402
from app.config import CARTA_PORTE_CATALOGS  # noqa: E402

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_catalogs_endpoint_lists_items():
    resp = client.get("/catalogs")
    assert resp.status_code == 200
    data = resp.json()
    assert "catalogs" in data
    assert len(data["catalogs"]) > 0


def test_carta_porte_endpoint_returns_subset():
    resp = client.get("/carta-porte/catalogs?include_data=false")
    assert resp.status_code == 200
    payload = resp.json()
    assert "required_catalogs" in payload
    assert set(payload["required_catalogs"]).issubset(set(CARTA_PORTE_CATALOGS))
