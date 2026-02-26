#!/usr/bin/env python3
"""CLI entry point for the stock pattern scanner."""

from __future__ import annotations

import argparse
import sys
import time

from constants import DEFAULT_MAX_WORKERS, DEFAULT_TOP_RESULTS, NEAR_PIVOT_THRESHOLD, PROGRESS_BAR_LENGTH
from pattern_scanner import StockScanner
from excel_export import export_to_excel
from ticker_lists import resolve_watchlist


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Stock Base Pattern Scanner — Detect CAN SLIM base patterns",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--sp500", action="store_true", help="Scan S&P 500 stocks")
    group.add_argument("--nasdaq100", action="store_true", help="Scan NASDAQ 100 stocks")
    group.add_argument("--tickers", nargs="+", metavar="TICKER", help="Specific tickers to scan")
    group.add_argument("--file", metavar="FILE", help="Read tickers from file (one per line)")

    parser.add_argument("--min-score", type=float, default=0, help="Minimum confidence score (0-100)")
    parser.add_argument("--near-pivot", action="store_true", help="Only show stocks within 5%% of buy point")
    parser.add_argument("--top", type=int, default=DEFAULT_TOP_RESULTS, help="Show top N results (default: 50)")
    parser.add_argument("--no-excel", action="store_true", help="Skip Excel export")
    parser.add_argument("--output", metavar="FILE", default="pattern_scan.xlsx", help="Excel output filename")
    parser.add_argument("--web", action="store_true", help="Launch web dashboard instead of CLI scan")

    return parser.parse_args(argv)


def resolve_tickers(args: argparse.Namespace) -> list[str]:
    if args.file:
        with open(args.file, encoding="utf-8") as f:
            return [line.strip().upper() for line in f if line.strip()]
    if args.tickers:
        return resolve_watchlist("custom", args.tickers)
    if args.sp500:
        print("Fetching S&P 500 ticker list...")
        return resolve_watchlist("sp500")
    if args.nasdaq100:
        print("Fetching NASDAQ 100 ticker list...")
        return resolve_watchlist("nasdaq100")
    return resolve_watchlist("default")


def print_progress(current: int, total: int, ticker: str):
    pct = current / total * 100 if total > 0 else 0
    bar_len = PROGRESS_BAR_LENGTH
    filled = int(bar_len * current / total) if total > 0 else 0
    bar = "\u2588" * filled + "\u2591" * (bar_len - filled)
    print(f"\r  {bar} {pct:5.1f}% ({current}/{total}) {ticker:<8}", end="", flush=True)


def print_results_table(results):
    if not results:
        print("\nNo patterns found matching your criteria.")
        return

    print(f"\n{'\u2500' * 120}")
    print(f"{'#':>3}  {'Ticker':<8} {'Pattern':<20} {'Score':>6} {'Status':<12} "
          f"{'Price':>10} {'Buy Pt':>10} {'Dist%':>7} {'Depth%':>7} "
          f"{'Wks':>4} {'RS':>5} {'50MA':>5} {'200MA':>6} {'Vol':>4}")
    print(f"{'\u2500' * 120}")

    for i, r in enumerate(results, 1):
        ma50 = "\u2713" if r.above_50ma else "\u2717"
        ma200 = "\u2713" if r.above_200ma else "\u2717"
        vol = "\u2713" if r.volume_confirmation else "\u2717"
        print(f"{i:>3}  {r.ticker:<8} {r.pattern_type:<20} {r.confidence_score:>5.1f}  "
              f"{r.status:<12} {r.current_price:>10.2f} {r.buy_point:>10.2f} "
              f"{r.distance_to_pivot:>6.1f}% {r.base_depth:>6.1f}% "
              f"{r.base_length_weeks:>4} {r.rs_rating:>5.1f} {ma50:>5} {ma200:>6} {vol:>4}")

    print(f"{'\u2500' * 120}")


def main():
    args = parse_args()

    if args.web:
        import uvicorn
        print("Starting web dashboard at http://localhost:8000")
        uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
        return

    try:
        tickers = resolve_tickers(args)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"\nStock Base Pattern Scanner")
    print(f"{'\u2550' * 40}")
    print(f"Scanning {len(tickers)} tickers...\n")

    try:
        start_time = time.time()
        scanner = StockScanner(tickers=tickers, max_workers=DEFAULT_MAX_WORKERS)
        results = scanner.scan(progress_callback=print_progress)
        elapsed = time.time() - start_time
    except KeyboardInterrupt:
        print("\n\nScan interrupted.")
        sys.exit(130)
    except Exception as e:
        print(f"\n\nScan failed: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"\n\nScan complete in {elapsed:.1f}s \u2014 {len(results)} patterns found\n")

    # Apply filters
    if args.min_score > 0:
        results = [r for r in results if r.confidence_score >= args.min_score]
    if args.near_pivot:
        results = [r for r in results if abs(r.distance_to_pivot) <= NEAR_PIVOT_THRESHOLD]

    results = results[: args.top]
    print_results_table(results)

    # Excel export
    if not args.no_excel and results:
        export_to_excel(results, args.output)
        print(f"\nExcel report saved to: {args.output}")


if __name__ == "__main__":
    main()
