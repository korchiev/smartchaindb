"""
Paper-hardening tests for the fail-closed + envelope-tight changes.

These tests do NOT import the full ``bigchaindb`` package (which pulls in
Tendermint, MongoDB, and a Gunicorn wire stack that will not install on a
plain developer machine). Instead they load ``shacl_validator.py`` in
isolation with a stub ``bigchaindb`` package that provides only what the
module needs: the ``config`` dict and a ``config_utils`` placeholder.

Covers:

* SHACL fail-closed default vs ``BIGCHAINDB_SHACL_FAIL_OPEN`` opt-in
* Startup shape-coverage check (missing shape rejects when fail-closed)
* Every terminal error path (connection, timeout, 404, 5xx, unexpected)
* JSON-schema envelope invariants for the 5 loosened marketplace ops
"""

from __future__ import annotations

import importlib.util
import os
import sys
import types
from pathlib import Path
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest
import requests
import yaml
from jsonschema import ValidationError, validate

ROOT = Path(__file__).resolve().parent.parent
SHACL_VALIDATOR_PATH = ROOT / "bigchaindb" / "common" / "shacl_validator.py"
SCHEMA_DIR = ROOT / "bigchaindb" / "common" / "schema"


# ---------------------------------------------------------------------------
# Isolated import of shacl_validator.py without triggering bigchaindb/__init__.
# ---------------------------------------------------------------------------

_DEFAULT_SHACL_CONFIG: Dict[str, Any] = {
    "shacl": {
        "enabled": True,
        "endpoint": "http://shacleng:3000",
        "timeout": 5,
        "cache_enabled": False,
    }
}


def _install_bigchaindb_stub(shacl_cfg: Dict[str, Any] | None = None) -> None:
    """
    Replace any existing bigchaindb.* modules with a minimal stub so
    ``import bigchaindb`` (from inside shacl_validator.py) returns
    a small in-memory package with just ``config`` and ``config_utils``.
    """
    for name in [n for n in list(sys.modules) if n == "bigchaindb" or n.startswith("bigchaindb.")]:
        del sys.modules[name]

    stub = types.ModuleType("bigchaindb")
    stub.config = dict(shacl_cfg or _DEFAULT_SHACL_CONFIG)
    stub.__path__ = []  # mark it as a package so submodule imports resolve
    sys.modules["bigchaindb"] = stub

    common = types.ModuleType("bigchaindb.common")
    common.__path__ = [str(ROOT / "bigchaindb" / "common")]
    sys.modules["bigchaindb.common"] = common
    stub.common = common

    config_utils_stub = types.ModuleType("bigchaindb.config_utils")
    sys.modules["bigchaindb.config_utils"] = config_utils_stub
    stub.config_utils = config_utils_stub


