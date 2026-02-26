# tests/test_database.py
import os
import tempfile
from database import ScanDatabase
from pattern_scanner import PatternResult


def test_create_scan():
    with tempfile.TemporaryDirectory() as tmpdir:
        db = ScanDatabase(os.path.join(tmpdir, "test.db"))
        scan_id = db.create_scan(watchlist="default", tickers=["AAPL", "MSFT"])
        assert isinstance(scan_id, str)
        assert len(scan_id) > 0


def test_update_scan_progress():
    with tempfile.TemporaryDirectory() as tmpdir:
        db = ScanDatabase(os.path.join(tmpdir, "test.db"))
        scan_id = db.create_scan(watchlist="default", tickers=["AAPL"])
        db.update_progress(scan_id, current=1, total=2, ticker="AAPL")
        progress = db.get_progress(scan_id)
        assert progress["current"] == 1
        assert progress["total"] == 2
        assert progress["ticker"] == "AAPL"


def test_save_and_get_results():
    with tempfile.TemporaryDirectory() as tmpdir:
        db = ScanDatabase(os.path.join(tmpdir, "test.db"))
        scan_id = db.create_scan(watchlist="default", tickers=["AAPL"])

        result = PatternResult(
            ticker="AAPL",
            pattern_type="Flat Base",
            confidence_score=80.0,
            buy_point=150.0,
            current_price=148.0,
            distance_to_pivot=-1.33,
            base_depth=10.0,
            base_length_weeks=7,
            volume_confirmation=True,
            above_50ma=True,
            above_200ma=True,
            rs_rating=85.0,
            pattern_details={"base_high": 152.0},
        )
        db.save_results(scan_id, [result])
        db.update_status(scan_id, "completed")

        results = db.get_results(scan_id)
        assert len(results) == 1
        assert results[0].ticker == "AAPL"
        assert results[0].confidence_score == 80.0

        status = db.get_scan_status(scan_id)
        assert status == "completed"
