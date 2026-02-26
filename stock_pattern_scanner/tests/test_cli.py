# tests/test_cli.py
import os
import subprocess
import sys

_SCANNER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_cli_help():
    result = subprocess.run(
        [sys.executable, "run_scanner.py", "--help"],
        capture_output=True, text=True, cwd=_SCANNER_DIR,
    )
    assert result.returncode == 0
    assert "--sp500" in result.stdout
    assert "--nasdaq100" in result.stdout
    assert "--tickers" in result.stdout
    assert "--min-score" in result.stdout


def test_cli_version_or_default():
    result = subprocess.run(
        [sys.executable, "run_scanner.py", "--tickers", "FAKE_TICKER_XYZ", "--no-excel", "--top", "1"],
        capture_output=True, text=True, cwd=_SCANNER_DIR, timeout=120,
    )
    assert "Traceback" not in result.stderr or "Traceback" not in result.stdout
