from __future__ import annotations

import hashlib
import time
from datetime import datetime, timezone
from typing import Any

from .pipeline import WorkbookData
from .workflow import (
    CanonicalProductionRecord,
    ClientCapabilities,
    ComparisonResult,
    EvidenceAssessment,
    SupervisorReason,
    TargetDefinition,
    compare_record,
    evidence_assessment,
    rca_registry,
)


CAPABILITIES: dict[str, ClientCapabilities] = {}
TARGETS: list[TargetDefinition] = []
RECORDS: dict[str, CanonicalProductionRecord] = {}
COMPARISONS: dict[str, ComparisonResult] = {}
INCIDENTS: dict[str, dict[str, Any]] = {}
REASONS: dict[str, list[SupervisorReason]] = {}


def configure_capabilities(value: ClientCapabilities) -> ClientCapabilities:
    CAPABILITIES[value.client_id] = value
    return value


def add_target(value: TargetDefinition) -> TargetDefinition:
    TARGETS[:] = [x for x in TARGETS if not (x.client == value.client and x.line == value.line and x.product == value.product and x.metric == value.metric and x.version == value.version)]
    TARGETS.append(value)
    return value


def add_record(record: CanonicalProductionRecord) -> CanonicalProductionRecord:
    RECORDS[record.fingerprint] = record
    return record


def output_row_to_record(row: dict[str, Any], client: str = "demo", plant: str = "", source: str = "excel") -> CanonicalProductionRecord:
    date = str(row.get("Date") or datetime.now(timezone.utc).date().isoformat())
    hour = str(row.get("Hour") or "00:00")
    if "-" in hour:
        hour = hour.split("-")[0].strip()
    timestamp = datetime.fromisoformat(f"{date}T{hour}:00" if hour.count(":") == 1 else f"{date}T{hour}")
    line = str(row.get("Line") or row.get("Stage") or "unknown")
    record_id = str(row.get("Source Record ID") or f"{source}:{line}:{date}:{row.get('Hour', '')}")
    return CanonicalProductionRecord(
        client=client,
        plant=plant,
        line=line,
        shift=str(row.get("Shift") or ""),
        timestamp=timestamp,
        product=str(row.get("Product") or ""),
        quantity=float(str(row.get("Good Count") or row.get("Actual output") or row.get("Actual") or 0).replace(",", "")),
        unit=str(row.get("Unit") or "batches"),
        data_source=source,
        source_record_id=record_id,
        measurements={k: v for k, v in row.items() if k not in {"Date", "Hour", "Stage", "Line", "Shift", "Product", "Good Count", "Actual output", "Actual", "Unit"}},
        provenance={"source_sheet": row.get("_sheet", "1_Output"), "source_row": row.get("_row")},
    )


def import_workbook(data: WorkbookData, client: str = "demo") -> dict[str, Any]:
    capability = CAPABILITIES.get(client, ClientCapabilities(client_id=client))
    imported = 0
    duplicate = 0
    results = []
    for row_number, row in enumerate(data.rows.get("1_Output", []), 2):
        row = {**row, "_row": row_number}
        record = output_row_to_record(row, client=client)
        before = len(RECORDS)
        add_record(record)
        duplicate += int(len(RECORDS) == before)
        imported += int(len(RECORDS) > before)
        target = next((t for t in reversed(TARGETS) if t.client == client and t.line == record.line and (not t.product or t.product == record.product)), None)
        if target:
            comparison = compare_record(record, target)
            COMPARISONS[record.fingerprint] = comparison
            results.append(comparison)
            if not comparison.target_met:
                incident_id = hashlib.sha256(f"{client}:{record.line}:{record.timestamp.isoformat()}:{target.metric}".encode()).hexdigest()[:16]
                incident = INCIDENTS.setdefault(incident_id, {"incident_id": incident_id, "client": client, "line": record.line, "shift": record.shift, "record_ids": [], "status": "OPEN", "comparison": comparison.model_dump(mode="json"), "reasons": []})
                if record.fingerprint not in incident["record_ids"]:
                    incident["record_ids"].append(record.fingerprint)
    return {"client": client, "tier": capability.input_tier, "imported": imported, "duplicates": duplicate, "comparisons": len(results), "incidents": len(INCIDENTS)}


def submit_reason(incident_id: str, reason: SupervisorReason) -> dict[str, Any]:
    if incident_id not in INCIDENTS:
        raise KeyError(incident_id)
    REASONS.setdefault(incident_id, []).append(reason)
    INCIDENTS[incident_id]["reasons"] = [x.model_dump(mode="json") for x in REASONS[incident_id]]
    return INCIDENTS[incident_id]


def assess_incident(incident_id: str) -> EvidenceAssessment:
    incident = INCIDENTS[incident_id]
    client = incident["client"]
    tier = CAPABILITIES.get(client, ClientCapabilities(client_id=client)).input_tier
    reasons = REASONS.get(incident_id, [])
    sources = ["production_output"] + (["supervisor_reason"] if reasons else [])
    hypothesis = reasons[-1].reason_description if reasons else "Target miss requires supervisor investigation"
    missing = [] if reasons else ["supervisor_reason"]
    return evidence_assessment(tier, hypothesis, sources, missing=missing)


def reset_workflow_state() -> None:
    CAPABILITIES.clear(); TARGETS.clear(); RECORDS.clear(); COMPARISONS.clear(); INCIDENTS.clear(); REASONS.clear()
