"""SQLAlchemy 2.0 models mirroring Blueprint v2.0 Part 8 (core tables).

The authoritative schema for deployment is
    infra/db/migrations/001_initial_schema.sql   (PostgreSQL 16: RLS, GIN, BRIN)
These ORM models give the application layer typed access on any backend
(SQLite for dev/tests, PostgreSQL in production).
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import (JSON, Boolean, Date, DateTime, Float, ForeignKey,
                        Integer, String, Text, create_engine)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

AUDIT_STATUS = ("EXTRACTED_BY_AI", "REVIEWED", "VERIFIED_AGAINST_GAZETTE")
LEGAL_STATUS = ("IN_FORCE", "AMENDED", "REPEALED", "SUPERSEDED", "DRAFT",
                "FUTURE_EFFECTIVE", "SUSPENDED")
STATUS4 = ("GREEN", "YELLOW", "RED", "BLACK")
VERIFICATION = ("UNVERIFIED", "VERIFIED", "EXPIRED", "REVOKED", "FORGED_SUSPECT")


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# 8.1 legal core
# ---------------------------------------------------------------------------

class Jurisdiction(Base):
    __tablename__ = "jurisdiction"
    id: Mapped[str] = mapped_column(String(8), primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    iso3166: Mapped[str] = mapped_column(String(2))
    region: Mapped[Optional[str]] = mapped_column(String(64))
    is_flag_state: Mapped[bool] = mapped_column(Boolean, default=False)
    is_port_state: Mapped[bool] = mapped_column(Boolean, default=False)
    is_coastal_state: Mapped[bool] = mapped_column(Boolean, default=False)


class Authority(Base):
    __tablename__ = "authority"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    jurisdiction_id: Mapped[Optional[str]] = mapped_column(ForeignKey("jurisdiction.id"))
    name: Mapped[str] = mapped_column(String(256))
    url: Mapped[Optional[str]] = mapped_column(String(512))


class LegalInstrument(Base):
    __tablename__ = "legal_instrument"
    id: Mapped[str] = mapped_column(String(128), primary_key=True)   # BD-ORD-MERCHANT-SHIPPING-1983
    jurisdiction_id: Mapped[Optional[str]] = mapped_column(ForeignKey("jurisdiction.id"))
    authority_id: Mapped[Optional[str]] = mapped_column(ForeignKey("authority.id"))
    instrument_type: Mapped[str] = mapped_column(String(16))
    title: Mapped[str] = mapped_column(Text)
    citation: Mapped[Optional[str]] = mapped_column(String(256))
    enacted_date: Mapped[Optional[date]] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(24))
    verification_status: Mapped[str] = mapped_column(String(32), default="EXTRACTED_BY_AI")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class SourceRegistry(Base):
    __tablename__ = "source_registry"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    instrument_id: Mapped[Optional[str]] = mapped_column(ForeignKey("legal_instrument.id"))
    source_type: Mapped[str] = mapped_column(String(32))
    url: Mapped[Optional[str]] = mapped_column(String(1024))
    file_path: Mapped[Optional[str]] = mapped_column(String(1024))
    sha256: Mapped[str] = mapped_column(String(64))
    retrieved_at: Mapped[datetime] = mapped_column(DateTime)
    publisher: Mapped[Optional[str]] = mapped_column(String(256))


class LegalVersion(Base):
    __tablename__ = "legal_version"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    instrument_id: Mapped[str] = mapped_column(ForeignKey("legal_instrument.id"))
    version_no: Mapped[int] = mapped_column(Integer)
    basis: Mapped[str] = mapped_column(String(64))          # ORIGINAL|AMENDMENT:{id}|...
    effective_from: Mapped[date] = mapped_column(Date)
    effective_to: Mapped[Optional[date]] = mapped_column(Date)
    source_id: Mapped[Optional[str]] = mapped_column(ForeignKey("source_registry.id"))


class LegalProvision(Base):
    __tablename__ = "legal_provision"
    id: Mapped[str] = mapped_column(String(160), primary_key=True)  # {INSTRUMENT_ID}-S{###}
    instrument_id: Mapped[str] = mapped_column(ForeignKey("legal_instrument.id"))
    locator: Mapped[str] = mapped_column(String(64))
    parent_id: Mapped[Optional[str]] = mapped_column(ForeignKey("legal_provision.id"))
    title: Mapped[Optional[str]] = mapped_column(String(512))
    text: Mapped[str] = mapped_column(Text)
    verification_status: Mapped[str] = mapped_column(String(32), default="EXTRACTED_BY_AI")


class ProvisionValidity(Base):
    __tablename__ = "provision_validity"
    provision_id: Mapped[str] = mapped_column(ForeignKey("legal_provision.id"), primary_key=True)
    version_id: Mapped[str] = mapped_column(ForeignKey("legal_version.id"), primary_key=True)
    valid_from: Mapped[date] = mapped_column(Date)
    valid_to: Mapped[Optional[date]] = mapped_column(Date)


class Amendment(Base):
    __tablename__ = "amendment"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    amending_instrument_id: Mapped[Optional[str]] = mapped_column(ForeignKey("legal_instrument.id"))
    target_instrument_id: Mapped[str] = mapped_column(ForeignKey("legal_instrument.id"))
    operation: Mapped[str] = mapped_column(String(16))
    target_provision_id: Mapped[Optional[str]] = mapped_column(ForeignKey("legal_provision.id"))
    effective_from: Mapped[date] = mapped_column(Date)
    verification_status: Mapped[str] = mapped_column(String(32), default="EXTRACTED_BY_AI")
    reviewer_id: Mapped[Optional[str]] = mapped_column(String(36))
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime)


class Repeal(Base):
    __tablename__ = "repeal"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    instrument_id: Mapped[str] = mapped_column(ForeignKey("legal_instrument.id"))
    repealed_by_instrument_id: Mapped[Optional[str]] = mapped_column(ForeignKey("legal_instrument.id"))
    repeal_date: Mapped[date] = mapped_column(Date)
    replacement_instrument_id: Mapped[Optional[str]] = mapped_column(ForeignKey("legal_instrument.id"))
    transitional_rules: Mapped[Optional[dict]] = mapped_column(JSON)
    historical_retention: Mapped[bool] = mapped_column(Boolean, default=True)  # P4


class StateParticipation(Base):
    __tablename__ = "state_participation"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    instrument_id: Mapped[Optional[str]] = mapped_column(ForeignKey("legal_instrument.id"))
    jurisdiction_id: Mapped[Optional[str]] = mapped_column(ForeignKey("jurisdiction.id"))
    ratification_date: Mapped[Optional[date]] = mapped_column(Date)
    entry_into_force_for_state: Mapped[Optional[date]] = mapped_column(Date)
    amendment_effective_for_state: Mapped[Optional[date]] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(32))
    source_url: Mapped[Optional[str]] = mapped_column(String(1024))
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime)


# ---------------------------------------------------------------------------
# 8.2 rule engine
# ---------------------------------------------------------------------------

class Rule(Base):
    __tablename__ = "rule"
    id: Mapped[str] = mapped_column(String(160), primary_key=True)   # {PROVISION_ID}-R{###}
    provision_id: Mapped[str] = mapped_column(ForeignKey("legal_provision.id"))
    domain: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16), default="DRAFT")


class RuleVersion(Base):
    __tablename__ = "rule_version"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    rule_id: Mapped[str] = mapped_column(ForeignKey("rule.id"))
    version_no: Mapped[int] = mapped_column(Integer)
    legal_version_id: Mapped[str] = mapped_column(ForeignKey("legal_version.id"))
    definition: Mapped[dict] = mapped_column(JSON)                  # ILRMF-DSL AST
    effective_from: Mapped[date] = mapped_column(Date)
    effective_to: Mapped[Optional[date]] = mapped_column(Date)
    created_by: Mapped[Optional[str]] = mapped_column(String(36))
    reviewed_by: Mapped[Optional[str]] = mapped_column(String(36))
    approved_by: Mapped[Optional[str]] = mapped_column(String(36))
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime)


class RuleEvaluationLog(Base):
    __tablename__ = "rule_evaluation_log"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    company_id: Mapped[str] = mapped_column(String(36))             # tenant key
    rule_version_id: Mapped[Optional[str]] = mapped_column(ForeignKey("rule_version.id"))
    entity_type: Mapped[str] = mapped_column(String(32))
    entity_id: Mapped[str] = mapped_column(String(64))
    eval_date: Mapped[date] = mapped_column(Date)
    input_facts: Mapped[dict] = mapped_column(JSON)
    output: Mapped[dict] = mapped_column(JSON)
    status_result: Mapped[str] = mapped_column(String(8))
    engine_version: Mapped[str] = mapped_column(String(32))
    computed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ---------------------------------------------------------------------------
# 8.3 entities incl. crew
# ---------------------------------------------------------------------------

class Company(Base):
    __tablename__ = "company"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(256))
    imo_number: Mapped[Optional[str]] = mapped_column(String(16), unique=True)
    country: Mapped[Optional[str]] = mapped_column(ForeignKey("jurisdiction.id"))
    doc_issuer: Mapped[Optional[str]] = mapped_column(String(64))
    type: Mapped[Optional[str]] = mapped_column(String(16))


class Vessel(Base):
    __tablename__ = "vessel"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    company_id: Mapped[Optional[str]] = mapped_column(ForeignKey("company.id"))
    name: Mapped[str] = mapped_column(String(256))
    imo_number: Mapped[str] = mapped_column(String(16), unique=True)
    flag: Mapped[Optional[str]] = mapped_column(ForeignKey("jurisdiction.id"))
    gross_tonnage: Mapped[Optional[float]] = mapped_column(Float)
    net_tonnage: Mapped[Optional[float]] = mapped_column(Float)
    deadweight: Mapped[Optional[float]] = mapped_column(Float)
    ship_type: Mapped[str] = mapped_column(String(32))
    keel_laid_date: Mapped[Optional[date]] = mapped_column(Date)
    build_date: Mapped[Optional[date]] = mapped_column(Date)
    class_society: Mapped[Optional[str]] = mapped_column(String(64))
    ism_doc_no: Mapped[Optional[str]] = mapped_column(String(64))
    smc_no: Mapped[Optional[str]] = mapped_column(String(64))


class Voyage(Base):
    __tablename__ = "voyage"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    company_id: Mapped[str] = mapped_column(String(36))
    vessel_id: Mapped[Optional[str]] = mapped_column(ForeignKey("vessel.id"))
    port_from: Mapped[Optional[str]] = mapped_column(String(128))
    port_to: Mapped[Optional[str]] = mapped_column(String(128))
    cargo: Mapped[Optional[dict]] = mapped_column(JSON)
    phase: Mapped[Optional[str]] = mapped_column(String(16))


class VoyageLeg(Base):
    __tablename__ = "voyage_leg"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    voyage_id: Mapped[str] = mapped_column(ForeignKey("voyage.id"))
    seq: Mapped[int] = mapped_column(Integer)
    from_port: Mapped[Optional[str]] = mapped_column(String(128))
    to_port: Mapped[Optional[str]] = mapped_column(String(128))
    zone_type: Mapped[str] = mapped_column(String(24))
    coastal_state: Mapped[Optional[str]] = mapped_column(ForeignKey("jurisdiction.id"))
    from_date: Mapped[Optional[date]] = mapped_column(Date)
    to_date: Mapped[Optional[date]] = mapped_column(Date)


class JurisdictionSegment(Base):
    __tablename__ = "jurisdiction_segment"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    leg_id: Mapped[str] = mapped_column(ForeignKey("voyage_leg.id"))
    layer: Mapped[str] = mapped_column(String(16))
    jurisdiction_id: Mapped[Optional[str]] = mapped_column(ForeignKey("jurisdiction.id"))
    as_of_date: Mapped[date] = mapped_column(Date)


class Seafarer(Base):
    __tablename__ = "seafarer"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    company_id: Mapped[str] = mapped_column(String(36))             # tenant key
    full_name: Mapped[str] = mapped_column(String(256))
    date_of_birth: Mapped[Optional[date]] = mapped_column(Date)
    nationality: Mapped[Optional[str]] = mapped_column(String(64))
    passport_no: Mapped[Optional[str]] = mapped_column(String(64))
    seafarer_id_no: Mapped[Optional[str]] = mapped_column(String(64))
    rank: Mapped[Optional[str]] = mapped_column(String(64))


class CrewAssignment(Base):
    __tablename__ = "crew_assignment"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    seafarer_id: Mapped[str] = mapped_column(ForeignKey("seafarer.id"))
    vessel_id: Mapped[str] = mapped_column(ForeignKey("vessel.id"))
    voyage_id: Mapped[Optional[str]] = mapped_column(ForeignKey("voyage.id"))
    rank_on_board: Mapped[str] = mapped_column(String(64))
    joined_at: Mapped[date] = mapped_column(Date)
    left_at: Mapped[Optional[date]] = mapped_column(Date)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True)


class CrewCertificate(Base):
    __tablename__ = "crew_certificate"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    seafarer_id: Mapped[str] = mapped_column(ForeignKey("seafarer.id"))
    cert_type: Mapped[str] = mapped_column(String(64))
    cert_no: Mapped[Optional[str]] = mapped_column(String(64))
    issuer: Mapped[Optional[str]] = mapped_column(String(128))
    issue_date: Mapped[Optional[date]] = mapped_column(Date)
    expiry_date: Mapped[Optional[date]] = mapped_column(Date)
    flag_endorsement: Mapped[Optional[str]] = mapped_column(String(64))
    verification_status: Mapped[str] = mapped_column(String(24), default="UNVERIFIED")


class CrewContract(Base):
    __tablename__ = "crew_contract"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    seafarer_id: Mapped[str] = mapped_column(ForeignKey("seafarer.id"))
    vessel_id: Mapped[Optional[str]] = mapped_column(ForeignKey("vessel.id"))
    company_id: Mapped[str] = mapped_column(String(36))
    signed_date: Mapped[Optional[date]] = mapped_column(Date)
    start_date: Mapped[Optional[date]] = mapped_column(Date)
    end_date: Mapped[Optional[date]] = mapped_column(Date)
    wage_amount: Mapped[Optional[float]] = mapped_column(Float)
    wage_currency: Mapped[Optional[str]] = mapped_column(String(8))
    abandonment_risk_flag: Mapped[bool] = mapped_column(Boolean, default=False)


# ---------------------------------------------------------------------------
# 8.4-8.5 evidence, results, overrides, audit
# ---------------------------------------------------------------------------

class Evidence(Base):
    __tablename__ = "evidence"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    company_id: Mapped[str] = mapped_column(String(36))             # tenant key
    entity_type: Mapped[str] = mapped_column(String(32))
    entity_id: Mapped[str] = mapped_column(String(64))
    evidence_type: Mapped[str] = mapped_column(String(64))
    certificate_no: Mapped[Optional[str]] = mapped_column(String(64))
    issuer: Mapped[Optional[str]] = mapped_column(String(128))
    issue_date: Mapped[Optional[date]] = mapped_column(Date)
    expiry_date: Mapped[Optional[date]] = mapped_column(Date)
    file_path: Mapped[Optional[str]] = mapped_column(String(1024))
    sha256: Mapped[Optional[str]] = mapped_column(String(64))
    verification_status: Mapped[str] = mapped_column(String(24), default="UNVERIFIED")


class ComplianceResult(Base):
    __tablename__ = "compliance_result"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    company_id: Mapped[str] = mapped_column(String(36))
    entity_type: Mapped[str] = mapped_column(String(32))
    entity_id: Mapped[str] = mapped_column(String(64))
    as_of_date: Mapped[date] = mapped_column(Date)
    overall_status: Mapped[str] = mapped_column(String(8))
    law_versions_used: Mapped[dict] = mapped_column(JSON)
    rule_versions_used: Mapped[dict] = mapped_column(JSON)
    computed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    items: Mapped[list["ComplianceResultItem"]] = relationship(back_populates="result")


class ComplianceResultItem(Base):
    __tablename__ = "compliance_result_item"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    result_id: Mapped[Optional[str]] = mapped_column(ForeignKey("compliance_result.id"))
    obligation_id: Mapped[Optional[str]] = mapped_column(String(160))
    rule_version_id: Mapped[Optional[str]] = mapped_column(ForeignKey("rule_version.id"))
    provision_id: Mapped[Optional[str]] = mapped_column(ForeignKey("legal_provision.id"))
    layer: Mapped[Optional[str]] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(8))
    reason: Mapped[str] = mapped_column(Text)
    required_action: Mapped[Optional[str]] = mapped_column(Text)
    deadline: Mapped[Optional[date]] = mapped_column(Date)
    evidence_id: Mapped[Optional[str]] = mapped_column(ForeignKey("evidence.id"))
    result: Mapped[Optional[ComplianceResult]] = relationship(back_populates="items")


class Override(Base):
    __tablename__ = "override"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    result_item_id: Mapped[Optional[str]] = mapped_column(ForeignKey("compliance_result_item.id"))
    rule_version_id: Mapped[Optional[str]] = mapped_column(ForeignKey("rule_version.id"))   # P14
    legal_version_id: Mapped[Optional[str]] = mapped_column(ForeignKey("legal_version.id"))  # P14
    override_type: Mapped[str] = mapped_column(String(24))
    justification: Mapped[str] = mapped_column(Text)
    supporting_authority: Mapped[Optional[str]] = mapped_column(Text)
    authorized_by: Mapped[str] = mapped_column(String(36))
    authorized_at: Mapped[datetime] = mapped_column(DateTime)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime)


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    company_id: Mapped[Optional[str]] = mapped_column(String(36))
    actor_id: Mapped[Optional[str]] = mapped_column(String(36))
    action: Mapped[str] = mapped_column(String(64))
    object_type: Mapped[Optional[str]] = mapped_column(String(32))
    object_id: Mapped[Optional[str]] = mapped_column(String(64))
    before: Mapped[Optional[dict]] = mapped_column(JSON)
    after: Mapped[Optional[dict]] = mapped_column(JSON)
    at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    prev_hash: Mapped[Optional[str]] = mapped_column(String(64))    # Part 18 hash chain
    entry_hash: Mapped[Optional[str]] = mapped_column(String(64))


def init_db(url: str = "sqlite:///mris-dev.db"):
    """Dev/test helper. Production uses infra/db/migrations/001_initial_schema.sql."""
    engine = create_engine(url, echo=False)
    Base.metadata.create_all(engine)
    return engine


# --- Auth & User Management ---
from sqlalchemy import Column, Integer, String

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    company_name = Column(String)
