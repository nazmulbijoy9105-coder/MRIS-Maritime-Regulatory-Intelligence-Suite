"""State-participation resolver (Part 6.5) — 'in force FOR THE FLAG on date D'.

Backs the DSL resolvers `in_force(provision, at)` and
`annex_ratified(flag, annex, at)`. Fail-closed semantics:

    True    — the state is bound at the date (acceptance + EIF known)
    False   — explicitly not bound / future amendment not yet effective
    None    — unknown (no data) => the DSL folds to UNKNOWN => BLACK upstream

Never applies future amendments early (Principle 6): an amendment with
entry_into_force in the future resolves False at any earlier date.
Per-state rows carry verification_status; EXTRACTED_BY_AI rows are demo-grade
until closed against the IMO Status Books / ILO (open-items register).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Optional

SEED_PATH = Path(__file__).resolve().parent.parent / "corpus" / "seed" / "state_participation.json"


class _Missing:
    pass


def _d(value) -> Optional[date]:
    if value in (None, _Missing):
        return None
    return value if isinstance(value, date) else date.fromisoformat(str(value))


@dataclass
class TreatyRow:
    instrument_id: str
    jurisdiction_id: str
    acceptance_date: Optional[date] = None
    entry_into_force_for_state: Optional[date] = None
    date_precision: str = "DAY"
    annexes: dict = field(default_factory=dict)      # {"I": {"accepted": date, "eif": date}}
    verification_status: str = "EXTRACTED_BY_AI"
    source_url: Optional[str] = None


@dataclass
class FutureAmendment:
    amendment_id: str
    instrument_id: str
    entry_into_force: date
    status: str = "FUTURE_EFFECTIVE"


class StateParticipationDB:
    def __init__(self, rows: list[TreatyRow], future: list[FutureAmendment] | None = None):
        self.rows = {(r.instrument_id, r.jurisdiction_id): r for r in rows}
        self.future = future or []

    # -- DSL resolver backends -------------------------------------------------
    def in_force(self, instrument_id: str, jurisdiction_id: str, at: date) -> Optional[bool]:
        row = self.rows.get((instrument_id, jurisdiction_id))
        if row is None:
            return None                              # unknown => fail closed
        eif = row.entry_into_force_for_state
        if eif is None:
            return None
        return at >= eif

    def annex_ratified(self, jurisdiction_id: str, annex: str, at: date) -> Optional[bool]:
        row = self.rows.get(("IMO-CONV-MARPOL-73-78", jurisdiction_id))
        if row is None:
            return None
        entry = row.annexes.get(annex.upper())
        if entry is None:
            return None
        eif = _d(entry.get("eif"))
        return None if eif is None else at >= eif

    def ratified_annexes(self, jurisdiction_id: str, at: date) -> list[str]:
        return sorted(a for a in ("I", "II", "III", "IV", "V", "VI")
                      if self.annex_ratified(jurisdiction_id, a, at) is True)

    # -- amendment intelligence ------------------------------------------------
    def amendment_in_force(self, amendment_id: str, at: date) -> Optional[bool]:
        for amend in self.future:
            if amend.amendment_id == amendment_id:
                return at >= amend.entry_into_force
        return None

    def treaty_status(self, jurisdiction_id: str, at: date) -> list[dict]:
        out = []
        for (instrument_id, juris), row in self.rows.items():
            if juris != jurisdiction_id:
                continue
            out.append({
                "instrument_id": instrument_id,
                "jurisdiction_id": juris,
                "in_force": self.in_force(instrument_id, juris, at),
                "acceptance_date": row.acceptance_date.isoformat() if row.acceptance_date else None,
                "entry_into_force_for_state":
                    row.entry_into_force_for_state.isoformat() if row.entry_into_force_for_state else None,
                "date_precision": row.date_precision,
                "verification_status": row.verification_status,
                "source_url": row.source_url,
                "annexes": {a: {"eif": v.get("eif"), "ratified_at": self.annex_ratified(juris, a, at)}
                            for a, v in row.annexes.items()} if row.annexes else None,
            })
        for amend in self.future:
            out.append({
                "instrument_id": amend.instrument_id,
                "amendment_id": amend.amendment_id,
                "in_force": self.amendment_in_force(amend.amendment_id, at),
                "entry_into_force": amend.entry_into_force.isoformat(),
                "status": amend.status if self.amendment_in_force(amend.amendment_id, at) is False
                          else "IN_FORCE",
                "note": "future amendment stored but inactive until effective (Principle 6)",
            })
        return sorted(out, key=lambda r: r["instrument_id"])


def load_state_participation(path: Path | None = None) -> StateParticipationDB:
    data = json.loads((path or SEED_PATH).read_text(encoding="utf-8"))
    rows = []
    for r in data.get("states", []):
        annexes = {a: {"accepted": v.get("accepted"), "eif": v.get("eif")}
                   for a, v in (r.get("annexes") or {}).items()}
        rows.append(TreatyRow(
            instrument_id=r["instrument_id"],
            jurisdiction_id=r["jurisdiction_id"],
            acceptance_date=_d(r.get("acceptance_date")),
            entry_into_force_for_state=_d(r.get("entry_into_force_for_state")),
            date_precision=r.get("date_precision", "DAY"),
            annexes=annexes,
            verification_status=r.get("verification_status", "EXTRACTED_BY_AI"),
            source_url=r.get("source_url"),
        ))
    future = [FutureAmendment(
        amendment_id=f["amendment_id"], instrument_id=f["instrument_id"],
        entry_into_force=_d(f["entry_into_force"]), status=f.get("status", "FUTURE_EFFECTIVE"))
        for f in data.get("future_amendments", [])]
    return StateParticipationDB(rows, future)
