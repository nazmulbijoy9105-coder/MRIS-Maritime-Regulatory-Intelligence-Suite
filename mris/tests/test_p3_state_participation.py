"""P3 tests: state participation resolver — 'in force FOR THE FLAG on date D'."""
from __future__ import annotations

from datetime import date

from mris.engine.state_participation import load_state_participation

TODAY = date(2026, 10, 6)


def test_in_force_for_flag_on_date():
    db = load_state_participation()
    # BD bound by MARPOL at today; not bound before accession year
    assert db.in_force("IMO-CONV-MARPOL-73-78", "BD", TODAY) is True
    assert db.in_force("IMO-CONV-MARPOL-73-78", "BD", date(1990, 1, 1)) is False
    # unknown state/instrument => None => fail-closed UNKNOWN upstream
    assert db.in_force("IMO-CONV-SOLAS-1974", "XX", TODAY) is None
    assert db.in_force("IMO-CONV-HNS-1996", "BD", TODAY) is None


def test_marpol_annex_ratification():
    db = load_state_participation()
    assert db.annex_ratified("BD", "I", TODAY) is True
    assert db.annex_ratified("BD", "VI", TODAY) is True
    assert db.annex_ratified("BD", "I", date(1990, 1, 1)) is False
    assert db.annex_ratified("BD", "IX", TODAY) is None          # annex without data
    assert db.ratified_annexes("BD", TODAY) == ["I", "II", "III", "IV", "V", "VI"]
    assert db.annex_ratified("XX", "I", TODAY) is None           # unknown flag


def test_future_amendment_never_applied_early():
    """Principle 6: MLC 2025 amendment (EIF 2027-12-23) is inactive before its date."""
    db = load_state_participation()
    assert db.amendment_in_force("ILO-CONV-MLC-2006-AMEND-2025", TODAY) is False
    assert db.amendment_in_force("ILO-CONV-MLC-2006-AMEND-2025", date(2027, 12, 22)) is False
    assert db.amendment_in_force("ILO-CONV-MLC-2006-AMEND-2025", date(2027, 12, 23)) is True


def test_treaty_status_report_carries_verification():
    db = load_state_participation()
    rows = db.treaty_status("BD", TODAY)
    assert any(r["instrument_id"] == "ILO-CONV-MLC-2006" for r in rows)
    for r in rows:
        if "amendment_id" not in r:
            assert r["verification_status"] == "EXTRACTED_BY_AI"   # gated, not production-grade
            assert r["in_force"] in (True, False, None)
    amend = next(r for r in rows if r.get("amendment_id") == "ILO-CONV-MLC-2006-AMEND-2025")
    assert amend["in_force"] is False and amend["status"] == "FUTURE_EFFECTIVE"


def test_marpol_rules_respect_treaty_position():
    """MARPOL rules apply only when the flag is bound by the annex (L1 gate)."""
    from mris.engine import match_applicability

    facts = {"gross_tonnage": 24500.0, "operation": "SEA_VOYAGE",
             "annex_ratified_for_flag": ["I", "II", "III", "IV", "V", "VI"]}
    app = {"all": [{"annex_ratified_for_flag": ["VI"]}, {"gt_min": 400}]}
    assert match_applicability(app, facts).is_true

    # flag not bound by Annex VI => rule does not apply
    facts2 = {**facts, "annex_ratified_for_flag": ["I", "V"]}
    assert match_applicability(app, facts2).value == "FALSE"

    # treaty position unknown => applicability unknown => BLACK upstream
    facts3 = {"gross_tonnage": 24500.0, "operation": "SEA_VOYAGE"}
    assert match_applicability(app, facts3).value == "UNKNOWN"

    # below GT threshold => not applicable
    facts4 = {**facts, "gross_tonnage": 320.0}
    assert match_applicability(app, facts4).value == "FALSE"

    # missing tonnage => fail closed
    facts5 = {"operation": "SEA_VOYAGE", "annex_ratified_for_flag": ["VI"]}
    assert match_applicability(app, facts5).value == "UNKNOWN"
