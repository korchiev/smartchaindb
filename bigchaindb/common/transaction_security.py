"""Authentication and input security shared by every validation treatment.

Domain validation may be declarative or imperative. Neither may bypass this
boundary, and a cached domain verdict never replaces authentication.
"""
from bigchaindb.common.exceptions import (
    AssetIdMismatch, DoubleSpend, InputDoesNotExist, InvalidSignature, ValidationError,
)


ACTOR_FIELDS = {
    "ADVERTISEMENT": "advertiser_public_key",
    "UPDATE_ADV": "updater_public_key",
    "BUY_OFFER": "buyer_public_key",
    "SELL": "seller_public_key",
    "REQUEST_RETURN": "requester_public_key",
    "SELLER_ACCEPT_RETURN": "seller_public_key",
}
ANNOUNCEMENTS = frozenset({
    "CREATE", "ADVERTISEMENT", "UPDATE_ADV", "REQUEST_RETURN", "SELLER_ACCEPT_RETURN",
})


def validate_ledger_authentication(tx, bigchain, current_transactions=()):
    # Import lazily: models imports this helper while transaction types load.
    from bigchaindb.common.transaction import Output, Transaction

    body = tx.to_dict()
    Transaction.validate_id(body)
    if not tx.inputs:
        raise InvalidSignature("A transaction must have a signed input")

    unsigned = Transaction._remove_signatures(body)
    unsigned["id"] = None
    message = Transaction._to_str(unsigned)
    prior = {item.id: item for item in current_transactions}
    signers = set()
    links = set()
    source_assets = []
    source_outputs = []

    def flatten(keys):
        for key in keys:
            if isinstance(key, list):
                yield from flatten(key)
            elif isinstance(key, str):
                yield key
            else:
                raise InvalidSignature("Invalid input owner key")

    for input_ in tx.inputs:
        owners = input_.owners_before
        if not owners:
            raise InvalidSignature("Input owner keys are required")
        # Bind the human-readable owner list to the actual signed condition.
        expected = Output.generate(owners, 1).fulfillment.condition_uri
        if input_.fulfillment.condition_uri != expected:
            raise InvalidSignature("Input owners do not match the signing condition")

        # Deserialization represents a null link as a false-y TransactionLink.
        link = input_.fulfills if input_.fulfills else None
        if tx.operation in ANNOUNCEMENTS and link is not None:
            raise ValidationError("Announcement inputs must not spend an output")
        if tx.operation in ("SELL", "TRANSFER") and link is None:
            raise InputDoesNotExist("Spending transaction must reference an output")
        if link is not None:
            key = (link.txid, link.output)
            if key in links:
                raise DoubleSpend("Transaction spends an input twice")
            links.add(key)
            source = prior.get(link.txid) or bigchain.get_transaction(link.txid)
            if source is None:
                raise InputDoesNotExist("Input transaction does not exist")
            index = link.output
            if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < len(source.outputs):
                raise InputDoesNotExist("Input output index does not exist")
            if bigchain.get_spent(link.txid, index, list(current_transactions)):
                raise DoubleSpend("Input was already spent")
            if source.outputs[index].fulfillment.condition_uri != expected:
                raise InvalidSignature("Input does not fulfill the referenced output")
            source_assets.append(source)
            source_outputs.append(source.outputs[index])

        # _input_valid hashes exactly the message used by sign(), including
        # the link when present. Explicit condition comparison above handles
        # ownership for announcements as well as spends.
        if not tx._input_valid(input_, "TRANSFER", message, expected):
            raise InvalidSignature("Transaction signature is invalid")
        signers.update(flatten(owners))

    actor_field = ACTOR_FIELDS.get(tx.operation)
    if actor_field:
        actor = (tx.metadata or {}).get(actor_field)
        if not actor or actor not in signers:
            raise InvalidSignature("{} must be an authenticated signer".format(actor_field))
    if source_assets and tx.operation in ("SELL", "TRANSFER"):
        asset_id = (tx.asset or {}).get("id")
        if Transaction.get_asset_id(source_assets) != asset_id:
            raise AssetIdMismatch("Input asset does not match the transaction asset")

    # Prevent a payload's public-key labels from disagreeing with the actual
    # output conditions. Synthetic marketplace payment outputs are not a
    # substitute for a funded payment protocol (outside this boundary).
    for output in tx.outputs:
        expected = Output.generate(output.public_keys, output.amount).fulfillment.condition_uri
        if expected != output.fulfillment.condition_uri:
            raise InvalidSignature("Output keys do not match its condition")
    if tx.operation == "TRANSFER" and sum(o.amount for o in tx.outputs) != sum(o.amount for o in source_outputs):
        raise ValidationError("Transferred input and output amounts must match")
    if tx.operation == "SELL":
        asset = tx.asset or {}
        offer_id = (asset.get("data") or {}).get("buy_offer_id") or asset.get("buy_offer_id")
        offer = prior.get(offer_id) or bigchain.get_transaction(offer_id)
        if offer is None or offer.operation != "BUY_OFFER":
            raise ValidationError("Sale must reference an existing buy offer")
        buyer = (offer.metadata or {}).get("buyer_public_key")
        if (offer.asset or {}).get("id") != asset.get("id") or (tx.metadata or {}).get("buyer_public_key") != buyer:
            raise ValidationError("Sale asset and buyer must match the offer")
        if (len(tx.outputs) != 2 or tx.outputs[0].public_keys != [buyer]
                or tx.outputs[1].public_keys != [(tx.metadata or {}).get("seller_public_key")]
                or tx.outputs[0].amount != sum(o.amount for o in source_outputs)
                or str(tx.outputs[1].amount) != str((tx.metadata or {}).get("sale_amount"))):
            raise ValidationError("Sale outputs must transfer the asset and declared payment to the intended recipients")
