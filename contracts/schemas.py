"""Shared data shapes. Every module takes and returns these objects.

Change this file ONLY through a pull request approved by two teammates.
"""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class Transaction(BaseModel):
    txn_id: str
    timestamp: datetime
    account_from: str
    account_to: str
    amount_gbp: float
    txn_type: str
    memo: str = ""  # free text: untrusted, never treated as instructions
    is_synthetic: bool
    # No label field: labels live only in data/ and evaluation/.


class Alert(BaseModel):
    alert_id: str
    account_id: str
    txn_ids: list[str]
    created_at: datetime
    trigger: str  # which rule(s) raised the alert, e.g. "near_threshold+velocity"


class Factor(BaseModel):
    name: str
    value: float
    contribution: float


class RiskScore(BaseModel):
    alert_id: str
    probability: float = Field(ge=0, le=1)
    interval_low: float = Field(ge=0, le=1)
    interval_high: float = Field(ge=0, le=1)
    uncertain: bool  # wide interval or unfamiliar pattern
    top_factors: list[Factor]
    model_version: str


class Recommendation(BaseModel):
    alert_id: str
    action: Literal["escalate", "close", "need_more_info"]
    case_note: str
    evidence_ids: list[str]  # txn_ids, factor names, or "score"
    numbers_cited: dict[str, float]  # every number in case_note, keyed by its source
    llm_used: bool  # False = deterministic template fallback


class PolicyDecision(BaseModel):
    alert_id: str
    final_action: Literal["escalate", "close", "need_more_info", "human_review"]
    blocked: list[str]  # reasons the recommendation was overridden
    requires_human: bool


class AuditEvent(BaseModel):
    event_id: str
    ts: datetime
    actor: Literal["data", "model", "agent", "validator", "policy", "human"]
    alert_id: str | None
    payload: dict
    prev_hash: str
    hash: str