def _load_shacl_module():
    """Load bigchaindb/common/shacl_validator.py in isolation and return it."""
    spec = importlib.util.spec_from_file_location(
        "shacl_validator_under_test", str(SHACL_VALIDATOR_PATH)
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def shacl_module():
    """Fresh isolated import of shacl_validator with fail-closed default config."""
    os.environ.pop("BIGCHAINDB_SHACL_FAIL_OPEN", None)
    _install_bigchaindb_stub()
    return _load_shacl_module()


@pytest.fixture
def enabled_client(shacl_module):
    client = shacl_module.SHACLValidatorClient()
    # Pre-populate the shape cache so tests can focus on validate() behavior
    # without an extra GET / round-trip.
    client._loaded_shapes = set(shacl_module.REQUIRED_SHAPES)
    return client


# ---------------------------------------------------------------------------
# Config + fail policy
# ---------------------------------------------------------------------------


class TestFailPolicy:
    def test_defaults_to_fail_closed(self, shacl_module):
        client = shacl_module.SHACLValidatorClient()
        assert client.enabled is True
        assert client.fail_open is False

    def test_env_var_enables_fail_open(self, monkeypatch, shacl_module):
        monkeypatch.setenv("BIGCHAINDB_SHACL_FAIL_OPEN", "true")
        client = shacl_module.SHACLValidatorClient()
        assert client.fail_open is True

    def test_config_flag_enables_fail_open_when_env_missing(self, monkeypatch):
        monkeypatch.delenv("BIGCHAINDB_SHACL_FAIL_OPEN", raising=False)
        _install_bigchaindb_stub({"shacl": {"enabled": True, "fail_open": True}})
        module = _load_shacl_module()
        client = module.SHACLValidatorClient()
        assert client.fail_open is True

    def test_env_overrides_config_flag(self, monkeypatch):
        monkeypatch.setenv("BIGCHAINDB_SHACL_FAIL_OPEN", "false")
        _install_bigchaindb_stub({"shacl": {"enabled": True, "fail_open": True}})
        module = _load_shacl_module()
        client = module.SHACLValidatorClient()
        assert client.fail_open is False

    @pytest.mark.parametrize("truthy", ["1", "true", "TRUE", "yes", "On"])
    def test_bool_env_truthy_values(self, monkeypatch, shacl_module, truthy):
        monkeypatch.setenv("BIGCHAINDB_SHACL_FAIL_OPEN", truthy)
        client = shacl_module.SHACLValidatorClient()
        assert client.fail_open is True

    @pytest.mark.parametrize("falsy", ["0", "no", "off", "false", "anything-else"])
    def test_bool_env_falsy_values(self, monkeypatch, shacl_module, falsy):
        monkeypatch.setenv("BIGCHAINDB_SHACL_FAIL_OPEN", falsy)
        client = shacl_module.SHACLValidatorClient()
        assert client.fail_open is False

    def test_fail_helper_returns_reject_in_closed_mode(self, enabled_client):
        conforms, results = enabled_client._fail("boom")
        assert conforms is False
        assert results == [{"message": "boom"}]

    def test_fail_helper_returns_accept_in_open_mode(self, monkeypatch, shacl_module):
        monkeypatch.setenv("BIGCHAINDB_SHACL_FAIL_OPEN", "true")
        client = shacl_module.SHACLValidatorClient()
        conforms, results = client._fail("boom")
        assert conforms is True
        assert results == []


# ---------------------------------------------------------------------------
# Shape coverage check
# ---------------------------------------------------------------------------


def _mock_shape_list_response(loaded):
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"loaded_shapes": list(loaded)}
    resp.text = "ok"
    return resp


