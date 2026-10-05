"""P2 tests: verification workflow (two-person gate), hash-chained audit,
ingestion pipeline (delta, classification, provision boundaries)."""
from __future__ import annotations

import pytest

from mris.engine import (AuditChain, IngestionPipeline, QueueItem, ReviewQueue,
                         SourceFeed, VerificationError, VerificationTier,
                         classify, detect_provision_boundaries, provision_id,
                         rule_can_go_active, rule_impact_match)

SAMPLE = """The Bangladesh Merchant Shipping Ordinance, 1983

Section 82. Manning of ships. Every ship registered in Bangladesh shall be
manned in accordance with the safe manning document approved by the Director
General.

Section 83. Crew agreements. An agreement shall be made between the master
and each member of the crew before the ship proceeds to sea.

Article 94. Flag State duties. Every State shall effectively exercise its
jurisdiction and control in administrative, social and technical matters
over ships flying its flag.
"""


def world():
    audit = AuditChain()
    queue = ReviewQueue(audit)
    pipeline = IngestionPipeline(queue, audit)
    pipeline.register(SourceFeed(id="s1", url="https://example.gov/gazette",
                                 source_type="GAZETTE", publisher="Gazette"))
    return pipeline, queue, audit


# ---------------------------------------------------------------------------
# verification workflow
# ---------------------------------------------------------------------------

def test_review_then_verify_two_person():
    _, queue, _ = world()
    queue.submit(QueueItem(id="q1", object_type="PROVISION",
                           object_id="X-S082", title="Section 82", extracted_text="…"))

    item = queue.review("q1", reviewer_id="r1", notes="checked")
    assert item.tier is VerificationTier.REVIEWED

    # two-person rule: the reviewer may not verify their own review
    with pytest.raises(VerificationError, match="two-person"):
        queue.verify("q1", verifier_id="r1")

    item = queue.verify("q1", verifier_id="r2", source_url="https://official/gazette")
    assert item.tier is VerificationTier.VERIFIED_AGAINST_GAZETTE
    assert item.verified_by == "r2"
    assert queue.is_verified("X-S082")


def test_workflow_order_enforced():
    _, queue, _ = world()
    queue.submit(QueueItem(id="q1", object_type="PROVISION",
                           object_id="X-S1", title="t", extracted_text="…"))
    with pytest.raises(VerificationError, match="REVIEWED"):
        queue.verify("q1", verifier_id="r2")            # cannot skip review
    queue.review("q1", reviewer_id="r1")
    with pytest.raises(VerificationError, match="EXTRACTED_BY_AI"):
        queue.review("q1", reviewer_id="r2")            # cannot re-review


def test_active_gate_fail_closed():
    _, queue, _ = world()
    queue.submit(QueueItem(id="q1", object_type="PROVISION",
                           object_id="X-S1", title="t", extracted_text="…"))
    allowed, unverified = rule_can_go_active(["X-S1"], queue)
    assert not allowed and unverified == ["X-S1"]

    queue.review("q1", reviewer_id="r1")
    queue.verify("q1", verifier_id="r2")
    allowed, unverified = rule_can_go_active(["X-S1"], queue)
    assert allowed and unverified == []


# ---------------------------------------------------------------------------
# audit chain
# ---------------------------------------------------------------------------

def test_audit_chain_verifies_and_detects_tampering():
    audit = AuditChain()
    audit.append("A", "x", "1", actor="r1")
    audit.append("B", "x", "1", actor="r2", before={"a": 1}, after={"a": 2})
    ok, broken = audit.verify_chain()
    assert ok and broken is None

    # tamper with the first entry's payload
    audit.entries[0]["after"] = {"tampered": True}
    ok, broken = audit.verify_chain()
    assert not ok and broken == 0


# ---------------------------------------------------------------------------
# ingestion pipeline
# ---------------------------------------------------------------------------

def test_ingest_delta_and_noop():
    pipeline, queue, _ = world()
    r1 = pipeline.ingest("s1", SAMPLE, instrument_id="BD-ORD-TEST-1983")
    assert r1.changed and r1.classification == "INSTRUMENT"
    assert r1.provision_count == 4                  # PREAMBLE + 3 provisions
    assert queue.pending_count() == 4

    # byte-identical re-ingest is a no-op
    r2 = pipeline.ingest("s1", SAMPLE, instrument_id="BD-ORD-TEST-1983")
    assert not r2.changed and r2.provision_count == 0
    assert queue.pending_count() == 4

    # any change re-queues provision chunks (ids stable per source+index)
    r3 = pipeline.ingest("s1", SAMPLE + "\nSection 84. New rule.", instrument_id="BD-ORD-TEST-1983")
    assert r3.changed and r3.provision_count == 5
    assert queue.pending_count() == 5


def test_provision_boundaries_keep_provisos():
    chunks = detect_provision_boundaries(SAMPLE)
    assert [c["locator"] for c in chunks] == ["PREAMBLE", "Section 82", "Section 83", "Article 94"]
    # leading unattributed text is flagged low-confidence for the human queue
    assert chunks[0]["confidence"] == 0.5
    # proviso/explanation stays with its provision
    assert "safe manning document" in chunks[1]["text"]
    assert chunks[1]["confidence"] >= 0.9


def test_classification():
    assert classify("The Merchant Shipping (Amendment) Act, 2021 amends the 1974 Act") == "AMENDMENT"
    assert classify("The said Ordinance is hereby repealed") == "REPEAL"
    assert classify("Schedule of dues and tariff for Chittagong Port") == "TARIFF"
    assert classify("Circular No. 07/2025 regarding pilotage") == "NOTICE"


def test_provision_id_derivation():
    assert provision_id("BD-ORD-MS-1983", "Section 82") == "BD-ORD-MS-1983-S082"
    assert provision_id("BD-ORD-MS-1983", "Section 82A") == "BD-ORD-MS-1983-S082-SSA"
    assert provision_id("IMO-CONV-SOLAS-1974", "Regulation 19") == "IMO-CONV-SOLAS-1974-S019"


def test_rule_impact_match():
    impacts = rule_impact_match(
        ["BD-ORD-MS-1983-S082", "BD-ORD-MS-1983-S066"],
        {"R1": ["BD-ORD-MS-1983-S082"], "R2": ["BD-ORD-MS-1983-S335"],
         "R3": ["BD-ORD-MS-1983-S082", "BD-ORD-MS-1983-S350"]})
    assert impacts == {"R1": ["BD-ORD-MS-1983-S082"],
                       "R3": ["BD-ORD-MS-1983-S082"]}
