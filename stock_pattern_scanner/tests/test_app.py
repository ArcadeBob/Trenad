# tests/test_app.py
import os
import tempfile

_test_db_dir = tempfile.mkdtemp()
os.environ["SCANNER_DB_PATH"] = os.path.join(_test_db_dir, "test_scanner_app.db")

from fastapi.testclient import TestClient
from app import app

client = TestClient(app)


def test_dashboard_loads():
    response = client.get("/")
    assert response.status_code == 200
    assert "Stock Pattern Scanner" in response.text


def test_get_watchlists():
    response = client.get("/api/watchlists")
    assert response.status_code == 200
    data = response.json()
    assert "default" in data
    assert "sp500" in data
    assert "nasdaq100" in data


def test_start_scan():
    response = client.post("/api/scan", json={
        "watchlist": "custom",
        "tickers": ["AAPL", "MSFT"],
    })
    assert response.status_code == 200
    data = response.json()
    assert "scan_id" in data


def test_get_results_pending():
    response = client.get("/api/scan/nonexistent/results")
    assert response.status_code == 200