class TestShapeCoverage:
    def test_populates_cache_on_first_call(self, monkeypatch, shacl_module):
        client = shacl_module.SHACLValidatorClient()
        with patch("requests.get", return_value=_mock_shape_list_response(shacl_module.REQUIRED_SHAPES)) as g:
            ok, fail = client._ensure_shape_coverage("BUY_OFFER")
        assert ok is True
        assert fail is None
        assert client._loaded_shapes == set(shacl_module.REQUIRED_SHAPES)
        g.assert_called_once()

    def test_reuses_cache_on_second_call(self, shacl_module):
        client = shacl_module.SHACLValidatorClient()
        with patch("requests.get", return_value=_mock_shape_list_response(shacl_module.REQUIRED_SHAPES)) as g:
            client._ensure_shape_coverage("BUY_OFFER")
            client._ensure_shape_coverage("SELL")
        assert g.call_count == 1

    def test_missing_shape_rejects_when_fail_closed(self, shacl_module):
        client = shacl_module.SHACLValidatorClient()
        partial = set(shacl_module.REQUIRED_SHAPES) - {"REQUEST_RETURN"}
        with patch("requests.get", return_value=_mock_shape_list_response(partial)):
            ok, fail = client._ensure_shape_coverage("REQUEST_RETURN")
        assert ok is False
        conforms, results = fail
        assert conforms is False
        assert "REQUEST_RETURN" in results[0]["message"]

    def test_missing_shape_accepts_when_fail_open(self, monkeypatch, shacl_module):
        monkeypatch.setenv("BIGCHAINDB_SHACL_FAIL_OPEN", "true")
        client = shacl_module.SHACLValidatorClient()
        with patch("requests.get", return_value=_mock_shape_list_response({"CREATE"})):
            ok, fail = client._ensure_shape_coverage("SELL")
        assert ok is False
        conforms, results = fail
        assert conforms is True  # fail-open lets it through
        assert results == []

    def test_service_unreachable_rejects_when_fail_closed(self, shacl_module):
        client = shacl_module.SHACLValidatorClient()
        with patch("requests.get", side_effect=requests.exceptions.ConnectionError("down")):
            ok, fail = client._ensure_shape_coverage("SELL")
        assert ok is False
        conforms, results = fail
        assert conforms is False
        assert "did not return a shape list" in results[0]["message"]

    def test_invalidate_shape_cache_forces_refetch(self, shacl_module):
        client = shacl_module.SHACLValidatorClient()
        with patch("requests.get", return_value=_mock_shape_list_response(shacl_module.REQUIRED_SHAPES)) as g:
            client._ensure_shape_coverage("SELL")
            client.invalidate_shape_cache()
            client._ensure_shape_coverage("SELL")
        assert g.call_count == 2

    def test_all_marketplace_ops_are_required(self, shacl_module):
        assert shacl_module.REQUIRED_SHAPES >= {
            "CREATE", "TRANSFER",
            "ADVERTISEMENT", "UPDATE_ADV",
            "BUY_OFFER", "SELL",
            "REQUEST_RETURN", "SELLER_ACCEPT_RETURN",
        }


# ---------------------------------------------------------------------------
# validate_transaction end-to-end paths
# ---------------------------------------------------------------------------


def _valid_buy_offer_tx() -> Dict[str, Any]:
    return {
        "id": "tx-1",
        "operation": "BUY_OFFER",
        "version": "2.0",
        "asset": {"id": "a" * 64, "data": {"advertisement_id": "b" * 64}},
        "metadata": {"buyer_public_key": "k"},
        "inputs": [{"fulfillment": "f", "owners_before": ["o"], "fulfills": None}],
        "outputs": [{"amount": "1"}],
    }


