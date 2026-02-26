# tests/test_excel_export.py
import os
from openpyxl import load_workbook
from excel_export import export_to_excel


def _sample_results(make_pattern_result):
    return [
        make_pattern_result(
            ticker="AAPL", pattern_type="Cup & Handle", confidence_score=85.0,
            buy_point=195.0, current_price=193.0, distance_to_pivot=-1.0,
            base_depth=22.0, base_length_weeks=14, rs_rating=88.0,
            pattern_details={"cup_low": 160.0},
        ),
        make_pattern_result(
            ticker="NVDA", pattern_type="Flat Base", confidence_score=72.0,
            buy_point=500.0, current_price=485.0, distance_to_pivot=-3.0,
            base_depth=9.0, base_length_weeks=6, volume_confirmation=False,
            rs_rating=95.0,
        ),
    ]


def test_export_creates_file(tmp_path, make_pattern_result):
    results = _sample_results(make_pattern_result)
    path = str(tmp_path / "test_report.xlsx")
    export_to_excel(results, path)
    assert os.path.exists(path)


def test_export_has_three_sheets(tmp_path, make_pattern_result):
    results = _sample_results(make_pattern_result)
    path = str(tmp_path / "test_report.xlsx")
    export_to_excel(results, path)
    wb = load_workbook(path)
    assert "Pattern Scanner Results" in wb.sheetnames
    assert "Pattern Guide" in wb.sheetnames
    assert "Top Picks" in wb.sheetnames


def test_export_results_sheet_has_data(tmp_path, make_pattern_result):
    results = _sample_results(make_pattern_result)
    path = str(tmp_path / "test_report.xlsx")
    export_to_excel(results, path)
    wb = load_workbook(path)
    ws = wb["Pattern Scanner Results"]
    assert ws.max_row >= 3
    assert ws["A2"].value == "AAPL"
