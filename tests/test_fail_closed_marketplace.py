"""Fail-closed marketplace rules: stolen advertisement and offers after CLOSE.

Direct previously checked owner on ADVERTISEMENT but both engines ignored
later UPDATE_ADV status (original metadata stays OPEN). SHACL now matches
Direct on owner and both engines overlay UPDATE_ADV status.
"""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

from bigchaindb.common.shacl_delta import collect_dep_state, compute_dep_state_hash
from bigchaindb.common.transaction import Transaction


@contextmanager
def assert_raises(exc_type, match=None):
    try:
        yield
    except exc_type as exc:
        if match and match not in str(exc):
            raise AssertionError("expected %r in %r" % (match, str(exc)))
        return
    raise AssertionError("did not raise %s" % exc_type)


def _open_ad(advertiser="seller"):
    ad = Mock()
    ad.operation = "ADVERTISEMENT"
    ad.id = "ad1"
    ad.metadata = {"status": "OPEN", "advertiser_public_key": advertiser}
    return ad


def _offer_tx(advertiser="seller", buyer="buyer"):
    inp = Mock()
    inp.fulfills = None
    expiry = (datetime.now(timezone.utc) + timedelta(days=1)).strftime(
        "%Y-%m-%dT%H:%M:%S+00:00"
    )
    return Transaction(
        operation=Transaction.BUY_OFFER,
        asset={"id": "a" * 64, "data": {"id": "a" * 64, "advertisement_id": "ad1"}},
        inputs=[inp],
        metadata={
            "buyer_public_key": buyer,
            "escrow_public_key": "escrow",
            "offer_expiry": expiry,
        },
    )


def test_direct_buy_offer_rejects_close_via_update_overlay():
    ad = _open_ad()
    bigchain = Mock()
    bigchain.get_transaction.return_value = ad
    bigchain.get_effective_advertisement_status.return_value = "CLOSED"
    with assert_raises(ValueError, "is not OPEN"):
        _offer_tx().validate_buy_offer_inputs(bigchain)


def test_direct_buy_offer_still_accepts_open_overlay():
    ad = _open_ad()
    bigchain = Mock()
    bigchain.get_transaction.return_value = ad
    bigchain.get_effective_advertisement_status.return_value = "OPEN"
    # Fails later on missing escrow output — must not fail the OPEN check.
    with assert_raises(ValueError, "exactly one output"):
        _offer_tx().validate_buy_offer_inputs(bigchain)


def test_direct_advertisement_rejects_non_owner():
    owner = "owner_key"
    thief = "thief_key"
    create_tx = Mock()
    create_tx.operation = Transaction.CREATE
    create_tx.get_asset_id.return_value = "c" * 64
    create_tx.outputs = [Mock(public_keys=[owner])]

    bigchain = Mock()
    bigchain.get_transaction.return_value = create_tx
    bigchain.get_open_advertisements_by_asset.return_value = []

    inp = Mock()
    inp.fulfills = None
    tx = Transaction(
        operation=Transaction.ADVERTISEMENT,
        asset={"id": "c" * 64},
        inputs=[inp],
        metadata={"status": "OPEN", "advertiser_public_key": thief},
    )
    tx.inputs_valid = lambda *args, **kwargs: True
    with assert_raises(ValueError, "original owner"):
        tx.validate_advertisement_inputs(bigchain)


def test_delta_hash_tracks_effective_status_not_only_original_metadata():
    open_adv = {
        "id": "adv1",
        "operation": "ADVERTISEMENT",
        "asset": {"id": "asset1"},
        "metadata": {"status": "OPEN", "price": "100"},
    }
    offer = {
        "id": "offer1",
        "operation": "BUY_OFFER",
        "asset": {"data": {"advertisement_id": "adv1"}},
    }

    class Store(object):
        def __init__(self, status):
            self.status = status

        def get_transaction(self, _id):
            return open_adv

        def get_effective_advertisement_status(self, _id):
            return self.status

    parts_closed = collect_dep_state(Store("CLOSED"), offer)
    assert parts_closed[0]["effective_status"] == "CLOSED"
    assert parts_closed[0]["metadata"]["status"] == "OPEN"
    assert compute_dep_state_hash(Store("OPEN"), offer) != compute_dep_state_hash(
        Store("CLOSED"), offer
    )
