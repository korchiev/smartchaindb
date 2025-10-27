#!/usr/bin/env python3
import time
from datetime import datetime, timedelta
import requests

from bigchaindb.common.transaction import Transaction, TransactionLink
from bigchaindb.common.crypto import generate_key_pair
from bigchaindb.common.transaction import Input, Output

BDB_URL = "http://localhost:9984"
TX_URL = f"{BDB_URL}/api/v1/transactions/"


def wait_committed(tx_id: str, timeout: int = 30) -> bool:
    start = time.time()
    while time.time() - start < timeout:
        r = requests.get(f"{BDB_URL}/api/v1/transactions/{tx_id}", timeout=5)
        if r.status_code == 200:
            return True
        time.sleep(0.3)
    return False


def send(tx):
    return requests.post(TX_URL, headers={'Content-Type': 'application/json'}, json=tx.to_dict(), timeout=30)


def create_asset(test_id: int, owner):
    tx = Transaction(
        operation=Transaction.CREATE,
        asset={'data': {
            'machineIdentifier': f'conflict_asset_{test_id}_{int(time.time()*1000)}',
            'capability': ['read'],
            'capabilityParameters': {'type': 'debug'}
        }},
        metadata={'test_id': test_id, 'test_type': 'CREATE', 'requestCreationTimestamp': datetime.now().isoformat()}
    )
    tx.inputs = [Input.generate([owner.public_key])]
    tx.outputs = [Output.generate([owner.public_key], amount=1)]
    tx.sign([owner.private_key])
    return tx


def create_advertisement(asset_id: str, advertiser):
    tx = Transaction(
        operation='ADVERTISEMENT',
        asset={'id': asset_id, 'data': {'id': asset_id}},
        metadata={
            'advertiser_public_key': advertiser.public_key,
            'status': 'OPEN',
            'price': '1000',
            'description': 'test advertisement',
            'advertisement_timestamp': datetime.now().isoformat(),
            'requestCreationTimestamp': datetime.now().isoformat(),
            'test_type': 'ADVERTISEMENT',
        }
    )
    tx.inputs = [Input.generate([advertiser.public_key])]
    tx.outputs = [Output.generate([advertiser.public_key], amount=1)]
    tx.sign([advertiser.private_key])
    return tx


def create_buy_offer(asset_id: str, adv_id: str, buyer, escrow):
    tx = Transaction(
        operation='BUY_OFFER',
        asset={'id': asset_id, 'data': {'id': asset_id, 'advertisement_id': adv_id}},
        metadata={
            'buyer_public_key': buyer.public_key,
            'offer_amount': '1000',
            'offer_expiry': (datetime.now() + timedelta(days=7)).isoformat(),
            'escrow_public_key': escrow.public_key,
            'offer_timestamp': datetime.now().isoformat(),
            'requestCreationTimestamp': datetime.now().isoformat(),
            'test_type': 'BUY_OFFER',
        }
    )
    tx.inputs = [Input.generate([buyer.public_key])]
    tx.outputs = [Output.generate([escrow.public_key], amount=1)]
    tx.sign([buyer.private_key])
    return tx


def create_sell(asset_id: str, buy_offer_id: str, seller, buyer):
    md = {
        'seller_public_key': seller.public_key,
        'buyer_public_key': buyer.public_key,
        'sale_amount': '1000',
        'sale_currency': 'USD',
        'sale_timestamp': datetime.now().isoformat(),
        'requestCreationTimestamp': datetime.now().isoformat(),
        'test_type': 'SELL',
    }
    fulfills_link = TransactionLink.from_dict({'output_index': 0, 'transaction_id': asset_id})
    sell_input = Input.generate([seller.public_key])
    sell_input.fulfills = fulfills_link
    asset = {"id": asset_id, "data": {"buy_offer_id": buy_offer_id}}
    inputs, outputs = Transaction.validate_sell([sell_input], asset_id, buy_offer_id, {'seller_public_key': seller.public_key, 'buyer_public_key': buyer.public_key, 'sale_amount': 1000, 'sale_currency': 'USD', 'sale_timestamp': md['sale_timestamp'], 'requestCreationTimestamp': md['requestCreationTimestamp'], 'test_type': 'SELL'})
    tx = Transaction(Transaction.SELL, asset, inputs, outputs, md)
    tx.sign([seller.private_key])
    return tx


