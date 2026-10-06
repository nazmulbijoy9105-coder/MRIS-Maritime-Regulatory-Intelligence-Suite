import json
import subprocess
import sys
from pathlib import Path

from mris.corpus import load_manifest


ROOT = Path(__file__).resolve().parents[1]


def test_manifest_uses_canonical_registry_shape():
    manifest = load_manifest()

    assert set(manifest) == {"_metadata", "instruments"}
    assert isinstance(manifest["instruments"], list)
    assert len(manifest["instruments"]) == 44

    ids = [item["instrument_id"] for item in manifest["instruments"]]
    assert len(ids) == len(set(ids))

    jurisdictions = {
        item["jurisdiction"] for item in manifest["instruments"]
    }
    assert jurisdictions == {"BD", "INTL"}


def test_demo_manifest_info_uses_canonical_registry():
    from mris.demo.runner import demo_manifest_info

    text = demo_manifest_info()

    assert "21 BD instruments" in text
    assert "23 international instruments" in text
    assert "open verification items" in text


def test_build_demo_data_has_no_legacy_manifest_keys():
    source = (
        ROOT / "scripts" / "build_demo_data.py"
    ).read_text(encoding="utf-8")

    assert 'manifest["international_instruments"]' not in source
    assert 'manifest["open_items_register"]' not in source


def test_build_corpus_tree_has_no_legacy_manifest_keys():
    source = (
        ROOT / "scripts" / "build_corpus_tree.py"
    ).read_text(encoding="utf-8")

    assert 'manifest["international_instruments"]' not in source
    assert 'manifest["open_items_register"]' not in source
    assert 'i["id"]' not in source


def test_build_demo_data_executes():
    result = subprocess.run(
        [sys.executable, "scripts/build_demo_data.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, (
        f"build_demo_data failed\n"
        f"STDOUT:\n{result.stdout}\n"
        f"STDERR:\n{result.stderr}"
    )

    output = ROOT / "frontend" / "demo_data.json"
    assert output.is_file()

    data = json.loads(
        output.read_text(encoding="utf-8")
    )

    assert len(data["instruments"]["bangladesh"]) == 21
    assert len(data["instruments"]["international"]) == 23

    expected_open = sum(
        1
        for item in load_manifest()["instruments"]
        if item.get("verification_status") != "VERIFIED"
    )

    assert len(data["impacts"]["open_verification_items"]) == expected_open