class TestValidateTransaction:
    def _post_ok(self, conforms=True, results=None, read_set=None):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {
            "conforms": conforms,
            "results": results or [],
            "read_set": read_set,
        }
        return resp

    def test_disabled_client_skips_validation(self, monkeypatch):
        _install_bigchaindb_stub({"shacl": {"enabled": False}})
        module = _load_shacl_module()
        client = module.SHACLValidatorClient()
        conforms, results = client.validate_transaction(_valid_buy_offer_tx())
        assert conforms is True
        assert results == []

    def test_missing_operation_is_rejected(self, enabled_client):
        tx = _valid_buy_offer_tx()
        tx.pop("operation")
        conforms, results = enabled_client.validate_transaction(tx)
        assert conforms is False
        assert "operation" in results[0]["message"].lower()

    def test_happy_path(self, enabled_client):
        with patch("requests.post", return_value=self._post_ok(True)):
            conforms, results = enabled_client.validate_transaction(_valid_buy_offer_tx())
        assert conforms is True
        assert results == []

    def test_delta_cache_skips_second_http_call(self, enabled_client):
        enabled_client.cache_enabled = True
        tx = _valid_buy_offer_tx()
        read_set = {"tx_ids": ["b" * 64], "queries": 1}
        with patch("requests.post", return_value=self._post_ok(True, read_set=read_set)) as post:
            first = enabled_client.validate_transaction(
                tx,
                dep_state_hash="dep-open",
                dep_ids=["b" * 64],
                covered_ids={"b" * 64},
            )
            second = enabled_client.validate_transaction(
                tx,
                dep_state_hash="dep-open",
                dep_ids=["b" * 64],
                covered_ids={"b" * 64},
            )
        assert first == (True, [])
        assert second == (True, [])
        assert post.call_count == 1
        enabled_client.on_tx_committed({"id": "b" * 64, "operation": "ADVERTISEMENT", "asset": {}})
        with patch("requests.post", return_value=self._post_ok(True)) as post2:
            third = enabled_client.validate_transaction(tx, dep_state_hash="dep-open")
        assert third == (True, [])
        assert post2.call_count == 1

    def test_uncovered_read_is_not_cached(self, enabled_client):
        enabled_client.cache_enabled = True
        tx = _valid_buy_offer_tx()
        read_set = {"tx_ids": ["c" * 64], "queries": 1}
        with patch("requests.post", return_value=self._post_ok(True, read_set=read_set)) as post:
            for _ in range(2):
                assert enabled_client.validate_transaction(
                    tx,
                    dep_state_hash="dep-open",
                    dep_ids=["b" * 64],
                    covered_ids={"b" * 64},
                ) == (True, [])
        assert post.call_count == 2
        assert enabled_client.delta_cache.stats()["size"] == 0
        assert enabled_client.readset_snapshot()["uncovered"] == 2

    def test_missing_read_set_is_not_cached(self, enabled_client):
        enabled_client.cache_enabled = True
        tx = _valid_buy_offer_tx()
        with patch("requests.post", return_value=self._post_ok(True)) as post:
            for _ in range(2):
                assert enabled_client.validate_transaction(
                    tx,
                    dep_state_hash="dep-open",
                    dep_ids=["b" * 64],
                    covered_ids={"b" * 64},
                ) == (True, [])
        assert post.call_count == 2
        assert enabled_client.delta_cache.stats()["size"] == 0

    def test_conflict_aborts_during_http(self, enabled_client):
        enabled_client.cache_enabled = True
        tx = _valid_buy_offer_tx()

        def post_side_effect(*_args, **_kwargs):
            enabled_client.on_tx_committed(
                {
                    "id": "upd1",
                    "operation": "UPDATE_ADV",
                    "asset": {"id": "b" * 64, "data": {"id": "b" * 64}},
                }
            )
            return self._post_ok(True)

        with patch("requests.post", side_effect=post_side_effect) as post:
            conforms, results = enabled_client.validate_transaction(tx, dep_state_hash="dep-open")
        assert post.call_count == 1
        assert conforms is False
        assert "conflict" in results[0]["message"].lower()
        assert enabled_client.delta_cache.get(tx["id"], "dep-open") is None

    def test_shape_violation_returned(self, enabled_client):
        with patch(
            "requests.post",
            return_value=self._post_ok(False, [{"message": ["advertisement_id required"]}]),
        ):
            conforms, results = enabled_client.validate_transaction(_valid_buy_offer_tx())
        assert conforms is False
        assert results

    def test_connection_error_fails_closed(self, enabled_client):
        with patch("requests.post", side_effect=requests.exceptions.ConnectionError("down")):
            conforms, results = enabled_client.validate_transaction(_valid_buy_offer_tx())
        assert conforms is False
        assert "Cannot connect" in results[0]["message"]
        # cache should have been invalidated so next call re-fetches shapes
        assert enabled_client._loaded_shapes is None

    def test_connection_error_fails_open_when_flag_set(self, monkeypatch, shacl_module):
        monkeypatch.setenv("BIGCHAINDB_SHACL_FAIL_OPEN", "true")
        client = shacl_module.SHACLValidatorClient()
        client._loaded_shapes = set(shacl_module.REQUIRED_SHAPES)
        with patch("requests.post", side_effect=requests.exceptions.ConnectionError("down")):
            conforms, results = client.validate_transaction(_valid_buy_offer_tx())
        assert conforms is True
        assert results == []

    def test_timeout_fails_closed(self, enabled_client):
        with patch("requests.post", side_effect=requests.exceptions.Timeout("slow")):
            conforms, results = enabled_client.validate_transaction(_valid_buy_offer_tx())
        assert conforms is False
        assert "timeout" in results[0]["message"].lower()

    def test_404_shape_missing_fails_closed(self, enabled_client):
        resp = MagicMock()
        resp.status_code = 404
        resp.json.return_value = {"error": "not found", "available_shapes": ["CREATE"]}
        resp.text = "not found"
        with patch("requests.post", return_value=resp):
            conforms, results = enabled_client.validate_transaction(_valid_buy_offer_tx())
        assert conforms is False
        assert "not loaded" in results[0]["message"] or "not found" in results[0]["message"]

    def test_5xx_fails_closed(self, enabled_client):
        resp = MagicMock()
        resp.status_code = 503
        resp.json.side_effect = ValueError("no json")
        resp.text = "upstream down"
        with patch("requests.post", return_value=resp):
            conforms, results = enabled_client.validate_transaction(_valid_buy_offer_tx())
        assert conforms is False
        assert "HTTP 503" in results[0]["message"]

    def test_unknown_operation_uses_shape_coverage(self, enabled_client):
        tx = _valid_buy_offer_tx()
        tx["operation"] = "TOTALLY_UNKNOWN"
        # TOTALLY_UNKNOWN is not in REQUIRED_SHAPES so shape coverage should pass;
        # the POST decides. Simulate the SHACL service returning 404.
        resp = MagicMock()
        resp.status_code = 404
        resp.json.return_value = {"error": "no shape", "available_shapes": list(enabled_client._loaded_shapes)}
        resp.text = "no shape"
        with patch("requests.post", return_value=resp):
            conforms, results = enabled_client.validate_transaction(tx)
        assert conforms is False


