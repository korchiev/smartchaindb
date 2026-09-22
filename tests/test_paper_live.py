"""
Live integration tests against a running SHACL microservice.

These tests target the SHACLValidatorClient built from the current source
against a real HTTP endpoint. They are skipped when the endpoint is not
reachable so ``pytest`` can still run offline.

Run standalone:

    # from WSL, in bigchaindb/backend/localshacl/shapes:
    PORT=3000 node index.js

    # from Windows:
    python -m pytest tests/test_paper_live.py -v --noconftest -s

Env vars
--------
SHACL_TEST_ENDPOINT   default http://localhost:3000
"""

from __future__ import annotations

import importlib.util
import os
import sys
import types
from pathlib import Path
from typing import Any, Dict

import pytest
import requests

ROOT = Path(__file__).resolve().parent.parent
SHACL_VALIDATOR_PATH = ROOT / "bigchaindb" / "common" / "shacl_validator.py"
ENDPOINT = os.environ.get("SHACL_TEST_ENDPOINT", "http://localhost:3000")


def _install_bigchaindb_stub(shacl_cfg: Dict[str, Any] | None = None) -> None:
    for name in [n for n in list(sys.modules) if n == "bigchaindb" or n.startswith("bigchaindb.")]:
        del sys.modules[name]
    stub = types.ModuleType("bigchaindb")
    stub.config = dict(shacl_cfg or {
        "shacl": {"enabled": True, "endpoint": ENDPOINT, "timeout": 5}
    })
    stub.__path__ = []
    sys.modules["bigchaindb"] = stub
    sys.modules["bigchaindb.config_utils"] = types.ModuleType("bigchaindb.config_utils")
    stub.config_utils = sys.modules["bigchaindb.config_utils"]


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "shacl_validator_live", str(SHACL_VALIDATOR_PATH)
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def live_service():
    try:
        r = requests.get(f"{ENDPOINT}/", timeout=2)
        assert r.status_code == 200
        return r.json()
    except Exception as exc:
        pytest.skip(f"SHACL service not reachable at {ENDPOINT}: {exc}")


@pytest.fixture
def client(live_service):
    os.environ.pop("BIGCHAINDB_SHACL_FAIL_OPEN", None)
    _install_bigchaindb_stub()
    module = _load_module()
    return module.SHACLValidatorClient()


def _tx_buy_offer(operation="BUY_OFFER") -> Dict[str, Any]:
    return {
        "id": "b" * 64,
        "operation": operation,
        "version": "2.0",
        "asset": {"id": "a" * 64, "data": {"advertisement_id": "c" * 64}},
        "metadata": {
            "buyer_public_key": "4zEhw3jXEW22ybMkdVyrs6T4TiUPW1rKt6FUQ84UyMqW",
            "escrow_public_key": "B7nbJxzpkgjAXqEjNspzvM1JJsR9dMM371fLR5JiSD5j",
            "offer_amount": "900",
            "offer_currency": "USD",
            "offer_expiry": "2099-01-01T00:00:00Z",
            "requestCreationTimestamp": "2025-01-01T00:00:00Z",
        },
        "inputs": [{"fulfillment": "abc123", "owners_before": ["k"], "fulfills": None}],
        "outputs": [{"amount": "1", "public_keys": ["k"]}],
    }


class TestLiveSHACL:
    def test_health_reports_all_loaded_shapes(self, live_service):
        loaded = set(live_service["loaded_shapes"])
        required = {
            "CREATE", "TRANSFER", "ADVERTISEMENT", "UPDATE_ADV",
            "BUY_OFFER", "SELL", "REQUEST_RETURN", "SELLER_ACCEPT_RETURN",
        }
        assert required.issubset(loaded), f"missing: {required - loaded}"

    def test_shape_coverage_populates_from_live_service(self, client):
        ok, fail = client._ensure_shape_coverage("BUY_OFFER")
        assert ok is True
        assert fail is None
        assert client._loaded_shapes is not None
        assert "BUY_OFFER" in client._loaded_shapes

    def test_live_buy_offer_returns_a_verdict(self, client):
        conforms, results = client.validate_transaction(_tx_buy_offer())
        # Whatever the shape decides is fine; we assert the plumbing works.
        assert isinstance(conforms, bool)
        assert isinstance(results, list)

    def test_live_buy_offer_without_advertisement_id_is_rejected(self, client):
        tx = _tx_buy_offer()
        tx["asset"]["data"] = {}
        conforms, results = client.validate_transaction(tx)
        assert conforms is False
        assert results

    def test_live_unknown_operation_fails_closed(self, client):
        # Not in REQUIRED_SHAPES but also not in loaded shapes -> service 404s
        tx = _tx_buy_offer(operation="TOTALLY_UNKNOWN_OP_XYZ")
        conforms, results = client.validate_transaction(tx)
        assert conforms is False
        assert results

    def test_unreachable_endpoint_fails_closed(self):
        os.environ.pop("BIGCHAINDB_SHACL_FAIL_OPEN", None)
        _install_bigchaindb_stub({
            "shacl": {
                "enabled": True,
                "endpoint": "http://127.0.0.1:1",  # nothing listens here
                "timeout": 2,
            }
        })
        module = _load_module()
        client = module.SHACLValidatorClient()
        conforms, results = client.validate_transaction(_tx_buy_offer())
        assert conforms is False
        assert "shape list" in results[0]["message"] or "Cannot connect" in results[0]["message"]

    def test_unreachable_endpoint_fails_open_when_flag_set(self, monkeypatch):
        monkeypatch.setenv("BIGCHAINDB_SHACL_FAIL_OPEN", "true")
        _install_bigchaindb_stub({
            "shacl": {
                "enabled": True,
                "endpoint": "http://127.0.0.1:1",
                "timeout": 2,
            }
        })
        module = _load_module()
        client = module.SHACLValidatorClient()
        conforms, results = client.validate_transaction(_tx_buy_offer())
        assert conforms is True
        assert results == []
