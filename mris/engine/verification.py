"""Verification state machine + hash-chained audit (Parts 11.2, 18; Principle 12).

EXTRACTED_BY_AI -> REVIEWED -> VERIFIED_AGAINST_GAZETTE

Gates:
  * only VERIFIED provisions may feed live compliance calculations
    (fail-closed — a rule over unverified law can never reach ACTIVE);
  * two-person rule: the reviewer who verifies an extraction must not be
    the same person who performed the review;
  * audit entries are hash-chained (prev_hash -> entry_hash) so tampering
    is detectable; the chain verifies end-to-end.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class VerificationTier(str, Enum):
    EXTRACTED_BY_AI = "EXTRACTED_BY_AI"
    REVIEWED = "REVIEWED"
    VERIFIED_AGAINST_GAZETTE = "VERIFIED_AGAINST_GAZETTE"


class VerificationError(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# Review queue
# ---------------------------------------------------------------------------

@dataclass
class QueueItem:
    id: str
    object_type: str                      # INSTRUMENT | PROVISION | RULE
    object_id: str
    title: str
    extracted_text: str
    source_url: Optional[str] = None
    confidence: float = 1.0               # extraction confidence (assistive)
    tier: VerificationTier = VerificationTier.EXTRACTED_BY_AI
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    review_notes: Optional[str] = None
    verified_by: Optional[str] = None
    verified_at: Optional[datetime] = None
    verification_source_url: Optional[str] = None
    history: list[dict] = field(default_factory=list)

    def as_dict(self) -> dict:
        d = {
            "id": self.id, "object_type": self.object_type,
            "object_id": self.object_id, "title": self.title,
            "tier": self.tier.value, "confidence": self.confidence,
            "source_url": self.source_url,
            "reviewed_by": self.reviewed_by, "reviewed_at": _iso(self.reviewed_at),
            "review_notes": self.review_notes,
            "verified_by": self.verified_by, "verified_at": _iso(self.verified_at),
            "verification_source_url": self.verification_source_url,
            "history": self.history,
        }
        return d


def _iso(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat() if dt else None


class ReviewQueue:
    """In-memory queue; production persists to compliance/audit tables."""

    def __init__(self, audit: Optional["AuditChain"] = None):
        self.items: dict[str, QueueItem] = {}
        self.audit = audit or AuditChain()

    # -- intake ---------------------------------------------------------------
    def submit(self, item: QueueItem) -> QueueItem:
        item.history.append({"at": _now_iso(), "action": "SUBMITTED",
                             "tier": item.tier.value})
        self.items[item.id] = item
        self.audit.append("REVIEW_SUBMITTED", "queue_item", item.id,
                          after={"object_id": item.object_id,
                                 "tier": item.tier.value})
        return item

    # -- workflow --------------------------------------------------------------
    def review(self, item_id: str, reviewer_id: str, notes: str = "") -> QueueItem:
        item = self._get(item_id)
        if item.tier is not VerificationTier.EXTRACTED_BY_AI:
            raise VerificationError(
                f"item is {item.tier.value}; only EXTRACTED_BY_AI items can be reviewed")
        item.tier = VerificationTier.REVIEWED
        item.reviewed_by = reviewer_id
        item.reviewed_at = _now()
        item.review_notes = notes
        item.history.append({"at": _now_iso(), "action": "REVIEWED",
                             "actor": reviewer_id, "notes": notes})
        self.audit.append("REVIEW_APPROVED", "queue_item", item_id,
                          actor=reviewer_id,
                          before={"tier": "EXTRACTED_BY_AI"},
                          after={"tier": item.tier.value, "notes": notes})
        return item

    def verify(self, item_id: str, verifier_id: str,
               source_url: Optional[str] = None) -> QueueItem:
        """Two-person gate: verifier must differ from the reviewer (Part 11)."""
        item = self._get(item_id)
        if item.tier is not VerificationTier.REVIEWED:
            raise VerificationError(
                f"item is {item.tier.value}; must be REVIEWED before verification")
        if verifier_id == item.reviewed_by:
            raise VerificationError(
                "two-person rule: verifier must not be the reviewer of the same item")
        item.tier = VerificationTier.VERIFIED_AGAINST_GAZETTE
        item.verified_by = verifier_id
        item.verified_at = _now()
        item.verification_source_url = source_url or item.source_url
        item.history.append({"at": _now_iso(), "action": "VERIFIED",
                             "actor": verifier_id,
                             "source_url": item.verification_source_url})
        self.audit.append("VERIFIED_AGAINST_GAZETTE", "queue_item", item_id,
                          actor=verifier_id,
                          before={"tier": "REVIEWED"},
                          after={"tier": item.tier.value,
                                 "source_url": item.verification_source_url})
        return item

    def reject(self, item_id: str, actor_id: str, reason: str) -> QueueItem:
        item = self._get(item_id)
        item.history.append({"at": _now_iso(), "action": "REJECTED",
                             "actor": actor_id, "reason": reason})
        self.audit.append("REVIEW_REJECTED", "queue_item", item_id,
                          actor=actor_id, after={"reason": reason})
        return item

    # -- queries ---------------------------------------------------------------
    def list(self, tier: Optional[VerificationTier] = None) -> list[QueueItem]:
        items = list(self.items.values())
        if tier is not None:
            items = [i for i in items if i.tier is tier]
        return sorted(items, key=lambda i: (i.tier.value, i.id))

    def pending_count(self) -> int:
        return sum(1 for i in self.items.values()
                   if i.tier is not VerificationTier.VERIFIED_AGAINST_GAZETTE)

    def is_verified(self, object_id: str) -> bool:
        return any(i.object_id == object_id and
                   i.tier is VerificationTier.VERIFIED_AGAINST_GAZETTE
                   for i in self.items.values())

    def _get(self, item_id: str) -> QueueItem:
        try:
            return self.items[item_id]
        except KeyError:
            raise VerificationError(f"queue item {item_id!r} not found") from None


def rule_can_go_active(rule_provision_ids: list[str], queue: ReviewQueue) -> tuple[bool, list[str]]:
    """Fail-closed gate (Principle 12): every backing provision must be
    VERIFIED_AGAINST_GAZETTE before the rule may reach ACTIVE."""
    unverified = [p for p in rule_provision_ids if not queue.is_verified(p)]
    return (not unverified, unverified)


# ---------------------------------------------------------------------------
# Hash-chained audit (Part 18)
# ---------------------------------------------------------------------------

GENESIS = "0" * 64


class AuditChain:
    def __init__(self):
        self.entries: list[dict] = []
        self._head = GENESIS

    def append(self, action: str, object_type: str, object_id: str, *,
               actor: Optional[str] = None, company_id: Optional[str] = None,
               before: Any = None, after: Any = None) -> dict:
        payload = {
            "at": _now_iso(), "action": action, "actor": actor,
            "company_id": company_id, "object_type": object_type,
            "object_id": object_id, "before": before, "after": after,
            "prev_hash": self._head,
        }
        entry_hash = self._hash(payload)
        entry = {**payload, "entry_hash": entry_hash}
        self.entries.append(entry)
        self._head = entry_hash
        return entry

    @staticmethod
    def _hash(payload: dict) -> str:
        blob = json.dumps(payload, sort_keys=True, default=str).encode()
        return hashlib.sha256(blob).hexdigest()

    def verify_chain(self) -> tuple[bool, Optional[int]]:
        """Returns (ok, index_of_first_broken_entry)."""
        prev = GENESIS
        for idx, entry in enumerate(self.entries):
            payload = {k: v for k, v in entry.items() if k != "entry_hash"}
            if entry.get("prev_hash") != prev or entry.get("entry_hash") != self._hash(payload):
                return False, idx
            prev = entry["entry_hash"]
        return True, None

    def trail(self, object_type: Optional[str] = None,
              object_id: Optional[str] = None) -> list[dict]:
        return [e for e in self.entries
                if (object_type is None or e["object_type"] == object_type) and
                   (object_id is None or e["object_id"] == object_id)]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()
