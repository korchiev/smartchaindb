"""Live HTTP tests against a running SHACL microservice (no BigchainDB import)."""
from __future__ import annotations

import os

import pytest
import requests

ENDPOINT = os.environ.get("SHACL_TEST_ENDPOINT", "http://localhost:3000")
REQUIRED = {
    "CREATE",
    "TRANSFER",
    "ADVERTISEMENT",
    "UPDATE_ADV",
    "BUY_OFFER",
    "SELL",
    "REQUEST_RETURN",
    "SELLER_ACCEPT_RETURN",
}


def _ttl(op: str, extra: str = "") -> str:
    return (
        "@prefix bdb: <http://bigchaindb.com/ns#> .\n"
        "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .\n\n"
        f"<urn:tx:{op.lower()}> a bdb:{op}Transaction ;\n"
        f'    bdb:operation "{op}" ;\n'
        '    bdb:version "2.0" ;\n'
        f"{extra}"
        " .\n"
    )


VALID_TTL = {
    "CREATE": _ttl(
        "CREATE",
        '    bdb:asset [ bdb:data [ bdb:machineIdentifier "m1" ] ] ;\n'
        '    bdb:metadata [ bdb:requestCreationTimestamp "2025-01-01T00:00:00Z"^^xsd:dateTime ] ;\n'
        '    bdb:inputs [ bdb:fulfillment "f" ] ;\n'
        '    bdb:outputs [ bdb:amount "1" ] ;\n',
    ),
    "BUY_OFFER": _ttl(
        "BUY_OFFER",
        "    bdb:asset [\n"
        f'        bdb:id "{"a" * 64}" ;\n'
        f'        bdb:data [ bdb:advertisement_id "{"b" * 64}" ]\n'
        "    ] ;\n"
        "    bdb:metadata [\n"
        '        bdb:buyer_public_key "4zEhw3jXEW22ybMkdVyrs6T4TiUPW1rKt6FUQ84UyMqW" ;\n'
        '        bdb:escrow_public_key "B7nbJxzpkgjAXqEjNspzvM1JJsR9dMM371fLR5JiSD5j" ;\n'
        '        bdb:offer_amount "900" ;\n'
        '        bdb:offer_currency "USD" ;\n'
        '        bdb:offer_expiry "2099-01-01T00:00:00Z"^^xsd:dateTime ;\n'
        '        bdb:requestCreationTimestamp "2025-01-01T00:00:00Z"\n'
        "    ] ;\n"
        '    bdb:inputs [ bdb:fulfillment "f" ] ;\n'
        '    bdb:outputs [ bdb:amount "1" ] ;\n',
    ),
    "SELL": _ttl(
        "SELL",
        "    bdb:asset [\n"
        f'        bdb:data [ bdb:id "{"a" * 64}" ; bdb:buy_offer_id "{"c" * 64}" ]\n'
        "    ] ;\n"
        "    bdb:metadata [\n"
        '        bdb:seller_public_key "4zEhw3jXEW22ybMkdVyrs6T4TiUPW1rKt6FUQ84UyMqW" ;\n'
        '        bdb:buyer_public_key "B7nbJxzpkgjAXqEjNspzvM1JJsR9dMM371fLR5JiSD5j" ;\n'
        '        bdb:sale_amount "900" ;\n'
        '        bdb:sale_currency "USD"\n'
        "    ] ;\n"
        '    bdb:inputs [ bdb:fulfillment "f" ; bdb:owners_before "4zEhw3jXEW22ybMkdVyrs6T4TiUPW1rKt6FUQ84UyMqW" ] ;\n'
        '    bdb:outputs [ bdb:amount "1" ; bdb:public_keys "B7nbJxzpkgjAXqEjNspzvM1JJsR9dMM371fLR5JiSD5j" ;\n'
        '        bdb:condition [ bdb:details [ bdb:type "ed25519-sha-256" ; bdb:public_key "B7nbJxzpkgjAXqEjNspzvM1JJsR9dMM371fLR5JiSD5j" ] ;\n'
        '            bdb:uri "ni:///sha-256;abc?fpt=ed25519-sha-256&cost=131072" ] ] ;\n'
        '    bdb:outputs [ bdb:amount "1" ; bdb:public_keys "4zEhw3jXEW22ybMkdVyrs6T4TiUPW1rKt6FUQ84UyMqW" ;\n'
        '        bdb:condition [ bdb:details [ bdb:type "ed25519-sha-256" ; bdb:public_key "4zEhw3jXEW22ybMkdVyrs6T4TiUPW1rKt6FUQ84UyMqW" ] ;\n'
        '            bdb:uri "ni:///sha-256;abc?fpt=ed25519-sha-256&cost=131072" ] ] ;\n',
    ),
    "REQUEST_RETURN": _ttl(
        "REQUEST_RETURN",
        "    bdb:asset [\n"
        f'        bdb:data [ bdb:id "{"a" * 64}" ; bdb:sell_transaction_id "{"d" * 64}" ]\n'
        "    ] ;\n"
        "    bdb:metadata [\n"
        '        bdb:requester_public_key "4zEhw3jXEW22ybMkdVyrs6T4TiUPW1rKt6FUQ84UyMqW" ;\n'
        '        bdb:return_reason "defective" ;\n'
        '        bdb:return_request_timestamp "2025-01-01T00:00:00Z"^^xsd:dateTime ;\n'
        '        bdb:return_policy_details [ bdb:return_window_days 30 ; bdb:return_status "PENDING" ]\n'
        "    ] ;\n"
        '    bdb:inputs [ bdb:fulfillment "f" ] ;\n',
    ),
}


