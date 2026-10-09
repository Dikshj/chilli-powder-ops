from datetime import datetime, timezone

import pytest

from app.workflow import (
    CanonicalProductionRecord,
    ClientCapabilities,
    SupervisorReason,
    TargetDefinition,
    compare_record,
    evidence_assessment,
)
from app.workflow_service import (
    INCIDENTS,
    add_record,
    add_target,
    configure_capabilities,
    import_workbook,
    reset_workflow_state,
    submit_reason,
)
from app.pipeline import WorkbookData


@pytest.fixture(autouse=True)
def clean_state():
    reset_workflow_state()
    yield
    reset_workflow_state()


def test_mixing_shift_comparison_matches_document_example():
    record = CanonicalProductionRecord(
        client="mixing-demo", line="Mixing", timestamp=datetime(2026, 10, 9, tzinfo=timezone.utc),
        quantity=29, unit="batches", data_source="excel", source_record_id="shift-1",
    )
    target = TargetDefinition(client="mixing-demo", line="Mixing", target_value=40, unit="batches", tolerance=0)
    result = compare_record(record, target)
    assert result.production_shortfall == 11
    assert result.percentage_variance == pytest.approx(-0.275)
    assert result.target_met is False


def test_tolerance_prevents_unnecessary_incident():
    record = CanonicalProductionRecord(
        client="c", line="L1", timestamp=datetime.now(timezone.utc), quantity=98, unit="batches", data_source="excel", source_record_id="1",
    )
    target = TargetDefinition(client="c", line="L1", target_value=100, unit="batches", tolerance=3)
    assert compare_record(record, target).target_met is True


def test_manual_import_is_idempotent_and_deduplicates_incidents():
    configure_capabilities(ClientCapabilities(client_id="mixing-demo", input_tier="manual"))
    add_target(TargetDefinition(client="mixing-demo", line="Mixing", target_value=5, unit="batches"))
    rows = [{"Date": "2026-10-09", "Hour": "09:00 - 10:00", "Stage": "Mixing", "Good Count": "3"}]
    data = WorkbookData({}, {"1_Output": rows}, "fixture")
    first = import_workbook(data, "mixing-demo")
    second = import_workbook(data, "mixing-demo")
    assert first["imported"] == 1
    assert second["duplicates"] == 1
    assert len(INCIDENTS) == 1


def test_supervisor_reason_is_reported_not_confirmed_and_scored_by_tier():
    configure_capabilities(ClientCapabilities(client_id="c", input_tier="manual"))
    add_target(TargetDefinition(client="c", line="L1", target_value=5, unit="batches"))
    data = WorkbookData({}, {"1_Output": [{"Date": "2026-10-09", "Hour": "09:00", "Stage": "L1", "Good Count": "3"}]}, "fixture")
    import_workbook(data, "c")
    incident_id = next(iter(INCIDENTS))
    submit_reason(incident_id, SupervisorReason(incident_id=incident_id, line="L1", target=5, actual=3, reason_category="Machine", reason_description="Motor overheated", supervisor="sup", submitted_at=datetime.now(timezone.utc)))
    assert INCIDENTS[incident_id]["reasons"][0]["status"] == "reported"
    manual = evidence_assessment("manual", "Motor overheated", ["supervisor_reason", "production_output"])
    sensor = evidence_assessment("sensor", "Motor overheated", ["supervisor_reason", "production_output"])
    assert sensor.score_factors["source_reliability"] > manual.score_factors["source_reliability"]

