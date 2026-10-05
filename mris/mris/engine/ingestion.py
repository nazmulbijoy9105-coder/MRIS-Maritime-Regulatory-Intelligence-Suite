"""Regulatory change / ingestion pipeline (Part 11).

    SOURCE MONITOR → HASH COMPARE → CLASSIFY → PROVISION EXTRACTION
    → LEGAL VERSION CHECK → EFFECTIVE-DATE ENGINE → LEGAL DIFF
    → RULE IMPACT → HUMAN LEGAL REVIEW → APPROVAL → ALERTS

This module implements the deterministic stages (registry, sha256 delta,
classification, provision-boundary detection, impact matching). OCR and
LLM-assisted extraction are assistive: their output enters as
EXTRACTED_BY_AI and only the human gate publishes (Principle 12).

SLA: official publication → customer alert ≤ 72 h for high-impact changes.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from .verification import AuditChain, QueueItem, ReviewQueue

HIGH_IMPACT_SLA_HOURS = 72

# ---------------------------------------------------------------------------
# Source registry
# ---------------------------------------------------------------------------

@dataclass
class SourceFeed:
    id: str
    url: str
    source_type: str                 # GAZETTE|OFFICIAL_DB|CIRCULAR|NOTICE|TARIFF
    publisher: str
    jurisdiction_id: str = "BD"
    last_sha256: Optional[str] = None
    last_checked_at: Optional[datetime] = None


@dataclass
class IngestResult:
    source_id: str
    changed: bool
    sha256: str
    classification: Optional[str] = None      # INSTRUMENT|AMENDMENT|REPEAL|...
    provision_count: int = 0
    queue_ids: list[str] = field(default_factory=list)
    notes: str = ""


_CLASSIFIERS = [
    ("REPEAL", re.compile(r"\b(repeal(?:s|ed|ing)?|revocation of)\b", re.I)),
    ("AMENDMENT", re.compile(r"\b(amendment|amends?|substitut(?:e|es|ed|ing)|"
                             r"insert(?:s|ed|ing)?|deleted by)\b", re.I)),
    ("TARIFF", re.compile(r"\b(tariff|schedule of (?:dues|charges|fees))\b", re.I)),
    ("NOTICE", re.compile(r"\b(notice|circular|no\.?\s*\d+/\d{4})\b", re.I)),
    ("INSTRUMENT", re.compile(r"\b(act|ordinance|rules|regulations|convention|"
                              r"protocol|s\.?\s*r\.?\s*o\.?)\b", re.I)),
]

# provision-boundary patterns: BD sections, IMO regulations, treaty articles
_PROVISION_RE = re.compile(
    r"^\s*(?:Section|Regulation|Reg\.?|Article|Art\.?|Rule|Clause)\s+"
    r"([0-9]+[A-Za-z]?(?:\s*[-–]\s*[0-9]+[A-Za-z]?)?)\s*[.:-]?\s*(.*)$",
    re.MULTILINE)


def classify(text: str) -> str:
    """Deterministic keyword classification (assistive — human confirms)."""
    for label, pattern in _CLASSIFIERS:
        if pattern.search(text):
            return label
    return "INSTRUMENT"


def detect_provision_boundaries(text: str) -> list[dict]:
    """Split legal text into provision-atomic chunks.

    Keeps provisos/explanations attached to their provision (they continue
    until the next boundary marker). Each chunk carries a confidence of 1.0
    for explicit markers; unattributed leading text becomes a PREAMBLE chunk
    with lower confidence routed to the human queue.
    """
    matches = list(_PROVISION_RE.finditer(text))
    chunks: list[dict] = []

    if matches and matches[0].start() > 0:
        lead = text[:matches[0].start()].strip()
        if lead:
            chunks.append({"locator": "PREAMBLE", "text": lead, "confidence": 0.5})

    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[m.start():end].strip()
        chunks.append({
            "locator": f"{m.group(0).split()[0]} {m.group(1)}",
            "title": m.group(2).strip()[:200],
            "text": body,
            "confidence": 0.95,
        })
    return chunks


def provision_id(instrument_id: str, locator: str) -> str:
    """Canonical derived ID (§4.2): {INSTRUMENT_ID}-S{###}[-SSx]."""
    m = re.match(r"\D*([0-9]+)([A-Za-z]?)", locator)
    if not m:
        slug = re.sub(r"[^0-9A-Za-z]+", "-", locator).strip("-").upper()
        return f"{instrument_id}-S{slug}"
    num, letter = m.group(1), m.group(2)
    return f"{instrument_id}-S{int(num):03d}" + (f"-SS{letter.upper()}" if letter else "")


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

class IngestionPipeline:
    def __init__(self, queue: Optional[ReviewQueue] = None,
                 audit: Optional[AuditChain] = None):
        self.audit = audit or AuditChain()
        self.queue = queue or ReviewQueue(self.audit)
        self.feeds: dict[str, SourceFeed] = {}
        self.results: list[IngestResult] = []

    def register(self, feed: SourceFeed) -> SourceFeed:
        self.feeds[feed.id] = feed
        self.audit.append("SOURCE_REGISTERED", "source_feed", feed.id,
                          after={"url": feed.url, "publisher": feed.publisher})
        return feed

    def ingest(self, source_id: str, content: bytes | str,
               instrument_id: str = "UNASSIGNED") -> IngestResult:
        """Fetch-result ingestion: hash → delta → classify → extract → queue.

        A byte-identical re-fetch is a no-op (delta detection). Any change
        routes every provision chunk to the human review queue as
        EXTRACTED_BY_AI — never straight into live calculations.
        """
        feed = self.feeds[source_id]
        raw = content.encode() if isinstance(content, str) else content
        sha = hashlib.sha256(raw).hexdigest()
        changed = feed.last_sha256 != sha
        feed.last_sha256 = sha
        feed.last_checked_at = datetime.now(timezone.utc)

        result = IngestResult(source_id=source_id, changed=changed, sha256=sha)

        if not changed:
            result.notes = "no delta — content unchanged since last fetch"
            self.results.append(result)
            return result

        text = raw.decode(errors="replace")
        result.classification = classify(text)
        chunks = detect_provision_boundaries(text)

        for n, chunk in enumerate(chunks, 1):
            pid = provision_id(instrument_id, chunk["locator"])
            item = QueueItem(
                id=f"q-{source_id}-{n:03d}",
                object_type="PROVISION",
                object_id=pid,
                title=f"{chunk['locator']} — {chunk.get('title', '')}".strip(" —"),
                extracted_text=chunk["text"],
                source_url=feed.url,
                confidence=chunk["confidence"],
            )
            self.queue.submit(item)
            result.queue_ids.append(item.id)

        result.provision_count = len(chunks)
        result.notes = (f"classified as {result.classification}; "
                        f"{len(chunks)} provision chunk(s) queued for human review")
        self.audit.append("SOURCE_INGESTED", "source_feed", source_id,
                          after={"sha256": sha, "classification": result.classification,
                                 "provisions": len(chunks)})
        self.results.append(result)
        return result

    def status(self) -> dict:
        return {
            "sources": [
                {"id": f.id, "url": f.url, "publisher": f.publisher,
                 "source_type": f.source_type, "jurisdiction_id": f.jurisdiction_id,
                 "last_sha256": f.last_sha256,
                 "last_checked_at": f.last_checked_at.isoformat() if f.last_checked_at else None}
                for f in self.feeds.values()
            ],
            "recent_ingestions": [
                {"source_id": r.source_id, "changed": r.changed, "sha256": r.sha256,
                 "classification": r.classification, "provision_count": r.provision_count,
                 "notes": r.notes}
                for r in self.results[-10:]
            ],
            "queue_pending": self.queue.pending_count(),
            "high_impact_sla_hours": HIGH_IMPACT_SLA_HOURS,
            "stages": ["source monitor", "hash compare", "classify",
                       "provision extraction", "legal diff", "rule impact",
                       "human legal review", "two-person approval", "customer alerts"],
        }


def rule_impact_match(changed_provision_ids: list[str],
                      active_rules: dict[str, list[str]]) -> dict[str, list[str]]:
    """Which ACTIVE rules touch changed provisions (impact analysis)."""
    changed = set(changed_provision_ids)
    return {rule_id: sorted(changed & set(provs))
            for rule_id, provs in active_rules.items()
            if changed & set(provs)}