def create_request_return(asset_id: str, sell_id: str, requester):
    md = {
        'requester_public_key': requester.public_key,
        'return_reason': 'Item not as described',
        'return_request_timestamp': datetime.now().isoformat(),
        'return_policy_details': {
            'return_window_days': 30,
            'return_conditions': 'Item must be in original condition',
            'return_status': 'PENDING'
        },
        'requestCreationTimestamp': datetime.now().isoformat(),
        'test_type': 'REQUEST_RETURN',
    }
    req_input = Input.generate([requester.public_key])
    # Reference the SELL transaction output to satisfy schema (fulfills must be object)
    req_input.fulfills = TransactionLink.from_dict({'output_index': 0, 'transaction_id': sell_id})
    # Schema expects top-level sell_transaction_id in asset
    asset = {"id": asset_id, "sell_transaction_id": sell_id, "data": {}}
    inputs, outputs = Transaction.validate_request_return([req_input], asset_id, sell_id, md)
    tx = Transaction(Transaction.REQUEST_RETURN, asset, inputs, outputs, md)
    tx.sign([requester.private_key])
    return tx


def create_accept_return(asset_id: str, request_return_id: str, accepter):
    md = {
        'accepter_public_key': accepter.public_key,
        'return_acceptance_timestamp': datetime.now().isoformat(),
        'refund_details': {'refund_amount': 1000.0, 'refund_currency': 'USD', 'refund_method': 'Escrow return'},
        'return_processing_notes': 'Return accepted, processing refund',
        'requestCreationTimestamp': datetime.now().isoformat(),
        'test_type': 'SELLER_ACCEPT_RETURN',
    }
    acc_input = Input.generate([accepter.public_key])
    # Reference the REQUEST_RETURN transaction output
    acc_input.fulfills = TransactionLink.from_dict({'output_index': 0, 'transaction_id': request_return_id})
    # Schema expects top-level request_return_id
    asset = {"id": asset_id, "request_return_id": request_return_id, "data": {}}
    inputs, outputs = Transaction.validate_accept_return([acc_input], asset_id, request_return_id, md)
    tx = Transaction(Transaction.ACCEPT_RETURN, asset, inputs, outputs, md)
    tx.sign([accepter.private_key])
    return tx


def test_advertisement_conflict():
    print("\n🔬 ADVERTISEMENT conflict test")
    creator = generate_key_pair(); advertiser = generate_key_pair()
    asset_tx = create_asset(0, creator); r = send(asset_tx); print(f"CREATE status={r.status_code}")
    if r.status_code != 202: print(r.text); return
    asset_id = r.json().get('id'); ok = wait_committed(asset_id, 30); print(f"CREATE committed={ok}");
    adv1 = create_advertisement(asset_id, advertiser); r1 = send(adv1); print(f"ADV1 status={r1.status_code}")
    adv2 = create_advertisement(asset_id, advertiser); r2 = send(adv2); print(f"ADV2 status={r2.status_code}");
    if r2.status_code != 202: print(f"ADV2 error (expected conflict): {r2.text}")


def test_buy_offer_conflict():
    print("\n🔬 BUY_OFFER conflict test")
    creator = generate_key_pair(); advertiser = generate_key_pair(); buyer = generate_key_pair(); escrow = generate_key_pair()
    asset_tx = create_asset(1, creator); r = send(asset_tx); assert r.status_code == 202
    asset_id = r.json().get('id'); ok = wait_committed(asset_id, 30)
    adv = create_advertisement(asset_id, advertiser); r = send(adv); assert r.status_code == 202
    adv_id = r.json().get('id')
    # Ensure advertisement is visible to SHACL to avoid early schema failures
    ok = wait_committed(adv_id, 30)
    offer1 = create_buy_offer(asset_id, adv_id, buyer, escrow); r1 = send(offer1); print(f"OFFER1 status={r1.status_code}")
    offer2 = create_buy_offer(asset_id, adv_id, buyer, escrow); r2 = send(offer2); print(f"OFFER2 status={r2.status_code}")
    if r2.status_code != 202: print(f"OFFER2 error (expected conflict): {r2.text}")


