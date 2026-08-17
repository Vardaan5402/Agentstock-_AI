"""Persistence service for immutable decision reviews, scenarios, and audit events."""

from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Any
from uuid import uuid4

from database.database import Database
from core.security import require_admin
from models.decision_workflow import DecisionWorkflowResult
from models.persistence import AuditEvent, AuditEventType, SavedDecisionReview, SavedWhatIfScenario
from models.what_if import WhatIfComparisonResult, WhatIfScenario


_SENSITIVE_KEY_PARTS = ("api_key", "secret", "password", "credential", "token")


def save_decision_review(database: Database, result: DecisionWorkflowResult) -> SavedDecisionReview:
    """Save a new immutable review and its creation audit event atomically.

    Re-saving the exact immutable snapshot returns the original record without
    writing a duplicate audit event. Existing snapshot evidence is never updated.
    """
    facts_json = result.facts.canonical_json()
    _assert_no_secrets(json.loads(facts_json))
    payload = {
        "snapshot_id": result.facts.snapshot_id,
        "business_id": result.facts.business.business_id,
        "product_id": result.facts.business.product_id,
        "facts_json": facts_json,
        "proposal_json": _model_json(result.proposal),
        "reference_validation_json": _model_json(result.reference_validation),
        "policy_validation_json": _model_json(result.policy_validation),
        "status": result.status.value,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _assert_no_secrets(payload)
    database.save_review_bundle(
        result.baseline.business,
        result.baseline.product,
        result.baseline.suppliers,
        result.baseline.supplier_products,
        payload,
        _audit_values(
            entity_type="decision_snapshot",
            entity_id=result.facts.snapshot_id,
            event_type=AuditEventType.DECISION_CREATED,
            metadata={"status": result.status.value},
        ),
    )
    return get_decision_review(database, result.facts.snapshot_id, record_view=False)


def get_decision_review(
    database: Database, snapshot_id: str, *, record_view: bool = True
) -> SavedDecisionReview:
    """Load and validate an immutable snapshot; malformed saved evidence is rejected."""
    row = database.get_decision_snapshot(snapshot_id)
    if row is None:
        raise ValueError("saved decision snapshot was not found")
    review = _parse_decision_row(row)
    if record_view:
        database.create_audit_event(_audit_values(
            entity_type="decision_snapshot",
            entity_id=snapshot_id,
            event_type=AuditEventType.DECISION_VIEWED,
            metadata={"status": review.status.value},
        ))
    return review


def list_decision_reviews(
    database: Database,
    *,
    business_id: str | None = None,
    product_id: str | None = None,
    status: str | None = None,
) -> list[SavedDecisionReview]:
    """Return validated read-only reviews, newest first."""
    return [
        _parse_decision_row(row)
        for row in database.list_decision_snapshots(
            business_id=business_id,
            product_id=product_id,
            status=status,
        )
    ]


def approve_decision_review(
    database: Database,
    snapshot_id: str,
    reviewer: str = "human_reviewer",
) -> SavedDecisionReview:
    """Record human approval of an immutable decision review."""

    review = get_decision_review(
        database,
        snapshot_id,
        record_view=False,
    )

    database.create_audit_event(
        _audit_values(
            entity_type="decision_snapshot",
            entity_id=snapshot_id,
            event_type=AuditEventType.DECISION_APPROVED,
            metadata={
                "reviewer": reviewer,
                "status": review.status.value,
            },
        )
    )

    return review


def reject_decision_review(
    database: Database,
    snapshot_id: str,
    reviewer: str = "human_reviewer",
    reason: str = "",
) -> SavedDecisionReview:
    """Record human rejection of an immutable decision review."""

    review = get_decision_review(
        database,
        snapshot_id,
        record_view=False,
    )

    metadata = {
        "reviewer": reviewer,
        "status": review.status.value,
    }

    if reason.strip():
        metadata["reason"] = reason.strip()

    database.create_audit_event(
        _audit_values(
            entity_type="decision_snapshot",
            entity_id=snapshot_id,
            event_type=AuditEventType.DECISION_REJECTED,
            metadata=metadata,
        )
    )

    return review

def save_what_if_scenario(
    database: Database,
    decision_snapshot_id: str,
    scenario: WhatIfScenario,
    comparison: WhatIfComparisonResult,
) -> SavedWhatIfScenario:
    """Persist a deterministic what-if result against an existing immutable review."""
    if database.get_decision_snapshot(decision_snapshot_id) is None:
        raise ValueError("what-if baseline snapshot was not found")
    if comparison.scenario_id != scenario.scenario_id:
        raise ValueError("what-if comparison does not match the scenario")
    scenario_json = scenario.model_dump_json()
    comparison_json = comparison.model_dump_json()
    _assert_no_secrets(json.loads(scenario_json))
    _assert_no_secrets(json.loads(comparison_json))
    saved_id = _scenario_record_id(decision_snapshot_id, scenario_json)
    database.save_what_if_scenario(
        {
            "id": saved_id,
            "decision_snapshot_id": decision_snapshot_id,
            "baseline_snapshot_id": comparison.baseline_snapshot_id,
            "scenario_id": scenario.scenario_id,
            "scenario_json": scenario_json,
            "comparison_json": comparison_json,
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
        _audit_values(
            entity_type="what_if_scenario",
            entity_id=saved_id,
            event_type=AuditEventType.WHAT_IF_CREATED,
            metadata={"decision_snapshot_id": decision_snapshot_id},
        ),
    )
    return get_what_if_scenario(database, saved_id, record_view=False)


def get_what_if_scenario(
    database: Database, saved_id: str, *, record_view: bool = True
) -> SavedWhatIfScenario:
    """Load a validated, read-only saved what-if comparison."""
    row = database.get_what_if_scenario(saved_id)
    if row is None:
        raise ValueError("saved what-if scenario was not found")
    saved = _parse_what_if_row(row)
    if record_view:
        database.create_audit_event(_audit_values(
            entity_type="what_if_scenario",
            entity_id=saved_id,
            event_type=AuditEventType.WHAT_IF_VIEWED,
            metadata={"decision_snapshot_id": saved.decision_snapshot_id},
        ))
    return saved


def list_what_if_scenarios(database: Database, *, decision_snapshot_id: str | None = None) -> list[SavedWhatIfScenario]:
    """Return validated saved scenarios, newest first."""
    return [_parse_what_if_row(row) for row in database.list_what_if_scenarios(decision_snapshot_id)]


def list_audit_events(database: Database, user: Any) -> list[AuditEvent]:
    """Return audit events only to the authenticated platform administrator."""
    authorized, message = require_admin(user)
    if not authorized:
        raise PermissionError(message)

    events = []
    for row in database.list_audit_events():
        try:
            events.append(AuditEvent(
                id=row["id"], entity_type=row["entity_type"], entity_id=row["entity_id"],
                event_type=row["event_type"], metadata=json.loads(row["metadata_json"]),
                created_at=row["created_at"],
            ))
        except (TypeError, ValueError, json.JSONDecodeError) as error:
            raise ValueError("saved audit event is corrupted") from error
    return events


def _parse_decision_row(row: Any) -> SavedDecisionReview:
    try:
        return SavedDecisionReview(
            snapshot_id=row["snapshot_id"], business_id=row["business_id"], product_id=row["product_id"],
            facts=json.loads(row["facts_json"]), proposal=_json_or_none(row["proposal_json"]),
            reference_validation=_json_or_none(row["reference_validation_json"]),
            policy_validation=_json_or_none(row["policy_validation_json"]),
            status=row["status"], created_at=row["created_at"],
        )
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise ValueError("saved decision snapshot is corrupted") from error


def _parse_what_if_row(row: Any) -> SavedWhatIfScenario:
    try:
        return SavedWhatIfScenario(
            id=row["id"], decision_snapshot_id=row["decision_snapshot_id"], baseline_snapshot_id=row["baseline_snapshot_id"],
            scenario=json.loads(row["scenario_json"]), comparison=json.loads(row["comparison_json"]),
            created_at=row["created_at"],
        )
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise ValueError("saved what-if scenario is corrupted") from error


def _model_json(model: Any) -> str | None:
    return None if model is None else model.model_dump_json()


def _json_or_none(value: str | None) -> Any:
    return None if value is None else json.loads(value)


def _scenario_record_id(decision_snapshot_id: str, scenario_json: str) -> str:
    return sha256(f"{decision_snapshot_id}:{scenario_json}".encode("utf-8")).hexdigest()


def _audit_values(*, entity_type: str, entity_id: str, event_type: AuditEventType, metadata: dict[str, str]) -> dict[str, str]:
    _assert_no_secrets(metadata)
    return {
        "id": uuid4().hex,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "event_type": event_type.value,
        "metadata_json": json.dumps(metadata, sort_keys=True, separators=(",", ":")),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def save_raw_audit_event(
    database: Database,
    entity_type: str,
    entity_id: str,
    event_type: AuditEventType,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Save an individual audit event directly."""
    meta = {k: str(v) for k, v in (metadata or {}).items()}
    _assert_no_secrets(meta)
    payload = _audit_values(
        entity_type=entity_type,
        entity_id=entity_id,
        event_type=event_type,
        metadata=meta,
    )
    database._insert("audit_events", payload)


def _assert_no_secrets(value: Any) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if any(part in str(key).lower() for part in _SENSITIVE_KEY_PARTS):
                raise ValueError("sensitive values must not be persisted")
            _assert_no_secrets(item)
    elif isinstance(value, list):
        for item in value:
            _assert_no_secrets(item)