# ---------------------------------------------------------------------------
# JSON-schema envelope regression for the 5 loosened marketplace ops
# ---------------------------------------------------------------------------


def _load_schema(name: str) -> Dict[str, Any]:
    with open(SCHEMA_DIR / f"{name}.yaml", "r", encoding="utf-8") as fh:
        schema = yaml.safe_load(fh)
    # The runtime applies TX_SCHEMA_COMMON before the per-operation schema, so
    # the shared definitions (sha3_hexdigest, input, output, base58, ...) live
    # in the common file. Merge them in so a per-op schema can be validated on
    # its own inside a unit test.
    if "definitions" not in schema:
        with open(SCHEMA_DIR / "transaction_v2.0.yaml", "r", encoding="utf-8") as fh:
            common = yaml.safe_load(fh)
        schema["definitions"] = common.get("definitions", {})
    return schema


def _valid_input(fulfills=None) -> Dict[str, Any]:
    return {
        "owners_before": ["B" * 44],
        "fulfillment": "abcDEF123_-",
        "fulfills": fulfills,
    }


def _valid_output() -> Dict[str, Any]:
    return {
        "amount": "1",
        "public_keys": ["B" * 44],
        "condition": {
            "details": {"type": "ed25519-sha-256", "public_key": "B" * 44},
            "uri": "ni:///sha-256;abc?fpt=ed25519-sha-256&cost=131072",
        },
    }


ENVELOPE_OPS = [
    ("buyoffer", 1, 1),          # (schema_name, min_outputs, max_outputs)
    ("sell", 2, 2),
    ("seller_accept_return", 0, None),
    ("update_adv", 0, 1),
    ("request_return", 0, None),
]


def _base_tx(op_upper: str, min_outputs: int) -> Dict[str, Any]:
    tx = {
        "asset": {"id": "a" * 64, "data": {"anything": "goes"}},
        "metadata": {"free_form": True},
        "inputs": [_valid_input()],
    }
    if min_outputs:
        tx["outputs"] = [_valid_output() for _ in range(min_outputs)]
    return tx