@pytest.fixture(scope="module")
def service():
    try:
        r = requests.get(f"{ENDPOINT}/", timeout=3)
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        pytest.skip(f"SHACL not reachable at {ENDPOINT}: {exc}")


def test_all_required_shapes_loaded(service):
    loaded = set(service["loaded_shapes"])
    missing = REQUIRED - loaded
    assert not missing, f"missing shapes: {missing}"


@pytest.mark.parametrize("op", sorted(REQUIRED))
def test_empty_graph_is_rejected(service, op):
    r = requests.post(
        f"{ENDPOINT}/validate",
        json={"shapeType": op, "data": _ttl(op)},
        timeout=10,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["conforms"] is False
    assert body["results"]


@pytest.mark.parametrize("op", sorted(VALID_TTL))
def test_well_formed_payload_gets_a_boolean_verdict(service, op):
    r = requests.post(
        f"{ENDPOINT}/validate",
        json={"shapeType": op, "data": VALID_TTL[op]},
        timeout=10,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert isinstance(body["conforms"], bool)
    assert isinstance(body["results"], list)


def test_unknown_shape_returns_404(service):
    r = requests.post(
        f"{ENDPOINT}/validate",
        json={"shapeType": "NO_SUCH_SHAPE", "data": _ttl("CREATE")},
        timeout=10,
    )
    assert r.status_code == 404
    body = r.json()
    assert "not found" in body["error"].lower()


def test_buy_offer_missing_advertisement_id_fails(service):
    ttl = _ttl(
        "BUY_OFFER",
        "    bdb:asset [\n"
        f'        bdb:id "{"a" * 64}" ;\n'
        "        bdb:data [ ]\n"
        "    ] ;\n"
        "    bdb:metadata [\n"
        '        bdb:buyer_public_key "4zEhw3jXEW22ybMkdVyrs6T4TiUPW1rKt6FUQ84UyMqW" ;\n'
        '        bdb:escrow_public_key "B7nbJxzpkgjAXqEjNspzvM1JJsR9dMM371fLR5JiSD5j" ;\n'
        '        bdb:offer_amount "900" ;\n'
        '        bdb:offer_currency "USD" ;\n'
        '        bdb:offer_expiry "2099-01-01T00:00:00Z"^^xsd:dateTime ;\n'
        '        bdb:requestCreationTimestamp "2025-01-01T00:00:00Z"\n'
        "    ] ;\n"
        '    bdb:inputs [ bdb:fulfillment "f" ] ;\n'
        '    bdb:outputs [ bdb:amount "1" ] ;\n',
    )
    r = requests.post(f"{ENDPOINT}/validate", json={"shapeType": "BUY_OFFER", "data": ttl}, timeout=10)
    assert r.status_code == 200
    body = r.json()
    assert body["conforms"] is False
    assert body["results"]
