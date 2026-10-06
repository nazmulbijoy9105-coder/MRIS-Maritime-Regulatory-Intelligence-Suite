import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

CORPUS_DIR = (
    Path(__file__).resolve().parents[2]
    / "mris"
    / "corpus"
)

SNAPSHOT_DIR = CORPUS_DIR / "snapshots"

CORPUS_EXTENSIONS = {
    ".json",
    ".yaml",
    ".yml",
    ".xml",
    ".txt",
    ".csv",
    ".md",
}


def corpus_files():
    return sorted(
        f
        for f in CORPUS_DIR.rglob("*")
        if (
            f.is_file()
            and SNAPSHOT_DIR not in f.parents
            and f.suffix.lower() in CORPUS_EXTENSIONS
        )
    )


def load_previous_snapshot():
    """
    Return the latest compatible canonical snapshot hash.

    Legacy snapshots without snapshot_hash are intentionally ignored
    as cryptographic parents. They remain historical evidence.
    """
    snapshots = sorted(
        SNAPSHOT_DIR.glob("snapshot_*.json")
    )

    for previous in reversed(snapshots):
        try:
            data = json.loads(
                previous.read_text(encoding="utf-8")
            )
        except json.JSONDecodeError:
            continue

        snapshot_hash = data.get("snapshot_hash")

        if snapshot_hash:
            return snapshot_hash

    return "GENESIS"


def create_snapshot():
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

    print("==========================================================")
    print("MRIS CORPUS SNAPSHOT ENGINE")
    print("==========================================================")

    files = corpus_files()

    corpus_state = {}

    for file_path in files:
        rel_path = file_path.relative_to(
            CORPUS_DIR
        ).as_posix()

        content = file_path.read_bytes()

        corpus_state[rel_path] = {
            "sha256": hashlib.sha256(content).hexdigest(),
            "bytes": len(content),
        }

    canonical_state = json.dumps(
        corpus_state,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    corpus_hash = hashlib.sha256(
        canonical_state
    ).hexdigest()

    prev_hash = load_previous_snapshot()

    timestamp = datetime.now(
        timezone.utc
    ).strftime("%Y%m%dT%H%M%SZ")

    snapshot_id = f"snap_{timestamp}"

    snapshot_core = {
        "schema_version": "1.0",
        "snapshot_id": snapshot_id,
        "timestamp": timestamp,
        "corpus_hash": corpus_hash,
        "prev_snapshot_hash": prev_hash,
        "file_count": len(corpus_state),
        "files": corpus_state,
    }

    canonical_snapshot = json.dumps(
        snapshot_core,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    snapshot_hash = hashlib.sha256(
        canonical_snapshot
    ).hexdigest()

    snapshot_data = {
        **snapshot_core,
        "snapshot_hash": snapshot_hash,
    }

    snap_file = (
        SNAPSHOT_DIR
        / f"snapshot_{timestamp}.json"
    )

    # Avoid accidental overwrite if two snapshots happen
    # to be generated in the same second.
    if snap_file.exists():
        raise FileExistsError(
            f"Snapshot already exists: {snap_file}"
        )

    with snap_file.open(
        "x",
        encoding="utf-8"
    ) as fh:
        json.dump(
            snapshot_data,
            fh,
            indent=4,
            sort_keys=True,
        )
        fh.write("\n")

    print(f"Snapshot ID:       {snapshot_id}")
    print(f"Corpus Hash:       {corpus_hash}")
    print(f"Previous Hash:     {prev_hash}")
    print(f"Snapshot Hash:     {snapshot_hash}")
    print(f"Files Snapshotted: {len(corpus_state)}")
    print(f"Saved to:          {snap_file}")
    print("==========================================================")
    print("RESULT: PASS")
    print("Canonical corpus snapshot created.")
    print("Hash chain is ready for subsequent snapshots.")


if __name__ == "__main__":
    create_snapshot()
