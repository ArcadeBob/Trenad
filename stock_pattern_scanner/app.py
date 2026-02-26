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

from constants import DEFAULT_MAX_WORKERS, SSE_POLL_INTERVAL
from database import ScanDatabase
from excel_export import export_to_excel
from pattern_scanner import StockScanner
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


def _run_scan(scan_id: str, tickers: list[str], min_score: float):
    """Run scan in a background thread."""
    def progress_cb(current: int, total: int, ticker: str):
        db.update_progress(scan_id, current, total, ticker)

    try:
        scanner = StockScanner(tickers=tickers, max_workers=DEFAULT_MAX_WORKERS)
        results = scanner.scan(progress_callback=progress_cb)

        if min_score > 0:
            results = [r for r in results if r.confidence_score >= min_score]

        db.save_results(scan_id, results)
        db.update_status(scan_id, "completed")
    except Exception as e:
        logger.error("Scan %s failed: %s", scan_id, e)
        db.update_status(scan_id, "failed")


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

            if progress["status"] in ("completed", "failed", "not_found"):
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
