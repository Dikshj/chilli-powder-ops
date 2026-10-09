from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field


InputTier = Literal["manual", "erp", "sensor"]


class ClientCapabilities(BaseModel):
    client_id: str
    input_tier: InputTier = "manual"
    enabled_sources: list[str] = Field(default_factory=lambda: ["excel"])


class CanonicalProductionRecord(BaseModel):
    client: str
    plant: str = ""
    line: str
    shift: str = ""
    timestamp: datetime
    product: str = ""
    quantity: float
    unit: str
    data_source: str
    source_record_id: str
    measurements: dict[str, Any] = Field(default_factory=dict)
    provenance: dict[str, Any] = Field(default_factory=dict)

    @property
    def fingerprint(self) -> str:
        payload = self.model_dump(mode="json")
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


class TargetDefinition(BaseModel):
    client: str
    plant: str = ""
    line: str
    product: str = ""
    metric: str = "output"
    target_value: float
    unit: str
    tolerance: float = 0.0
    effective_from: datetime | None = None
    effective_to: datetime | None = None
    owner: str = ""
    version: int = 1


class ComparisonResult(BaseModel):
    record_id: str
    target: TargetDefinition
    actual_output: float
    expected_output: float
    absolute_variance: float
    percentage_variance: float
    production_shortfall: float
    lost_output: float
    within_tolerance: bool
    target_met: bool
    data_source: str


class SupervisorReason(BaseModel):
    incident_id: str
    line: str
    shift: str = ""
    time_window: str = ""
    target: float
    actual: float
    reason_category: Literal["Manpower", "Machine", "Material", "Process", "Method / Process"]
    reason_description: str = Field(min_length=1)
    supervisor: str
    submitted_at: datetime
    supporting_evidence: list[str] = Field(default_factory=list)
    status: Literal["reported", "corrected"] = "reported"


class EvidenceAssessment(BaseModel):
    hypothesis: str
    evidence_strength: Literal["LOW", "MEDIUM", "HIGH"]
    supporting_sources: list[str] = Field(default_factory=list)
    contradicting_sources: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    status: Literal["REPORTED", "SUSPECTED", "SUPPORTED", "CONFIRMED"] = "SUSPECTED"
    score_factors: dict[str, float] = Field(default_factory=dict)


class RCARegistryEntry(BaseModel):
    code: str
    name: str = ""
    definition: str = ""
    status: Literal["awaiting_definitions", "active"] = "awaiting_definitions"


def rca_registry() -> list[RCARegistryEntry]:
    return [RCARegistryEntry(code=f"RC-{i:02d}") for i in range(1, 14)]


def compare_record(record: CanonicalProductionRecord, target: TargetDefinition) -> ComparisonResult:
    if target.target_value == 0:
        percentage = 0.0 if record.quantity == 0 else 1.0
    else:
        percentage = (record.quantity - target.target_value) / target.target_value
    variance = record.quantity - target.target_value
    tolerance = abs(target.tolerance)
    return ComparisonResult(
        record_id=record.source_record_id,
        target=target,
        actual_output=record.quantity,
        expected_output=target.target_value,
        absolute_variance=variance,
        percentage_variance=percentage,
        production_shortfall=max(target.target_value - record.quantity, 0),
        lost_output=max(target.target_value - record.quantity, 0),
        within_tolerance=abs(variance) <= tolerance,
        target_met=record.quantity >= target.target_value - tolerance,
        data_source=record.data_source,
    )


def evidence_assessment(
    tier: InputTier,
    hypothesis: str,
    sources: list[str],
    missing: list[str] | None = None,
    contradicting: list[str] | None = None,
) -> EvidenceAssessment:
    missing = missing or []
    contradicting = contradicting or []
    reliability = {"manual": 0.55, "erp": 0.70, "sensor": 0.85}[tier]
    completeness = max(0.0, 1.0 - min(len(missing) * 0.15, 0.6))
    corroboration = min(1.0, 0.35 + len(set(sources)) * 0.2)
    contradiction_penalty = min(0.5, len(contradicting) * 0.15)
    score = max(0.0, reliability * 0.4 + completeness * 0.3 + corroboration * 0.3 - contradiction_penalty)
    strength = "HIGH" if score >= 0.75 else "MEDIUM" if score >= 0.5 else "LOW"
    status = "SUPPORTED" if strength == "HIGH" else "SUSPECTED"
    return EvidenceAssessment(
        hypothesis=hypothesis,
        evidence_strength=strength,
        supporting_sources=sources,
        contradicting_sources=contradicting,
        missing_evidence=missing,
        status=status,
        score_factors={"source_reliability": reliability, "completeness": completeness, "corroboration": corroboration, "contradiction_penalty": contradiction_penalty},
    )