class TestSchemaEnvelopes:
    def test_all_five_schemas_load(self):
        for name, _, _ in ENVELOPE_OPS:
            schema = _load_schema(f"transaction_{name}_v2.0")
            assert schema["type"] == "object"
            assert schema["properties"]["metadata"]["additionalProperties"] is True

    @pytest.mark.parametrize("name,min_out,max_out", ENVELOPE_OPS)
    def test_envelope_accepts_free_form_data_and_metadata(self, name, min_out, max_out):
        schema = _load_schema(f"transaction_{name}_v2.0")
        tx = _base_tx(name.upper(), min_out)
        # Add outputs if the schema requires them but our helper produced 0
        if min_out == 0 and "outputs" in schema["properties"]:
            tx["outputs"] = []
        validate(instance=tx, schema=schema)

    @pytest.mark.parametrize("name,min_out,_", ENVELOPE_OPS)
    def test_envelope_accepts_null_data(self, name, min_out, _):
        schema = _load_schema(f"transaction_{name}_v2.0")
        tx = _base_tx(name.upper(), min_out)
        tx["asset"]["data"] = None
        validate(instance=tx, schema=schema)

    @pytest.mark.parametrize("name,min_out,_", ENVELOPE_OPS)
    def test_envelope_rejects_missing_asset_id(self, name, min_out, _):
        schema = _load_schema(f"transaction_{name}_v2.0")
        tx = _base_tx(name.upper(), min_out)
        del tx["asset"]["id"]
        with pytest.raises(ValidationError):
            validate(instance=tx, schema=schema)

    @pytest.mark.parametrize("name,min_out,_", ENVELOPE_OPS)
    def test_envelope_rejects_extra_asset_field(self, name, min_out, _):
        schema = _load_schema(f"transaction_{name}_v2.0")
        tx = _base_tx(name.upper(), min_out)
        tx["asset"]["nonsense"] = "x"
        with pytest.raises(ValidationError):
            validate(instance=tx, schema=schema)

    def test_sell_requires_exactly_two_outputs(self):
        schema = _load_schema("transaction_sell_v2.0")
        tx = _base_tx("SELL", 2)
        tx["outputs"] = [_valid_output()]  # only one
        with pytest.raises(ValidationError):
            validate(instance=tx, schema=schema)

    def test_buyoffer_requires_at_least_one_output(self):
        schema = _load_schema("transaction_buyoffer_v2.0")
        tx = _base_tx("BUY_OFFER", 1)
        tx["outputs"] = []
        with pytest.raises(ValidationError):
            validate(instance=tx, schema=schema)

    def test_request_return_fulfills_accepts_null_or_object(self):
        schema = _load_schema("transaction_request_return_v2.0")
        tx = _base_tx("REQUEST_RETURN", 0)

        # null (driver's current behaviour)
        tx["inputs"] = [_valid_input(fulfills=None)]
        validate(instance=tx, schema=schema)

        # object with txid/output
        tx["inputs"] = [_valid_input(fulfills={"txid": "s" * 64, "output": 0})]
        validate(instance=tx, schema=schema)

        # object with transaction_id/output_index
        tx["inputs"] = [_valid_input(fulfills={"transaction_id": "s" * 64, "output_index": 0})]
        validate(instance=tx, schema=schema)

    def test_request_return_rejects_asset_id_not_hex(self):
        schema = _load_schema("transaction_request_return_v2.0")
        tx = _base_tx("REQUEST_RETURN", 0)
        tx["asset"]["id"] = "not-hex"
        with pytest.raises(ValidationError):
            validate(instance=tx, schema=schema)

    def test_update_adv_allows_zero_outputs(self):
        schema = _load_schema("transaction_update_adv_v2.0")
        tx = _base_tx("UPDATE_ADV", 0)
        tx["outputs"] = []
        validate(instance=tx, schema=schema)

    def test_update_adv_rejects_two_outputs(self):
        schema = _load_schema("transaction_update_adv_v2.0")
        tx = _base_tx("UPDATE_ADV", 0)
        tx["outputs"] = [_valid_output(), _valid_output()]
        with pytest.raises(ValidationError):
            validate(instance=tx, schema=schema)
