import hashlib
import json
import sys
from pathlib import Path

CORPUS_DIR = (
    Path(__file__).resolve().parents[2]
    / "mris"
    / "corpus"
)

SNAPSHOT_DIR = CORPUS_DIR / "snapshots"


def fail(message):
    print(f"RESULT: FAIL - {message}")
    sys.exit(1)


def canonical_json(value):
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def verify_snapshot(snapshot_path):
    try:
        snapshot = json.loads(
            snapshot_path.read_text(
                encoding="utf-8"
            )
        )
    except json.JSONDecodeError as exc:
        fail(f"Invalid snapshot JSON: {exc}")

    required = {
        "schema_version",
        "snapshot_id",
        "timestamp",
        "corpus_hash",
        "prev_snapshot_hash",
        "snapshot_hash",
        "file_count",
        "files",
    }

    missing = sorted(
        required - set(snapshot)
    )

    if missing:
        fail(
            "Snapshot schema missing required fields: "
            + ", ".join(missing)
        )

    if snapshot["schema_version"] != "1.0":
        fail(
            f"Unsupported snapshot schema: "
            f"{snapshot['schema_version']!r}"
        )

    files = snapshot["files"]

    if not isinstance(files, dict):
        fail(
            "Snapshot 'files' must be an object."
        )

    if snapshot["file_count"] != len(files):
        fail(
            f"file_count mismatch: declared "
            f"{snapshot['file_count']}, "
            f"actual {len(files)}"
        )

    reconstructed = {}

    for rel_path, metadata in files.items():

        if not isinstance(metadata, dict):
            fail(
                f"Incompatible metadata for "
                f"{rel_path!r}"
            )

        if "sha256" not in metadata:
            fail(
                f"Missing sha256 metadata: "
                f"{rel_path}"
            )

        if "bytes" not in metadata:
            fail(
                f"Missing byte-count metadata: "
                f"{rel_path}"
            )

        path = CORPUS_DIR / rel_path

        try:
            path.resolve().relative_to(
                CORPUS_DIR.resolve()
            )
        except ValueError:
            fail(
                f"Path escapes corpus directory: "
                f"{rel_path}"
            )

        if not path.is_file():
            fail(
                f"MISSING FILE: {rel_path}"
            )

        actual = path.read_bytes()

        actual_hash = hashlib.sha256(
            actual
        ).hexdigest()

        if actual_hash != metadata["sha256"]:
            fail(
                f"HASH MISMATCH: {rel_path}"
            )

        if len(actual) != metadata["bytes"]:
            fail(
                f"BYTE COUNT MISMATCH: {rel_path}"
            )

        reconstructed[rel_path] = {
            "sha256": actual_hash,
            "bytes": len(actual),
        }

    calculated_corpus_hash = hashlib.sha256(
        canonical_json(reconstructed)
    ).hexdigest()

    if calculated_corpus_hash != snapshot["corpus_hash"]:
        fail(
            "CORPUS HASH MISMATCH"
        )

    # Reconstruct exactly the object that was hashed
    # to produce snapshot_hash.
    snapshot_core = {
        "schema_version": snapshot[
            "schema_version"
        ],
        "snapshot_id": snapshot[
            "snapshot_id"
        ],
        "timestamp": snapshot[
            "timestamp"
        ],
        "corpus_hash": snapshot[
            "corpus_hash"
        ],
        "prev_snapshot_hash": snapshot[
            "prev_snapshot_hash"
        ],
        "file_count": snapshot[
            "file_count"
        ],
        "files": snapshot[
            "files"
        ],
    }

    calculated_snapshot_hash = hashlib.sha256(
        canonical_json(snapshot_core)
    ).hexdigest()

    if calculated_snapshot_hash != snapshot[
        "snapshot_hash"
    ]:
        fail(
            "SNAPSHOT HASH MISMATCH"
        )

    print(
        "=========================================================="
    )
    print(
        "MRIS CORPUS SNAPSHOT VERIFICATION"
    )
    print(
        "=========================================================="
    )
    print(
        f"Snapshot:       {snapshot_path.name}"
    )
    print(
        f"Snapshot ID:    {snapshot['snapshot_id']}"
    )
    print(
        f"Schema:         {snapshot['schema_version']}"
    )
    print(
        f"Files checked:  {len(files)}"
    )
    print(
        f"Corpus hash:    {snapshot['corpus_hash']}"
    )
    print(
        f"Snapshot hash:  {snapshot['snapshot_hash']}"
    )
    print(
        f"Previous hash:  {snapshot['prev_snapshot_hash']}"
    )
    print()
    print(
        "RESULT: PASS"
    )
    print(
        "Corpus and snapshot cryptographic integrity verified."
    )


if __name__ == "__main__":
    snapshots = sorted(
        SNAPSHOT_DIR.glob(
            "snapshot_*.json"
        )
    )

    if not snapshots:
        fail("No snapshots found.")

    verify_snapshot(
        snapshots[-1]
    )
