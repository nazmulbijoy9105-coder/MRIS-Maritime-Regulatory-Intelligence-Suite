import json
from pathlib import Path
from fastapi.testclient import TestClient
from mris.api import app
from mris.corpus.open_items import open_items

client = TestClient(app)


def test_all_parameterless_get_routes_return_200():
    for r in app.routes:
        if "GET" in getattr(r, "methods", ()) and "{" not in r.path \
                and not r.path.startswith(("/docs", "/redoc", "/openapi")):
            assert client.get(r.path).status_code == 200, r.path


def test_open_items_count():
    m = json.load(open(Path("mris/corpus/seed/manifest.json"), encoding="utf-8"))
    assert len(open_items(m["instruments"])) == 37
    assert len(client.get("/v1/changes/impacts").json()["open_verification_items"]) == 37
