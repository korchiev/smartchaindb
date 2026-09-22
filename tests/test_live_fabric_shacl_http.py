"""Live HTTP tests against Fabric SHACL on :3001."""
from __future__ import annotations

import os

import pytest
import requests

ENDPOINT = os.environ.get("FABRIC_SHACL_ENDPOINT", "http://localhost:3001")


def _ttl(op: str, extra: str = "") -> str:
    return (
        "@prefix fabric: <http://smartchaindb.org/fabric#> .\n\n"
        f"<urn:tx:{op.lower()}> a fabric:{op} ;\n"
        f'    fabric:operation "{op}" ;\n'
        f"{extra}"
        " .\n"
    )


@pytest.fixture(scope="module")
def service():
    try:
        r = requests.get(f"{ENDPOINT}/", timeout=3)
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        pytest.skip(f"Fabric SHACL not reachable at {ENDPOINT}: {exc}")


def test_fabric_shapes_loaded(service):
    loaded = set(service.get("loaded_shapes") or service.get("loadedShapes") or [])
    if not loaded and "loaded_shapes" not in service:
        # server.js health payload uses loaded_shapes
        loaded = set(service.get("loaded_shapes", []))
    required = {
        "CREATE", "TRANSFER", "ADVERTISEMENT", "UPDATE_ADV",
        "BUY_OFFER", "SELL", "REQUEST_RETURN", "SELLER_ACCEPT_RETURN",
    }
    # Accept either list field name from the health JSON.
    blob = str(service)
    missing = [op for op in required if op not in blob]
    assert not missing, service


def test_create_missing_asset_id_is_rejected(service):
    r = requests.post(
        f"{ENDPOINT}/validate",
        json={"shapeType": "CREATE", "data": _ttl("CREATE", '    fabric:owner "org1User" ;\n')},
        timeout=10,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["conforms"] is False


def test_create_new_asset_conforms(service):
    extra = (
        '    fabric:assetId "asset_live" ;\n'
        '    fabric:owner "org1User" ;\n'
        "    fabric:assetExists false ;\n"
    )
    r = requests.post(
        f"{ENDPOINT}/validate",
        json={"shapeType": "CREATE", "data": _ttl("CREATE", extra)},
        timeout=10,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["conforms"] is True, body


def test_create_existing_asset_rejected(service):
    extra = (
        '    fabric:assetId "asset_live" ;\n'
        '    fabric:owner "org1User" ;\n'
        "    fabric:assetExists true ;\n"
    )
    r = requests.post(
        f"{ENDPOINT}/validate",
        json={"shapeType": "CREATE", "data": _ttl("CREATE", extra)},
        timeout=10,
    )
    assert r.status_code == 200, r.text
    assert r.json()["conforms"] is False
