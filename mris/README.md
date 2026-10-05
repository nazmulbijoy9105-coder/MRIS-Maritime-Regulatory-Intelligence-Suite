# MRIS — Maritime Regulatory Intelligence Suite

[![tests](https://img.shields.io/badge/tests-63%20passed-brightgreen)](#quick-start)
[![python](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)
[![stack](https://img.shields.io/badge/stack-FastAPI%20·%20ILRMF%E2%80%91DSL%20·%20PostgreSQL%2016-informational)](#architecture)
[![deploy](https://img.shields.io/badge/vercel-ready-black)](#deploy)

Implementation of **Blueprint v2.0 (Post-Audit Baseline)** — full stack:
deterministic legal-rule engine + premium dark UI + Vercel-ready packaging.

> **Regulatory intelligence, not legal advice.** Unverified content never feeds
> live compliance calculations: every rule is gated on
> `EXTRACTED_BY_AI → REVIEWED → VERIFIED_AGAINST_GAZETTE` (fail-closed).

```
LEGAL CORPUS → VERSION CONTROL → AMENDMENT INTELLIGENCE → JURISDICTION
→ APPLICABILITY → DETERMINISTIC RULES → EVIDENCE → COMPLIANCE → ALERT → AUDIT → LAWYER
```

## What is built

| Blueprint part | Implementation | Status |
|---|---|---|
| Part 4 repo structure | `mris/` package + `scripts/build_corpus_tree.py` corpus materialiser | ✅ |
| Part 5 BD corpus | `mris/corpus/seed/manifest.json` — 21 BD instruments + open-items register | ✅ |
| Part 6 international corpus | manifest: SOLAS/MARPOL/STCW/MLC/UNCLOS… 20 instruments + **state-participation DB** (Part 6.5: "in force FOR THE FLAG on date D", future amendments never applied early) | ✅ |
| Part 9.2 rule specs | 7 executable rules: MSO 1983 S066/S082/S335/S350 + MARPOL Annex I (oil records) / Annex V (garbage) / Annex VI (IAPP) | ✅ |
| Part 8 data model | `infra/db/migrations/001_initial_schema.sql` (PostgreSQL 16, RLS, GIN/BRIN, hash-chained audit) + `mris/models.py` ORM | ✅ |
| Part 9.3 ILRMF-DSL | `mris/ilrmf/` — EBNF parser, type checker, sandboxed **three-valued** evaluator, 20 builtins | ✅ |
| Part 11 change pipeline | `mris/engine/ingestion.py` — source registry, sha256 delta, classification, provision-boundary detection | ✅ |
| Part 9.5 precedence | `mris/engine/precedence.py` — L1–L6 layers, `STRICTER`/`CONFLICT`/`ADVISORY`, Principle-15 invariant | ✅ |
| Part 9.6 LCA-1 | `mris/engine/lca1.py` — voyage legs × jurisdiction segments, PSC asymmetry, per-leg drill-down | ✅ |
| Part 9.2 rule specs | `mris/corpus/rules/*.yaml` — S082 manning, S335 load line, S350 unseaworthy | ✅ |
| Part 10 evidence engine | expiry semantics in DSL builtins (`expired`, `expires_within`, `cert_valid`) | ✅ (sweep worker = ops task) |
| Objs S/T/R/J/K (P4/P5) | incident → regulatory notification deadlines + corrective actions; liability **advisory** flags (Principle 15); cyber MSC.428 posture; shipyard readiness ladder + permit hard gates | ✅ |
| Part 12.2 API | `mris/api/app.py` — fleet, compliance, provenance, rule eval, LCA-1 preview, rules, versions, change impacts | ✅ |
| Frontend | `frontend/` — premium dark SPA: fleet dashboard, result-contract drill-down, provenance drawer, DSL console, voyage preview, corpus browser | ✅ |
| Deploy | `vercel.json` + `api/index.py` (FastAPI serverless) + static frontend with baked engine fallback (`demo_data.json`) | ✅ |
| Part 14 P1 exit demo | `python -m mris.demo` — one BD-flagged cargo ship fully assessed | ✅ |
| Parts 11/13/18/19 | docker-compose (Postgres 16 + MinIO), RLS + hash-chain in DDL, index strategy | 🟡 deployment-ready |
| Legal review (P2) | two-person verification workflow + **hash-chained tamper-evident audit** + Legal Review Console UI | ✅ |

## Quick start

```bash
pip install -e ".[dev]"
pytest -q              # 43 tests: Kleene logic, quantifiers, LCA-1, fail-closed
python -m mris.demo    # full vessel assessment (P1 exit criteria)
uvicorn mris.api:app   # UI on :8000 → open http://localhost:8000
python scripts/build_corpus_tree.py   # materialise Part 4/5 corpus folders
python scripts/build_demo_data.py     # bake engine output for static hosting
docker compose up      # Postgres 16 (schema auto-applied) + API + MinIO
```

### Deploy

**Vercel (one click):** import the repo — `vercel.json` builds the static UI
(`frontend/`) and routes `/v1/*` + `/health` to the FastAPI serverless function
(`api/index.py`). The UI falls back to `demo_data.json` (real engine output,
baked at build time) when the API is unreachable, so the site renders
beautifully even as a pure static deployment.

**GitHub:** the repo renders as-is — README badges above, folder table below.
Push and import; no build step required for the frontend (vanilla JS, zero deps,
offline-capable).

### The UI

| View | What it shows |
|---|---|
| Overview | fleet KPIs, compliance-health donut, verification gates |
| Fleet Compliance | vessel cards with live status bars — click for drill-down |
| Vessel Assessment | status ring + **full Part-Z result contract** per obligation + provenance drawer (result → rule → provision → legal version → instrument → source) |
| Rule Engine | executable rule specs with DSL syntax highlighting + live evaluation console |
| Voyage Preview | LCA-1 form (flag / domestic / legs) + precedence hierarchy + conflict cards |
| Legal Corpus | BD + international instruments with verification gates + **treaty status per flag** (state participation) |
| Change Monitor | open-items register + 7-stage change pipeline |
| Legal Review | verification queue (two-person gate), hash-chained audit timeline, ingestion demo |
| Operations & Risk | incidents + notification countdowns, liability advisory flags, MSC.428 cyber posture, shipyard readiness + permit alerts |

## The demo assessment

`python -m mris.demo` runs three production-shaped rules against
**MV PADMA STAR** (IMO 9521457, flag BD, cargo, GT 24 500):

- **S082 manning → RED** — Master's CoC expired 10 days ago (status ladder:
  `RED: EXISTS c IN current_crew : NOT c.coc_valid(at: eval_date)`)
- **S335 load line → YELLOW** — certificate expires in 45 days (expiry engine)
- **S350 unseaworthy → RED** — safety equipment certificate expired
- Overall **RED**, with the full result contract (Part Z) per item: requirement,
  why applicable, provision, legal version, evidence, facts, action, deadline,
  consequence, lawyer-review flag.

## ILRMF-DSL in 30 seconds

```yaml
condition:
  type: MANDATORY            # UNKNOWN => BLACK (fail-closed)
  expression: |
    (EXISTS e IN evidence : e.evidence_type = "SAFE_MANNING_DOCUMENT")
    AND (FORALL crew_member IN current_crew :
           crew_member.coc_valid(at: eval_date)
           AND crew_member.rank IN required_ranks)
```

- **Three-valued Kleene logic** — `TRUE / FALSE / UNKNOWN`; `NOT UNKNOWN = UNKNOWN`;
  missing facts never silently become `FALSE` (or `TRUE`).
- **Total & sandboxed** — division by zero, depth cap, step budget all fold to
  `UNKNOWN`, never an exception escaping into a compliance result.
- **Typed** — `BOOL NUMBER STRING DATE DURATION RANK CERT_TYPE EVIDENCE SET<T>`;
  ill-typed rules are rejected and can never reach `ACTIVE`.
- **JSONB-serialisable** — AST round-trips into `rule_version.definition`.
- **Quantifiers** — `EXISTS / FORALL / ANY / NONE` over indexed entity sets.
  Fail-closed asymmetry (documented): `FORALL` over an empty/unpopulated set is
  `UNKNOWN` (cannot verify a universal), while `EXISTS` over empty is a definite
  `FALSE` ("not on file").

## Determinism guarantees (Part 2 principles)

1. **Result = f(law_version, rule_version, facts)** — every result snapshots both.
2. **Fail closed** — conflict / missing data / unverified source ⇒ BLACK, never a guess.
3. **Advisory can never weaken statutory** (Principle 15) — L6 (SIRE/OCIMF/charter)
   items stay YELLOW advisory; a binding GREEN stays GREEN.
4. **STRICTER / CONFLICT** — compatible obligations merge to the tighter bound
   (`MIN(5) ∧ MIN(8) ⇒ MIN(8)`); incompatible hard obligations ⇒ BLACK item
   citing both provisions + layers, routed to legal review (48 h SLA).
5. **Historical reproducibility** — `as_of` selects `legal_version` /
   `provision_validity` intervals; future law is stored but never applied early.
6. **Human gate** — AI extracts and diffs; only an authorised reviewer approves
   a production rule (`rule_version.approved_by`, author ≠ approver).

## Repository layout

```
mris/
├── mris/
│   ├── ilrmf/          # ILRMF-DSL: tri, lexer, ast, parser, types, context,
│   │                   #             evaluator, rule_spec   (Part 9.3)
│   ├── engine/         # status, precedence, rules, lca1, compliance (Parts 9.5-9.7)
│   ├── corpus/         # seed manifest (Parts 5/6) + executable rule YAMLs (Part 9.2)
│   ├── api/            # FastAPI surface (Part 12.2)
│   ├── demo/           # P1 exit-criteria assessment + demo fleet
│   └── models.py       # SQLAlchemy mirror of Part 8
├── frontend/           # premium UI: index.html + styles.css + app.js + demo_data.json
├── api/                # Vercel serverless entry (index.py + requirements.txt)
├── infra/db/migrations/001_initial_schema.sql   # PostgreSQL 16 DDL + RLS
├── scripts/            # build_corpus_tree.py · build_demo_data.py
├── tests/              # 63 tests — DSL, engine, LCA-1, result contract, review workflow,
│                       #             state participation, incidents/liability/cyber/yard
├── vercel.json · Dockerfile · docker-compose.yml
└── pyproject.toml
```

## Roadmap (Part 14)

- **P0 foundation** ✅ schema, corpus manifest, DSL, engine core
- **P1 BD MVP** ✅ rules MANNING / LOADLINE / UNSEAWORTHY / LICENCE live; demo fleet spans all four statuses (GREEN / YELLOW / RED / BLACK)
- **P2 temporal + change monitor** ✅ ingestion pipeline, verification workflow (two-person gate), hash-chained audit, legal review console
- **P3 international layer** ✅ state-participation DB ("in force FOR THE FLAG"), MARPOL Annex I/V/VI rules, gt_min/annex applicability, treaty-status API + UI
- **P4 commercial depth** ✅ incident → notification workflow (deterministic deadlines, overdue escalation), liability risk flags (advisory), cyber MSC.428 baseline
- **P5 full depth** 🟡 shipyard readiness + permit gates ✅; ports/recycling/shipbuilding corpus depth is content work on the existing framework

## Standing rules

- Every `⚠ VERIFY` item in the manifest open-items register must be closed
  against the official Gazette / bdlaws / IMO Status Book / ILO before its rules
  enter production. The register is never deleted, only appended and closed with
  `verified_at` + source URL.
- Repealed law is never deleted; drafts are quarantined; future law is stored
  inactive. Historical results reproduce exactly from version snapshots.
