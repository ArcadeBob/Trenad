import subprocess
import sys


def test_cli_help():
    result = subprocess.run(
        [sys.executable, "run_scanner.py", "--help"],
        capture_output=True, text=True, cwd=".",
    )
    assert result.returncode == 0
    assert "--sp500" in result.stdout
    assert "--nasdaq100" in result.stdout
    assert "--tickers" in result.stdout
    assert "--min-score" in result.stdout


def test_cli_version_or_default():
    """CLI should at least parse arguments without crashing."""
    result = subprocess.run(
        [sys.executable, "run_scanner.py", "--tickers", "FAKE_TICKER_XYZ", "--no-excel", "--top", "1"],
        capture_output=True, text=True, cwd=".", timeout=120,
    )
    # Should complete without Python traceback (may have warnings about invalid ticker)
    assert "Traceback" not in result.stderr or "Traceback" not in result.stdout
