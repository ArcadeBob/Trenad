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


def test_create_backtest(tmp_db):
    bt_id = tmp_db.create_backtest(
        watchlist="default",
        tickers=["AAPL", "MSFT"],
        stop_loss_pct=7.0,
        profit_target_pct=20.0,
        min_confidence=40.0,
    )
    assert isinstance(bt_id, str)
    assert len(bt_id) > 0


def test_backtest_progress(tmp_db):
    bt_id = tmp_db.create_backtest(
        watchlist="default", tickers=["AAPL"],
        stop_loss_pct=7.0, profit_target_pct=20.0, min_confidence=40.0,
    )
    tmp_db.update_backtest_progress(bt_id, current=5, total=50)
    progress = tmp_db.get_backtest_progress(bt_id)
    assert progress["current"] == 5
    assert progress["total"] == 50
    assert progress["status"] == "running"


def test_save_and_get_backtest_trades(tmp_db):
    bt_id = tmp_db.create_backtest(
        watchlist="default", tickers=["AAPL"],
        stop_loss_pct=7.0, profit_target_pct=20.0, min_confidence=40.0,
    )
    trades = [
        {
            "ticker": "AAPL",
            "pattern_type": "Flat Base",
            "confidence_score": 72.0,
            "detection_date": "2025-06-15",
            "entry_date": "2025-06-18",
            "entry_price": 150.0,
            "exit_date": "2025-07-10",
            "exit_price": 180.0,
            "exit_reason": "target",
            "pnl_pct": 20.0,
            "market_regime": "confirmed_uptrend",
        },
    ]
    tmp_db.save_backtest_trades(bt_id, trades)
    tmp_db.update_backtest_status(bt_id, "completed")
    tmp_db.save_backtest_summary(bt_id, total_trades=1, win_rate=100.0, profit_factor=999.0)

    result = tmp_db.get_backtest_trades(bt_id)
    assert len(result) == 1
    assert result[0]["ticker"] == "AAPL"
    assert result[0]["pnl_pct"] == 20.0

    summary = tmp_db.get_backtest_summary(bt_id)
    assert summary["total_trades"] == 1
    assert summary["win_rate"] == 100.0
    assert summary["status"] == "completed"
