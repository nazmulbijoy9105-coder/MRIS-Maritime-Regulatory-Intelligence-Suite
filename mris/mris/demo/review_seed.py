"""Seeded legal-review world — shared by the API and the static demo bake.

Story: the four executable rules rest on VERIFIED provisions; open items
(suspect numbering, subordinate-legislation titles) remain gated EXTRACTED_BY_AI
until closed against the official Gazette (fail-closed, Part 16 register).
"""
from __future__ import annotations

from ..engine.ingestion import IngestionPipeline, SourceFeed
from ..engine.verification import AuditChain, QueueItem, ReviewQueue


def build_review_world() -> tuple[IngestionPipeline, ReviewQueue, AuditChain]:
    audit = AuditChain()
    queue = ReviewQueue(audit)
    pipeline = IngestionPipeline(queue, audit)

    pipeline.register(SourceFeed(
        id="bd-gazette", url="https://www.bdlaws.minlaw.gov.bd",
        source_type="GAZETTE",
        publisher="Ministry of Law, Justice and Parliamentary Affairs",
        jurisdiction_id="BD"))
    pipeline.register(SourceFeed(
        id="bd-dos", url="https://www.dos.gov.bd", source_type="OFFICIAL_DB",
        publisher="Department of Shipping", jurisdiction_id="BD"))

    seeds = [
        QueueItem(id="q-demo-001", object_type="PROVISION",
                  object_id="BD-ORD-MERCHANT-SHIPPING-1983-S066",
                  title="Section 66 — Licence for taking ship to sea",
                  extracted_text="No person shall take, or attempt to take, any ship to sea unless…",
                  source_url="https://www.bdlaws.minlaw.gov.bd", confidence=0.92),
        QueueItem(id="q-demo-002", object_type="PROVISION",
                  object_id="BD-ORD-MERCHANT-SHIPPING-1983-S471",
                  title="Section 471 — Limitation of liability",
                  extracted_text="The owner of a Bangladesh ship shall not be liable…",
                  source_url="https://www.bdlaws.minlaw.gov.bd", confidence=0.71),
        QueueItem(id="q-demo-003", object_type="PROVISION",
                  object_id="BD-ACT-TERRITORIAL-WATERS-MARITIME-ZONES-1974-S022",
                  title="Section 22 — penalty for pollution (post-2021 numbering)",
                  extracted_text="If any person contravenes any provision… he shall be punishable…",
                  source_url="https://www.bdlaws.minlaw.gov.bd", confidence=0.64),
        QueueItem(id="q-demo-004", object_type="PROVISION",
                  object_id="BD-ORD-MERCHANT-SHIPPING-1983-S082",
                  title="Section 82 — Manning of ships",
                  extracted_text="Every ship registered in Bangladesh shall be manned…",
                  source_url="https://www.bdlaws.minlaw.gov.bd", confidence=0.98),
    ]
    for item in seeds:
        queue.submit(item)

    # the manning provision is fully verified (backs the live S082 rule)
    queue.review("q-demo-004", reviewer_id="reviewer-1",
                 notes="cross-checked against bdlaws consolidated text")
    queue.verify("q-demo-004", verifier_id="reviewer-2",
                 source_url="https://www.bdlaws.minlaw.gov.bd/act-81.html")
    # the pollution-numbering item is in review (needs Gazette confirmation)
    queue.review("q-demo-003", reviewer_id="reviewer-1",
                 notes="numbering cross-checked against 2021 amendment; needs Gazette confirmation")

    return pipeline, queue, audit