def test_sell_conflict():
    print("\n🔬 SELL conflict test")
    creator = generate_key_pair(); advertiser = generate_key_pair(); buyer = generate_key_pair(); seller = generate_key_pair(); escrow = generate_key_pair()
    asset_tx = create_asset(2, creator); r = send(asset_tx); assert r.status_code == 202; asset_id = r.json().get('id'); ok = wait_committed(asset_id, 30)
    adv = create_advertisement(asset_id, advertiser); r = send(adv); assert r.status_code == 202; adv_id = r.json().get('id')
    ok = wait_committed(adv_id, 30)
    offer = create_buy_offer(asset_id, adv_id, buyer, escrow); r = send(offer); assert r.status_code == 202; buy_offer_id = r.json().get('id')
    # Ensure BUY_OFFER is on-chain so SELL avoids early failures
    ok = wait_committed(buy_offer_id, 30)
    sell1 = create_sell(asset_id, buy_offer_id, seller, buyer); r1 = send(sell1); print(f"SELL1 status={r1.status_code}")
    sell2 = create_sell(asset_id, buy_offer_id, seller, buyer); r2 = send(sell2); print(f"SELL2 status={r2.status_code}")
    if r2.status_code != 202: print(f"SELL2 error (expected conflict): {r2.text}")


def test_return_conflicts():
    print("\n🔬 REQUEST_RETURN and SELLER_ACCEPT_RETURN conflict tests")
    creator = generate_key_pair(); advertiser = generate_key_pair(); buyer = generate_key_pair(); seller = generate_key_pair(); escrow = generate_key_pair(); requester = buyer; accepter = seller
    asset_tx = create_asset(3, creator); r = send(asset_tx); assert r.status_code == 202; asset_id = r.json().get('id'); ok = wait_committed(asset_id, 30)
    adv = create_advertisement(asset_id, advertiser); r = send(adv); assert r.status_code == 202; adv_id = r.json().get('id')
    ok = wait_committed(adv_id, 30)
    offer = create_buy_offer(asset_id, adv_id, buyer, escrow); r = send(offer); assert r.status_code == 202; buy_offer_id = r.json().get('id')
    ok = wait_committed(buy_offer_id, 30)
    sell = create_sell(asset_id, buy_offer_id, seller, buyer); r = send(sell); assert r.status_code == 202; sell_id = r.json().get('id')
    ok = wait_committed(sell_id, 30)
    # REQUEST_RETURN conflict
    rr1 = create_request_return(asset_id, sell_id, requester); r1 = send(rr1); print(f"REQ_RET1 status={r1.status_code}")
    rr2 = create_request_return(asset_id, sell_id, requester); r2 = send(rr2); print(f"REQ_RET2 status={r2.status_code}")
    if r2.status_code != 202: print(f"REQ_RET2 error (expected conflict): {r2.text}")
    # ACCEPT_RETURN conflict
    rr_id = r1.json().get('id') if r1.status_code == 202 else None
    if rr_id:
        ok = wait_committed(rr_id, 30)
        ar1 = create_accept_return(asset_id, rr_id, accepter); a1 = send(ar1); print(f"ACC_RET1 status={a1.status_code}")
        ar2 = create_accept_return(asset_id, rr_id, accepter); a2 = send(ar2); print(f"ACC_RET2 status={a2.status_code}")
        if a2.status_code != 202: print(f"ACC_RET2 error (expected conflict): {a2.text}")


def main():
    test_advertisement_conflict()
    test_buy_offer_conflict()
    test_sell_conflict()
    test_return_conflicts()


if __name__ == "__main__":
    main()


