"""Committed state plus the ordered, already accepted prefix of a block."""


def field_value(tx, path):
    value = tx.to_dict() if hasattr(tx, "to_dict") else tx
    for key in path.split("."):
        value = value.get(key) if isinstance(value, dict) else None
    return value


class LedgerStateView:
    def __init__(self, base, pending=()):
        self.base = base
        self.pending = list(pending)

    def __getattr__(self, name):
        return getattr(self.base, name)

    def get_transaction(self, tx_id):
        for tx in reversed(self.pending):
            if tx.id == tx_id:
                return tx
        return self.base.get_transaction(tx_id)

    def get_effective_advertisement_status(self, adv_id):
        adv = self.get_transaction(adv_id)
        if adv is None:
            return None
        status = self.base.get_effective_advertisement_status(adv_id)
        if status is None:
            status = (adv.metadata or {}).get("status")
        for tx in self.pending:
            if tx.operation == "UPDATE_ADV" and adv_id in (
                field_value(tx, "asset.id"), field_value(tx, "asset.data.id")
            ):
                status = (tx.metadata or {}).get("status") or status
        return status

    def referencing_transactions(self, operation, fields, value):
        fields = (fields,) if isinstance(fields, str) else tuple(fields)
        query = {"operation": operation, "$or": [{f: value} for f in fields]}
        conn = self.base.connection
        docs = conn.run(conn.collection("transactions").find(query, {"id": 1, "_id": 0}))
        ids = [doc["id"] for doc in docs]
        ids.extend(tx.id for tx in self.pending if tx.operation == operation
                   and any(field_value(tx, f) == value for f in fields))
        return [self.get_transaction(tx_id) for tx_id in dict.fromkeys(ids)]

    def get_open_advertisements_by_asset(self, asset_id):
        return [ad for ad in self.referencing_transactions("ADVERTISEMENT", "asset.id", asset_id)
                if self.get_effective_advertisement_status(ad.id) in ("OPEN", "LOCKED")]
