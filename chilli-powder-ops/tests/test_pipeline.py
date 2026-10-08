import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1]))
from app.pipeline import load_workbook, validate, metrics, rca

def test_demo_workbook_has_five_floor_sheets():
    d = load_workbook()
    assert set(d.rows) == {"1_Output", "2_Stops", "3_Settings", "4_Changes", "5_Response"}
    assert "Answer_Key" not in d.rows

def test_planted_grinding_issue_is_a_hold():
    d = load_workbook(); m = metrics(d)["Grinding"]
    assert rca("Grinding", m, d)["status"] == "HOLD"
    assert rca("Grinding", m, d)["quality_hold"] is True

