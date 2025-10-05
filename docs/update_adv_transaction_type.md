## UPDATE_ADV Transaction

Purpose: Update an existing ADVERTISEMENT's mutable fields (e.g., status, price, expiry) by the advertiser.

### Operation
- operation: `UPDATE_ADV`
- version: `2.0`

### Structure
Asset:
```json
{
  "asset": {
    "data": {
      "id": "<advertisement_tx_id>"
    }
  }
}
```

Metadata (examples):
```json
{
  "updater_public_key": "<base58 pubkey>",
  "status": "LOCKED",
  "price": "1000",
  "expiry": "2025-12-31T23:59:59Z"
}
```

### Validation Rules
- Asset references target advertisement via `asset.data.id` (64-hex).
- At least one input (advertiser signature) is required.
- No outputs.
- Only the original advertiser may update (owner check against ADVERTISEMENT metadata `seller_public_key`).
- Status transitions allowed: `OPEN -> LOCKED -> CLOSED`. No reversions.
- If provided, `expiry` must be in the future. `price` must be a positive integer string.

### Driver Usage (Java)
```java
MetaData meta = new MetaData();
meta.setMetaData("status", "LOCKED");
// optional
// meta.setMetaData("price", "1000");
// meta.setMetaData("expiry", "2025-12-31T23:59:59Z");

Transactions.updateAdv(driver, advertisementId, meta, advertiserKeys);
```

### Notes
- This transaction does not move UTXOs; it updates state validated via SHACL and server-side checks.

