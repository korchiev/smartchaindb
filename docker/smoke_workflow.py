#!/usr/bin/env python3
"""Live marketplace lifecycle through BigchainDB + SHACL.

CREATE -> ADVERTISEMENT -> UPDATE_ADV -> BUY_OFFER -> SELL
-> REQUEST_RETURN -> SELLER_ACCEPT_RETURN
"""
import time
from datetime import datetime, timedelta, timezone

import requests
from bigchaindb_driver.crypto import generate_keypair
from bigchaindb.common.transaction import Input, Transaction

API = "http://127.0.0.1:9984/api/v1/transactions"
NOW = datetime.now(timezone.utc)


def iso(dt):
    return dt.replace(microsecond=dt.microsecond or 123456).isoformat()


def gen_input(public_key):
    return [Input.generate([public_key])]


def wait_api():
    last = None
    urls = (
        "http://127.0.0.1:9984/",
        "http://tendermint:26657/status",
    )
    for _attempt in range(40):
        try:
            for url in urls:
                resp = requests.get(url, timeout=3)
                if resp.status_code >= 500:
                    raise requests.RequestException(url + " " + str(resp.status_code))
            return
        except requests.RequestException as exc:
            last = exc
        time.sleep(2)
    raise SystemExit("API never became reachable: {}".format(last))


def post(tx, label):
    resp = requests.post(API + "?mode=commit", json=tx.to_dict(), timeout=45)
    print("POST", label, resp.status_code)
    print(resp.text[:800])
    if resp.status_code >= 400:
        raise SystemExit(1)
    txid = resp.json().get("id") or tx.id
    got = requests.get(API + "/" + txid, timeout=10)
    print("GET ", label, got.status_code, got.json().get("operation"), txid)
    if got.status_code != 200:
        raise SystemExit(1)
    return txid


wait_api()

seller = generate_keypair()
buyer = generate_keypair()
escrow = generate_keypair()

create_tx = Transaction.create(
    [seller.public_key],
    [([seller.public_key], 1)],
    metadata={"requestCreationTimestamp": iso(NOW)},
    asset={
        "machineIdentifier": "wsl-workflow-1",
        "capability": ["sell"],
        "capabilityParameters": {"p": "1"},
    },
).sign([seller.private_key])
create_id = post(create_tx, "CREATE")

adv_tx = Transaction.advertisement(
    inputs=gen_input(seller.public_key),
    asset_id=create_id,
    metadata={
        "status": "OPEN",
        "advertiser_public_key": seller.public_key,
        "price": "100.00",
        "description": "workflow smoke item",
        "category": "test",
        "expiry_date": iso(NOW + timedelta(days=30)),
        "requestCreationTimestamp": iso(NOW),
    },
).sign([seller.private_key])
adv_id = post(adv_tx, "ADVERTISEMENT")

upd_tx = Transaction.update_adv(
    inputs=gen_input(seller.public_key),
    advertisement_id=adv_id,
    metadata={
        "status": "OPEN",
        "updater_public_key": seller.public_key,
        "price": "99.00",
        "expiry_date": iso(NOW + timedelta(days=30)),
        "requestCreationTimestamp": iso(NOW),
    },
).sign([seller.private_key])
upd_id = post(upd_tx, "UPDATE_ADV")

offer_tx = Transaction.buy_offer(
    inputs=gen_input(buyer.public_key),
    asset_id=create_id,
    advertisement_id=adv_id,
    metadata={
        "buyer_public_key": buyer.public_key,
        "escrow_public_key": escrow.public_key,
        "offer_amount": "100",
        "offer_currency": "USD",
        "offer_timestamp": iso(NOW),
        "offer_expiry": iso(NOW + timedelta(days=7)),
        "requestCreationTimestamp": iso(NOW),
    },
).sign([buyer.private_key])
offer_id = post(offer_tx, "BUY_OFFER")

sell_tx = Transaction.sell(
    inputs=create_tx.to_inputs(),
    asset_id=create_id,
    buy_offer_id=offer_id,
    metadata={
        "seller_public_key": seller.public_key,
        "buyer_public_key": buyer.public_key,
        "sale_amount": "100",
        "sale_currency": "USD",
        "sale_timestamp": iso(NOW),
        "sale_notes": "workflow smoke sale",
        "requestCreationTimestamp": iso(NOW),
    },
).sign([seller.private_key])
sell_id = post(sell_tx, "SELL")

ret_tx = Transaction.request_return(
    inputs=gen_input(buyer.public_key),
    asset_id=create_id,
    sell_transaction_id=sell_id,
    metadata={
        "requester_public_key": buyer.public_key,
        "return_reason": "defective item",
        "return_request_timestamp": iso(NOW),
        "return_policy_details": {
            "return_window_days": 30,
            "return_conditions": "unopened",
            "return_status": "PENDING",
        },
        "requestCreationTimestamp": iso(NOW),
    },
).sign([buyer.private_key])
ret_id = post(ret_tx, "REQUEST_RETURN")

acc_tx = Transaction.seller_accept_return(
    inputs=gen_input(seller.public_key),
    asset_id=create_id,
    request_return_id=ret_id,
    metadata={
        "seller_public_key": seller.public_key,
        "acceptance_timestamp": iso(NOW),
        "processing_notes": "accepted",
        "requestCreationTimestamp": iso(NOW),
        "refund_details": {
            "refund_amount": 100.0,
            "refund_currency": "USD",
            "refund_method": "original_payment",
        },
    },
).sign([seller.private_key])
acc_id = post(acc_tx, "SELLER_ACCEPT_RETURN")

print("WORKFLOW OK")
print("CREATE", create_id)
print("ADVERTISEMENT", adv_id)
print("UPDATE_ADV", upd_id)
print("BUY_OFFER", offer_id)
print("SELL", sell_id)
print("REQUEST_RETURN", ret_id)
print("SELLER_ACCEPT_RETURN", acc_id)
