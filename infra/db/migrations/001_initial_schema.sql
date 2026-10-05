-- MRIS — PostgreSQL 16 initial schema (Blueprint v2.0, Part 8)
-- Migration 001: complete legal core, rule engine, entities, evidence,
-- compliance, audit, and module tables (cyber/incident/shipbuilding/
-- shipyard/liability/recycling) with tenancy RLS + index strategy.
--
-- Principles enforced here:
--   P1  instrument immutability      P2  version everything
--   P3  temporal validity            P4  repealed != deleted
--   P13 tenant isolation (RLS)       P14 overrides version-pinned
--   P8  result = f(law_version, rule_version, facts)
--
-- Requires: PostgreSQL 16, extensions pgcrypto (gen_random_uuid),
-- pg_trgm (fuzzy legal search).

BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ---------------------------------------------------------------------------
-- 8.1 LEGAL CORE
-- ---------------------------------------------------------------------------

CREATE TABLE id_registry (                       -- v2.0: canonical ID enforcement (audit fix #7)
    id TEXT PRIMARY KEY,
    id_type TEXT NOT NULL CHECK (id_type IN ('INSTRUMENT','PROVISION','RULE','AMENDMENT')),
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE jurisdiction (
    id TEXT PRIMARY KEY,                         -- 'BD','PA','SG'
    name TEXT NOT NULL,
    iso3166 CHAR(2) NOT NULL,
    region TEXT,
    is_flag_state BOOL DEFAULT false,
    is_port_state BOOL DEFAULT false,
    is_coastal_state BOOL DEFAULT false
);

CREATE TABLE authority (
    id TEXT PRIMARY KEY,                         -- 'BD-DOS','BD-CPA','IMO','ILO'
    jurisdiction_id TEXT REFERENCES jurisdiction(id),
    name TEXT NOT NULL,
    url TEXT
);

CREATE TABLE legal_instrument (
    id TEXT PRIMARY KEY,                         -- BD-ORD-MERCHANT-SHIPPING-1983
    jurisdiction_id TEXT REFERENCES jurisdiction(id),
    authority_id TEXT REFERENCES authority(id),
    instrument_type TEXT NOT NULL CHECK (instrument_type IN
        ('ACT','ORD','RULES','REG','SRO','ORDER','AMEND','CONV','PROTOCOL',
         'CODE','CIRC','NOTICE','TARIFF')),
    title TEXT NOT NULL,
    citation TEXT,                               -- 'Ordinance No. XXVI of 1983'
    enacted_date DATE,
    status TEXT NOT NULL CHECK (status IN
        ('IN_FORCE','AMENDED','REPEALED','SUPERSEDED','DRAFT','FUTURE_EFFECTIVE','SUSPENDED')),
    verification_status TEXT NOT NULL DEFAULT 'EXTRACTED_BY_AI'
        CHECK (verification_status IN ('EXTRACTED_BY_AI','REVIEWED','VERIFIED_AGAINST_GAZETTE')),
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE source_registry (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    instrument_id TEXT REFERENCES legal_instrument(id),
    source_type TEXT NOT NULL CHECK (source_type IN
        ('GAZETTE','OFFICIAL_DB','CONSOLIDATED_UNOFFICIAL','CLASS_CERTIFICATE',
         'CIRCULAR','NOTICE','TARIFF','CONTRACTUAL_REFERENCE')),
    url TEXT,
    file_path TEXT,
    sha256 TEXT NOT NULL,                        -- content hash for change detection (Part 11)
    retrieved_at TIMESTAMPTZ NOT NULL,
    publisher TEXT
);
CREATE INDEX idx_source_instrument ON source_registry (instrument_id, retrieved_at);
CREATE INDEX idx_source_sha ON source_registry (sha256);

CREATE TABLE legal_version (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    instrument_id TEXT NOT NULL REFERENCES legal_instrument(id),
    version_no INT NOT NULL,                     -- 1 = original
    basis TEXT NOT NULL,                         -- ORIGINAL|AMENDMENT:{id}|CONSOLIDATION|CORRECTION
    effective_from DATE NOT NULL,
    effective_to DATE,                           -- NULL = open-ended (Principle 3)
    source_id UUID REFERENCES source_registry(id),
    UNIQUE(instrument_id, version_no)
);
CREATE INDEX idx_legal_version_temporal ON legal_version (instrument_id, effective_from, effective_to);

CREATE TABLE legal_provision (
    id TEXT PRIMARY KEY,                         -- {INSTRUMENT_ID}-S{###}  derived, never free text (§4.2)
    instrument_id TEXT NOT NULL REFERENCES legal_instrument(id),
    locator TEXT NOT NULL,                       -- 'Section 82' / 'Regulation 19' / 'Article 94'
    parent_id TEXT REFERENCES legal_provision(id),
    title TEXT,
    text TEXT NOT NULL,
    verification_status TEXT NOT NULL DEFAULT 'EXTRACTED_BY_AI'
        CHECK (verification_status IN ('EXTRACTED_BY_AI','REVIEWED','VERIFIED_AGAINST_GAZETTE')),
    tsv tsvector GENERATED ALWAYS AS (to_tsvector('english', text)) STORED,
    UNIQUE(instrument_id, locator)
);
CREATE INDEX idx_provision_tsv ON legal_provision USING GIN (tsv);
CREATE INDEX idx_provision_trgm ON legal_provision USING GIN (text gin_trgm_ops);  -- fuzzy citation match
CREATE INDEX idx_provision_parent ON legal_provision (parent_id);

CREATE TABLE provision_validity (                -- temporal interval per provision per version
    provision_id TEXT REFERENCES legal_provision(id),
    version_id UUID REFERENCES legal_version(id),
    valid_from DATE NOT NULL,
    valid_to DATE,
    PRIMARY KEY (provision_id, version_id)
);
CREATE INDEX idx_prov_validity_window ON provision_validity (provision_id, valid_from, valid_to);

CREATE TABLE amendment (
    id TEXT PRIMARY KEY,                         -- BD-AMEND-TWMZ-2021-001
    amending_instrument_id TEXT REFERENCES legal_instrument(id),
    target_instrument_id TEXT NOT NULL REFERENCES legal_instrument(id),
    operation TEXT NOT NULL CHECK (operation IN
        ('INSERT','SUBSTITUTE','DELETE','OMIT','RENUMBER','REPEAL')),
    target_provision_id TEXT REFERENCES legal_provision(id),
    effective_from DATE NOT NULL,
    verification_status TEXT NOT NULL DEFAULT 'EXTRACTED_BY_AI'
        CHECK (verification_status IN ('EXTRACTED_BY_AI','REVIEWED','VERIFIED_AGAINST_GAZETTE')),
    reviewer_id UUID,
    approved_at TIMESTAMPTZ
);
CREATE INDEX idx_amendment_target ON amendment (target_instrument_id, effective_from);

CREATE TABLE repeal (
    id TEXT PRIMARY KEY,
    instrument_id TEXT NOT NULL REFERENCES legal_instrument(id),
    repealed_by_instrument_id TEXT REFERENCES legal_instrument(id),
    repealed_by_provision_id TEXT REFERENCES legal_provision(id),
    repeal_date DATE NOT NULL,
    replacement_instrument_id TEXT REFERENCES legal_instrument(id),
    transitional_rules JSONB,
    historical_retention BOOL NOT NULL DEFAULT true   -- Principle 4: repealed law is never deleted
);

CREATE TABLE state_participation (               -- §6.5: what makes "in force FOR THE FLAG" answerable
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    instrument_id TEXT REFERENCES legal_instrument(id),
    jurisdiction_id TEXT REFERENCES jurisdiction(id),
    signature_date DATE, ratification_date DATE, accession_date DATE,
    acceptance_date DATE,
    entry_into_force_for_state DATE,
    denunciation_date DATE,
    reservation TEXT, declaration TEXT,
    amendment_id TEXT REFERENCES amendment(id),
    amendment_effective_for_state DATE,
    status TEXT NOT NULL,
    source_url TEXT,
    verified_at TIMESTAMPTZ
);
CREATE INDEX idx_state_party ON state_participation (instrument_id, jurisdiction_id);

-- ---------------------------------------------------------------------------
-- 8.2 RULE ENGINE
-- ---------------------------------------------------------------------------

CREATE TABLE rule (
    id TEXT PRIMARY KEY,                         -- {PROVISION_ID}-R{###}
    provision_id TEXT NOT NULL REFERENCES legal_provision(id),
    domain TEXT NOT NULL,                        -- MANNING|CERT|LOADLINE|UNSEAWORTHY|MARPOL|ISM|ISPS|MLC|CYBER|INCIDENT|...
    status TEXT NOT NULL DEFAULT 'DRAFT' CHECK (status IN
        ('DRAFT','IN_REVIEW','ACTIVE','DEPRECATED','RETIRED'))
);
CREATE INDEX idx_rule_provision ON rule (provision_id);
CREATE INDEX idx_rule_domain ON rule (domain, status);

CREATE TABLE rule_version (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_id TEXT NOT NULL REFERENCES rule(id),
    version_no INT NOT NULL,
    legal_version_id UUID NOT NULL REFERENCES legal_version(id),
    definition JSONB NOT NULL,                   -- ILRMF-DSL AST (Part 9.3)
    effective_from DATE NOT NULL,
    effective_to DATE,
    created_by UUID, reviewed_by UUID, approved_by UUID,   -- Principle 12: human gate; author != approver
    approved_at TIMESTAMPTZ,
    UNIQUE(rule_id, version_no)
);
CREATE INDEX idx_rule_version_active ON rule_version (rule_id, effective_from, effective_to);

CREATE TABLE rule_evaluation_log (               -- every execution, immutable (Principle 8)
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL,                    -- tenant key (audit fix #8)
    rule_version_id UUID REFERENCES rule_version(id),
    entity_type TEXT NOT NULL,                   -- VESSEL|COMPANY|VOYAGE|CREW|PORT|SHIPYARD|...
    entity_id TEXT NOT NULL,
    eval_date DATE NOT NULL,
    input_facts JSONB NOT NULL,
    output JSONB NOT NULL,
    status_result TEXT NOT NULL CHECK (status_result IN ('GREEN','YELLOW','RED','BLACK')),
    engine_version TEXT NOT NULL,
    computed_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_eval_entity_date ON rule_evaluation_log (entity_id, eval_date);      -- audit fix #2
CREATE INDEX idx_eval_tenant      ON rule_evaluation_log (company_id, computed_at);
CREATE INDEX idx_eval_facts_gin   ON rule_evaluation_log USING GIN (input_facts jsonb_path_ops);
CREATE INDEX idx_eval_output_gin  ON rule_evaluation_log USING GIN (output jsonb_path_ops);
CREATE INDEX idx_eval_computed_brin ON rule_evaluation_log USING BRIN (computed_at);  -- §8.8 BRIN

-- ---------------------------------------------------------------------------
-- 8.3 ENTITIES (incl. crew — audit fix #1)
-- ---------------------------------------------------------------------------

CREATE TABLE company (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    imo_number TEXT UNIQUE,
    country TEXT REFERENCES jurisdiction(id),
    doc_issuer TEXT,                             -- ISM DOC issuing administration
    type TEXT CHECK (type IN ('OWNER','MANAGER','AGENT','RECYCLER','TERMINAL','SHIPYARD','BUILDER'))
);

CREATE TABLE vessel (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID REFERENCES company(id),
    name TEXT NOT NULL,
    imo_number TEXT UNIQUE NOT NULL,
    flag TEXT REFERENCES jurisdiction(id),
    gross_tonnage NUMERIC, net_tonnage NUMERIC, deadweight NUMERIC,
    ship_type TEXT NOT NULL,
    keel_laid_date DATE,                         -- drives construction-era applicability (§9.4)
    build_date DATE,
    class_society TEXT,
    ism_doc_no TEXT, smc_no TEXT
);
CREATE INDEX idx_vessel_company ON vessel (company_id);
CREATE INDEX idx_vessel_flag    ON vessel (flag);

CREATE TABLE voyage (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL,
    vessel_id UUID REFERENCES vessel(id),
    port_from TEXT, port_to TEXT,
    eta TIMESTAMPTZ, etd TIMESTAMPTZ,
    cargo JSONB,
    phase TEXT CHECK (phase IN ('PRE_VOYAGE','AT_SEA','IN_PORT','AT_BERTH'))
);

CREATE TABLE voyage_leg (                         -- v2.0: multi-jurisdiction resolution (audit fix #6)
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    voyage_id UUID NOT NULL REFERENCES voyage(id),
    seq INT NOT NULL,
    from_port TEXT, to_port TEXT,
    zone_type TEXT NOT NULL CHECK (zone_type IN
        ('INTERNAL_WATERS','TERRITORIAL','CONTIGUOUS','EEZ','CONTINENTAL_SHELF','HIGH_SEAS')),
    coastal_state TEXT REFERENCES jurisdiction(id),
    from_date DATE, to_date DATE
);
CREATE INDEX idx_leg_voyage ON voyage_leg (voyage_id, seq);

CREATE TABLE jurisdiction_segment (               -- the applicability context of a leg
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    leg_id UUID NOT NULL REFERENCES voyage_leg(id),
    layer TEXT NOT NULL CHECK (layer IN
        ('L1_INTL','L2_FLAG','L3_COASTAL','L4_PORT','L5_CLASS','L6_CONTRACT')),
    jurisdiction_id TEXT REFERENCES jurisdiction(id),
    as_of_date DATE NOT NULL
);
CREATE INDEX idx_segment_leg ON jurisdiction_segment (leg_id, layer);

CREATE TABLE seafarer (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL,                    -- tenant key
    full_name TEXT NOT NULL,
    date_of_birth DATE,
    nationality TEXT,
    passport_no TEXT, seafarer_id_no TEXT,
    rank TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_seafarer_company ON seafarer (company_id);

CREATE TABLE crew_assignment (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    seafarer_id UUID NOT NULL REFERENCES seafarer(id),
    vessel_id UUID NOT NULL REFERENCES vessel(id),
    voyage_id UUID REFERENCES voyage(id),
    rank_on_board TEXT NOT NULL,
    joined_at DATE NOT NULL,
    left_at DATE,
    is_current BOOL NOT NULL DEFAULT true
);
CREATE INDEX idx_crewassign_vessel ON crew_assignment (vessel_id, is_current);

CREATE TABLE crew_certificate (                   -- CoC, CoP, flag endorsements, medicals, GMDSS
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    seafarer_id UUID NOT NULL REFERENCES seafarer(id),
    cert_type TEXT NOT NULL,
    cert_no TEXT, issuer TEXT,
    issue_date DATE, expiry_date DATE,
    flag_endorsement TEXT,
    verification_status TEXT NOT NULL DEFAULT 'UNVERIFIED'
        CHECK (verification_status IN ('UNVERIFIED','VERIFIED','EXPIRED','REVOKED','FORGED_SUSPECT'))
);
CREATE INDEX idx_crewcert_expiry ON crew_certificate (seafarer_id, expiry_date);

CREATE TABLE crew_contract (                      -- MLC employment agreement tracking
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    seafarer_id UUID NOT NULL REFERENCES seafarer(id),
    vessel_id UUID REFERENCES vessel(id),
    company_id UUID NOT NULL,
    signed_date DATE, start_date DATE, end_date DATE,
    wage_amount NUMERIC, wage_currency TEXT,
    repatriation_terms TEXT,
    abandonment_risk_flag BOOL DEFAULT false
);

-- ---------------------------------------------------------------------------
-- 8.4 EVIDENCE
-- ---------------------------------------------------------------------------

CREATE TABLE evidence (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL,                     -- tenant key
    entity_type TEXT NOT NULL,                    -- VESSEL|COMPANY|VOYAGE|CREW|PORT|SHIPYARD|SHIP_PROJECT
    entity_id TEXT NOT NULL,
    evidence_type TEXT NOT NULL,                  -- CERTIFICATE|LICENCE|DOC|INSPECTION|SURVEY|INSURANCE
    certificate_no TEXT, issuer TEXT,
    issue_date DATE, expiry_date DATE,
    file_path TEXT, sha256 TEXT,
    verification_status TEXT NOT NULL DEFAULT 'UNVERIFIED'
        CHECK (verification_status IN ('UNVERIFIED','VERIFIED','EXPIRED','REVOKED','FORGED_SUSPECT'))
);
CREATE INDEX idx_evidence_entity ON evidence (entity_id, evidence_type);
CREATE INDEX idx_evidence_expiry ON evidence (expiry_date) WHERE expiry_date IS NOT NULL;
CREATE INDEX idx_evidence_tenant ON evidence (company_id);

CREATE TABLE cert_to_rule (                       -- Part 10: provision -> acceptable evidence types
    provision_id TEXT NOT NULL REFERENCES legal_provision(id),
    evidence_type TEXT NOT NULL,
    PRIMARY KEY (provision_id, evidence_type)
);

-- ---------------------------------------------------------------------------
-- 8.5 COMPLIANCE RESULTS + OVERRIDES + AUDIT
-- ---------------------------------------------------------------------------

CREATE TABLE compliance_result (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL,
    entity_type TEXT NOT NULL, entity_id TEXT NOT NULL,
    as_of_date DATE NOT NULL,
    overall_status TEXT NOT NULL CHECK (overall_status IN ('GREEN','YELLOW','RED','BLACK')),
    law_versions_used JSONB NOT NULL,             -- snapshot of every legal_version used
    rule_versions_used JSONB NOT NULL,
    computed_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(entity_type, entity_id, as_of_date)
);
CREATE INDEX idx_result_entity_date ON compliance_result (entity_id, as_of_date);
CREATE INDEX idx_result_tenant_status ON compliance_result (company_id, overall_status);

CREATE TABLE compliance_result_item (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    result_id UUID REFERENCES compliance_result(id),
    obligation_id TEXT,
    rule_version_id UUID REFERENCES rule_version(id),
    provision_id TEXT REFERENCES legal_provision(id),
    layer TEXT CHECK (layer IN ('L1_INTL','L2_FLAG','L3_COASTAL','L4_PORT','L5_CLASS','L6_CONTRACT')),
    status TEXT NOT NULL CHECK (status IN ('GREEN','YELLOW','RED','BLACK')),
    reason TEXT NOT NULL,                         -- human-readable justification chain (Result contract Z)
    required_action TEXT,
    deadline DATE,
    evidence_id UUID REFERENCES evidence(id)
);
CREATE INDEX idx_result_item ON compliance_result_item (result_id, status);

CREATE TABLE override (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    result_item_id UUID REFERENCES compliance_result_item(id),
    rule_version_id UUID REFERENCES rule_version(id),        -- v2.0 (audit fix #3): version-pinned
    legal_version_id UUID REFERENCES legal_version(id),
    override_type TEXT NOT NULL CHECK (override_type IN
        ('LEGAL_REVIEW','EQUIVALENCY','EXEMPTION','EMERGENCY')),
    justification TEXT NOT NULL,
    supporting_authority TEXT,
    authorized_by UUID NOT NULL,                  -- must hold LEGAL_REVIEWER role (enforced in app)
    authorized_at TIMESTAMPTZ NOT NULL,
    expires_at TIMESTAMPTZ
);
CREATE INDEX idx_override_item ON override (result_item_id);

CREATE TABLE audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID,                              -- tenant key (NULL = platform-level event)
    actor_id UUID,
    action TEXT NOT NULL,
    object_type TEXT, object_id TEXT,
    before JSONB, after JSONB,
    at TIMESTAMPTZ DEFAULT now(),
    prev_hash TEXT,                               -- hash chain (Part 18): HMAC of previous entry
    entry_hash TEXT
);
CREATE INDEX idx_audit_object ON audit_log (object_type, object_id, at);
CREATE INDEX idx_audit_tenant ON audit_log (company_id, at);
CREATE INDEX idx_audit_at_brin ON audit_log USING BRIN (at);
REVOKE UPDATE, DELETE ON audit_log FROM PUBLIC;   -- append-only (Part 18)

-- ---------------------------------------------------------------------------
-- 8.6 MODULE TABLES (audit fix #4) — 13_CYBER / 14_INCIDENT / 11 / 12 / 15
-- ---------------------------------------------------------------------------

CREATE TABLE data_inventory (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL,
    entity_type TEXT NOT NULL,                    -- VESSEL|COMPANY|PORT|TERMINAL
    entity_id TEXT NOT NULL,
    data_category TEXT NOT NULL,                  -- CREW|PASSENGER|CARGO|TECHNICAL|OT_ICS|NAV|AIS_ECDIS
    storage_location TEXT, cross_border BOOL,
    protection_controls JSONB
);

CREATE TABLE cyber_control (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    framework TEXT NOT NULL,                      -- MSC.428|MSC-FAL.1/Circ.3|IMO Res.A.1068|national
    control_ref TEXT NOT NULL,
    title TEXT NOT NULL, description TEXT,
    UNIQUE(framework, control_ref)
);

CREATE TABLE cyber_assessment (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL,
    entity_type TEXT NOT NULL, entity_id TEXT NOT NULL,
    control_id UUID REFERENCES cyber_control(id),
    status TEXT NOT NULL CHECK (status IN ('GREEN','YELLOW','RED','BLACK')),
    assessed_at TIMESTAMPTZ, assessed_by UUID,
    evidence_id UUID REFERENCES evidence(id)
);

CREATE TABLE incident (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL,
    vessel_id UUID REFERENCES vessel(id),
    voyage_id UUID REFERENCES voyage(id),
    incident_type TEXT NOT NULL CHECK (incident_type IN
        ('COLLISION','GROUNDING','FIRE','EXPLOSION','POLLUTION','MACHINERY',
         'INJURY','DEATH','CARGO','SECURITY','CYBER')),
    occurred_at TIMESTAMPTZ NOT NULL,
    location JSONB,
    severity TEXT CHECK (severity IN ('LOW','MEDIUM','HIGH','VERY_HIGH')),
    description TEXT,
    status TEXT NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN','NOTIFIED','INVESTIGATING','CLOSED'))
);
CREATE INDEX idx_incident_company ON incident (company_id, occurred_at);

CREATE TABLE incident_notification (              -- regulatory reporting deadlines (Obj S)
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id UUID NOT NULL REFERENCES incident(id),
    authority_id TEXT REFERENCES authority(id),
    requirement_provision_id TEXT REFERENCES legal_provision(id),
    deadline TIMESTAMPTZ,
    sent_at TIMESTAMPTZ,
    status TEXT NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING','SENT','ACKNOWLEDGED','OVERDUE'))
);
CREATE INDEX idx_notification_due ON incident_notification (deadline) WHERE status = 'PENDING';

CREATE TABLE corrective_action (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL,
    incident_id UUID REFERENCES incident(id),
    action TEXT NOT NULL,
    owner UUID, due_date DATE,
    status TEXT NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN','IN_PROGRESS','DONE','VERIFIED')),
    verified_by UUID
);

CREATE TABLE ship_project (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL,
    hull_no TEXT, project_name TEXT,
    ship_type TEXT, intended_flag TEXT REFERENCES jurisdiction(id),
    keel_laid_date DATE, delivery_date DATE,
    phase TEXT CHECK (phase IN ('DESIGN','CONSTRUCTION','SEA_TRIALS','DELIVERY'))
);

CREATE TABLE design_approval (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES ship_project(id),
    plan_type TEXT NOT NULL,
    provision_id TEXT REFERENCES legal_provision(id),
    status TEXT NOT NULL CHECK (status IN ('SUBMITTED','APPROVED','CONDITIONAL','REJECTED')),
    approved_by TEXT, approved_at TIMESTAMPTZ
);

CREATE TABLE construction_survey (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES ship_project(id),
    survey_type TEXT NOT NULL,
    survey_date DATE,
    surveyor TEXT,
    result TEXT CHECK (result IN ('SATISFACTORY','DEFICIENCY','HOLD')),
    report_evidence_id UUID REFERENCES evidence(id)
);

CREATE TABLE yard_facility (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL,
    name TEXT NOT NULL, dock_capacity_gt NUMERIC,
    licences JSONB
);

CREATE TABLE work_permit (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL,
    facility_id UUID REFERENCES yard_facility(id),
    vessel_id UUID REFERENCES vessel(id),
    permit_type TEXT NOT NULL,                    -- HOT_WORK|CONFINED_SPACE|ALOFT|ENCLOSED...
    issued_at TIMESTAMPTZ, expiry_at TIMESTAMPTZ,
    safety_officer UUID,
    status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE','SUSPENDED','CLOSED','EXPIRED'))
);
CREATE INDEX idx_permit_expiry ON work_permit (expiry_at) WHERE status = 'ACTIVE';

CREATE TABLE insurance_policy (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL,
    entity_type TEXT NOT NULL CHECK (entity_type IN ('VESSEL','COMPANY')),
    entity_id TEXT NOT NULL,
    policy_type TEXT NOT NULL CHECK (policy_type IN ('H&M','P&I','CLC','BUNKER','WRECK','LOH','K&R')),
    insurer TEXT, policy_no TEXT,
    issue_date DATE, expiry_date DATE,
    limit_amount NUMERIC, limit_currency TEXT,
    evidence_id UUID REFERENCES evidence(id)
);
CREATE INDEX idx_insurance_expiry ON insurance_policy (entity_id, expiry_date);

CREATE TABLE liability_exposure (                 -- risk-flag ADVISORY layer, never legal advice
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL,
    vessel_id UUID REFERENCES vessel(id),
    exposure_type TEXT NOT NULL,
    source_provision_id TEXT REFERENCES legal_provision(id),
    risk_flag TEXT NOT NULL CHECK (risk_flag IN ('INFO','WATCH','ELEVATED')),
    rationale TEXT,
    assessed_at TIMESTAMPTZ DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- 8.7 SHIP RECYCLING / ENVIRONMENTAL (Obj U)
-- ---------------------------------------------------------------------------

CREATE TABLE recycling_facility (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL,
    name TEXT, location TEXT,
    licence_no TEXT, licence_expiry DATE,
    hong_kong_convention_ready BOOL DEFAULT false
);

CREATE TABLE ihm_record (                         -- Inventory of Hazardous Materials
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vessel_id UUID NOT NULL REFERENCES vessel(id),
    ihm_part TEXT NOT NULL CHECK (ihm_part IN ('I','II','III')),
    hazmat_type TEXT, location TEXT, quantity NUMERIC,
    document_evidence_id UUID REFERENCES evidence(id)
);

-- ---------------------------------------------------------------------------
-- 8.8 ROW-LEVEL SECURITY (audit fix #8 / Principle 13 — tenant isolation absolute)
-- App sets the GUC per transaction:  SET LOCAL app.tenant = '<uuid>';
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION current_tenant() RETURNS UUID AS $$
    SELECT NULLIF(current_setting('app.tenant', true), '')::uuid
$$ LANGUAGE SQL STABLE;

DO $$
DECLARE
    t TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY[
        'rule_evaluation_log','voyage','seafarer','crew_contract','evidence',
        'compliance_result','audit_log','data_inventory','cyber_assessment',
        'incident','corrective_action','ship_project','yard_facility','work_permit',
        'insurance_policy','liability_exposure','recycling_facility'
    ] LOOP
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', t);
        EXECUTE format(
            'CREATE POLICY tenant_isolation ON %I USING (company_id = current_tenant())',
            t);
    END LOOP;
END $$;

COMMIT;
