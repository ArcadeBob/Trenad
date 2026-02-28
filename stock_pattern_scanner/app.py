"""FastAPI web application for the stock pattern scanner."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import tempfile
import threading
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse, FileResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from constants import DEFAULT_MAX_WORKERS, MIN_DATA_POINTS, SSE_POLL_INTERVAL
from database import ScanDatabase
from backtest import BacktestEngine, BacktestConfig, compute_metrics
from excel_export import export_to_excel
from market_regime import MarketRegime
from pattern_scanner import PatternDetector, StockScanner
from ticker_lists import (
    DEFAULT_GROWTH_WATCHLIST,
    resolve_watchlist,
)

logger = logging.getLogger(__name__)

DB_PATH = os.environ.get("SCANNER_DB_PATH", "scanner.db")
db = ScanDatabase(DB_PATH)

templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))


app = FastAPI(title="Stock Pattern Scanner")


class ScanRequest(BaseModel):
    watchlist: str = "default"
    tickers: Optional[list[str]] = None
    min_score: float = 0


class BacktestRequest(BaseModel):
    watchlist: str = "default"
    tickers: Optional[list[str]] = None
    stop_loss_pct: float = 7.0
    profit_target_pct: float = 20.0
    min_confidence: float = 40.0


def _run_scan(scan_id: str, tickers: list[str], min_score: float):
    """Run scan in a background thread."""
    def progress_cb(current: int, total: int, ticker: str):
        db.update_progress(scan_id, current, total, ticker)

    try:
        scanner = StockScanner(tickers=tickers, max_workers=DEFAULT_MAX_WORKERS)
        scanner._db = db
        results = scanner.scan(progress_callback=progress_cb)

        if min_score > 0:
            results = [r for r in results if r.confidence_score >= min_score]

        db.save_results(scan_id, results)
        db.update_status(scan_id, "completed")
    except Exception as e:
        logger.error("Scan %s failed: %s", scan_id, e, exc_info=True)
        db.update_status(scan_id, f"failed: {e}")


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse(request, "dashboard.html")


@app.get("/api/watchlists")
async def get_watchlists():
    return {
        "default": {"name": "Growth Watchlist", "count": len(DEFAULT_GROWTH_WATCHLIST)},
        "sp500": {"name": "S&P 500", "count": "~500"},
        "nasdaq100": {"name": "NASDAQ 100", "count": "~100"},
        "custom": {"name": "Custom Tickers", "count": "variable"},
    }


@app.get("/api/market-status")
async def market_status():
    """Return current market regime based on SPY data."""
    import yfinance as yf
    try:
        spy = yf.Ticker("SPY")
        spy_df = spy.history(period="2y")
        if spy_df is None or len(spy_df) < 200:
            return {"status": "unknown", "error": "Could not fetch SPY data"}
        detector = PatternDetector()
        spy_df = detector.add_moving_averages(spy_df)
        regime = MarketRegime(spy_df)
        return regime.evaluate()
    except Exception as e:
        return {"status": "unknown", "error": str(e)}


@app.post("/api/scan")
async def start_scan(request: ScanRequest):
    tickers = resolve_watchlist(request.watchlist, request.tickers)
    scan_id = db.create_scan(watchlist=request.watchlist, tickers=tickers)

    thread = threading.Thread(
        target=_run_scan,
        args=(scan_id, tickers, request.min_score),
        daemon=True,
    )
    thread.start()

    return {"scan_id": scan_id, "total_tickers": len(tickers)}


@app.get("/api/scan/{scan_id}/progress")
async def scan_progress(scan_id: str):
    """SSE endpoint streaming scan progress."""
    async def event_generator():
        while True:
            progress = db.get_progress(scan_id)
            data = json.dumps(progress)
            yield f"data: {data}\n\n"

            status = progress["status"]
            if status in ("completed", "not_found") or status.startswith("failed"):
                break
            await asyncio.sleep(SSE_POLL_INTERVAL)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@app.get("/api/scan/{scan_id}/results")
async def get_results(scan_id: str):
    results = db.get_results(scan_id)
    return {
        "scan_id": scan_id,
        "count": len(results),
        "results": [
            {
                "ticker": r.ticker,
                "pattern_type": r.pattern_type,
                "confidence_score": r.confidence_score,
                "status": r.status,
                "buy_point": r.buy_point,
                "current_price": r.current_price,
                "distance_to_pivot": r.distance_to_pivot,
                "base_depth": r.base_depth,
                "base_length_weeks": r.base_length_weeks,
                "volume_confirmation": r.volume_confirmation,
                "above_50ma": r.above_50ma,
                "above_200ma": r.above_200ma,
                "rs_rating": r.rs_rating,
                "stop_loss_price": r.stop_loss_price,
                "profit_target_price": r.profit_target_price,
                "breakout_confirmed": r.breakout_confirmed,
                "volume_surge_pct": r.volume_surge_pct,
                "volume_rating": r.volume_rating,
                "trend_score": r.trend_score,
                "earnings_flag": r.earnings_flag,
                "earnings_days_until": r.earnings_days_until,
                "earnings_momentum_score": r.earnings_momentum_score,
                "sector": r.sector,
                "sector_rs": r.sector_rs,
                "sector_class": r.sector_class,
                "avg_dollar_volume": r.avg_dollar_volume,
                "volume_grade": r.volume_grade,
                "regime_penalty": r.regime_penalty,
            }
            for r in results
        ],
    }


@app.get("/api/export/excel/{scan_id}")
async def export_excel(scan_id: str):
    results = db.get_results(scan_id)
    if not results:
        return {"error": "No results found for this scan"}

    filepath = os.path.join(tempfile.gettempdir(), f"scan_{scan_id}.xlsx")
    export_to_excel(results, filepath)
    return FileResponse(
        filepath,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=f"pattern_scan_{scan_id}.xlsx",
    )


def _run_backtest(bt_id: str, tickers: list[str], config: BacktestConfig):
    """Run backtest in a background thread."""
    import yfinance as yf

    try:
        # Fetch data for all tickers + SPY
        spy = yf.Ticker("SPY")
        spy_data = spy.history(period="2y")
        if spy_data is None or len(spy_data) < MIN_DATA_POINTS:
            db.update_backtest_status(bt_id, "failed: Could not fetch SPY data")
            return

        ticker_data = {}
        for ticker in tickers:
            try:
                t = yf.Ticker(ticker)
                df = t.history(period="2y")
                if df is not None and len(df) >= MIN_DATA_POINTS:
                    ticker_data[ticker] = df
            except Exception as e:
                logger.warning("Failed to fetch %s for backtest: %s", ticker, e)

        if not ticker_data:
            db.update_backtest_status(bt_id, "failed: No valid ticker data")
            return

        engine = BacktestEngine(
            ticker_data=ticker_data,
            spy_data=spy_data,
            config=config,
        )

        def progress_cb(current: int, total: int):
            db.update_backtest_progress(bt_id, current, total)

        trades = engine.run(progress_callback=progress_cb)
        metrics = compute_metrics(trades)

        db.save_backtest_trades(bt_id, trades)
        db.save_backtest_summary(
            bt_id,
            total_trades=metrics["total_trades"],
            win_rate=metrics["win_rate"],
            profit_factor=metrics["profit_factor"] if metrics["profit_factor"] != float("inf") else 999.0,
        )
        db.update_backtest_status(bt_id, "completed")
    except Exception as e:
        logger.error("Backtest %s failed: %s", bt_id, e, exc_info=True)
        db.update_backtest_status(bt_id, f"failed: {e}")


@app.post("/api/backtest")
async def start_backtest(request: BacktestRequest):
    tickers = resolve_watchlist(request.watchlist, request.tickers)
    config = BacktestConfig(
        stop_loss_pct=request.stop_loss_pct,
        profit_target_pct=request.profit_target_pct,
        min_confidence=request.min_confidence,
    )
    bt_id = db.create_backtest(
        watchlist=request.watchlist,
        tickers=tickers,
        stop_loss_pct=config.stop_loss_pct,
        profit_target_pct=config.profit_target_pct,
        min_confidence=config.min_confidence,
    )

    thread = threading.Thread(
        target=_run_backtest,
        args=(bt_id, tickers, config),
        daemon=True,
    )
    thread.start()

    return {"backtest_id": bt_id, "total_tickers": len(tickers)}


@app.get("/api/backtest/{bt_id}/progress")
async def backtest_progress(bt_id: str):
    """SSE endpoint streaming backtest progress."""
    async def event_generator():
        while True:
            progress = db.get_backtest_progress(bt_id)
            data = json.dumps(progress)
            yield f"data: {data}\n\n"

            status = progress["status"]
            if status in ("completed", "not_found") or status.startswith("failed"):
                break
            await asyncio.sleep(SSE_POLL_INTERVAL)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@app.get("/api/backtest/{bt_id}/results")
async def get_backtest_results(bt_id: str):
    trades = db.get_backtest_trades(bt_id)
    summary = db.get_backtest_summary(bt_id)
    metrics = compute_metrics(trades) if trades else {
        "total_trades": 0, "win_rate": 0.0, "avg_return": 0.0,
        "profit_factor": 0.0, "avg_win": 0.0, "avg_loss": 0.0,
        "expectancy": 0.0, "by_pattern": {}, "by_confidence": {},
        "by_regime": {},
    }
    return {
        "backtest_id": bt_id,
        "summary": summary,
        "metrics": metrics,
        "trades": trades,
    }
