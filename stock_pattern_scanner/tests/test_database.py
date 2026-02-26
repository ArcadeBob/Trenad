# tests/test_database.py


def test_create_scan(tmp_db):
    scan_id = tmp_db.create_scan(watchlist="default", tickers=["AAPL", "MSFT"])
    assert isinstance(scan_id, str)
    assert len(scan_id) > 0


def test_update_scan_progress(tmp_db):
    scan_id = tmp_db.create_scan(watchlist="default", tickers=["AAPL"])
    tmp_db.update_progress(scan_id, current=1, total=2, ticker="AAPL")
    progress = tmp_db.get_progress(scan_id)
    assert progress["current"] == 1
    assert progress["total"] == 2
    assert progress["ticker"] == "AAPL"


def test_save_and_get_results(tmp_db, make_pattern_result):
    scan_id = tmp_db.create_scan(watchlist="default", tickers=["AAPL"])
    result = make_pattern_result(
        confidence_score=80.0,
        pattern_details={"base_high": 152.0},
    )
    tmp_db.save_results(scan_id, [result])
    tmp_db.update_status(scan_id, "completed")

    results = tmp_db.get_results(scan_id)
    assert len(results) == 1
    assert results[0].ticker == "AAPL"
    assert results[0].confidence_score == 80.0

    assert tmp_db.get_scan_status(scan_id) == "completed"
