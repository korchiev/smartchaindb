# ADVERTISE and BUY Transaction Rules

## ADVERTISE Transaction

### Purpose
An ADVERTISE transaction allows an asset owner to create an advertisement for selling their asset, specifying price, conditions, and expiry time.

### Transaction Structure
```json
{
  "operation": "ADVERTISE",
  "asset": {
    "id": "<asset_id>",
    "data": {
      "asset_id": "<asset_id>",
      "price": "<price_in_tokens>",
      "currency": "<currency_type>",
      "conditions": "<additional_conditions>"
    }
  },
  "metadata": {
    "expiry_time": "<ISO_8601_timestamp>",
    "advertisement_type": "SALE",
    "description": "<optional_description>"
  },
  "inputs": [
    {
      "fulfills": {
        "transaction_id": "<previous_tx_id>",
        "output_index": 0
      },
      "owners_before": ["<owner_public_key>"],
      "fulfillment": "<cryptographic_fulfillment>"
    }
  ],
  "outputs": [
    {
      "amount": "1",
      "condition": {
        "details": {
          "type": "ed25519-sha-256",
          "public_key": "<owner_public_key>"
        },
        "uri": "<condition_uri>"
      },
      "public_keys": ["<owner_public_key>"]
    }
  ]
}
```

### Validation Rules

#### 1. Ownership Validation
- **Rule**: The advertiser must own the asset being advertised
- **Support Data**: Current asset ownership from blockchain
- **SHACL Pattern**:
```turtle
:AdvertiseOwnershipRule a sh:NodeShape ;
    sh:targetClass :AdvertiseTransaction ;
    sh:sparql [
        sh:select """
            SELECT ?tx ?assetId ?advertiser ?currentOwner
            WHERE {
                ?tx a :AdvertiseTransaction ;
                    :assetId ?assetId ;
                    :advertiser ?advertiser .
                ?assetId :currentOwner ?currentOwner .
                FILTER (?advertiser != ?currentOwner)
            }
        """ ;
        sh:message "Advertiser must own the asset being advertised" ;
    ] .
```

#### 2. Uniqueness Validation
- **Rule**: Only one open advertisement per asset at a time
- **Support Data**: All existing open advertisements for the asset
- **SHACL Pattern**:
```turtle
:AdvertiseUniquenessRule a sh:NodeShape ;
    sh:targetClass :AdvertiseTransaction ;
    sh:sparql [
        sh:select """
            SELECT ?tx1 ?tx2 ?assetId
            WHERE {
                ?tx1 a :AdvertiseTransaction ;
                     :assetId ?assetId ;
                     :status :OPEN .
                ?tx2 a :AdvertiseTransaction ;
                     :assetId ?assetId ;
                     :status :OPEN .
                FILTER (?tx1 != ?tx2)
            }
        """ ;
        sh:message "Only one open advertisement per asset allowed" ;
    ] .
```

#### 3. Expiry Validation
- **Rule**: Advertisement must not be expired
- **Support Data**: Current timestamp
- **SHACL Pattern**:
```turtle
:AdvertiseExpiryRule a sh:NodeShape ;
    sh:targetClass :AdvertiseTransaction ;
    sh:property [
        sh:path :expiryTime ;
        sh:datatype xsd:dateTime ;
        sh:minInclusive "now"^^xsd:dateTime ;
        sh:message "Advertisement must not be expired" ;
    ] .
```

#### 4. Price Validation
- **Rule**: Price must be positive and valid
- **Support Data**: None (transaction data only)
- **SHACL Pattern**:
```turtle
:AdvertisePriceRule a sh:NodeShape ;
    sh:targetClass :AdvertiseTransaction ;
    sh:property [
        sh:path :price ;
        sh:datatype xsd:decimal ;
        sh:minInclusive 0 ;
        sh:message "Price must be positive" ;
    ] .
```

### Support Data Requirements
1. **Asset Ownership**: Query for current owner of the asset
2. **Open Advertisements**: Query for existing open advertisements for the asset
3. **Current Time**: System timestamp for expiry validation

### Invalidating Patterns
- **Ownership Change**: Asset transferred to different owner
- **New Open Advertisement**: Another advertisement created for same asset
- **Time Expiry**: Advertisement expiry time reached
- **Advertisement Closure**: Advertisement manually closed or locked

---

## BUY Transaction

### Purpose
A BUY transaction allows a buyer to purchase an advertised asset by providing payment and fulfilling the advertisement conditions.

### Transaction Structure
```json
{
  "operation": "BUY",
  "asset": {
    "id": "<advertisement_id>",
    "data": {
      "advertisement_id": "<advertisement_id>",
      "buyer_public_key": "<buyer_public_key>",
      "payment_amount": "<payment_amount>",
      "payment_currency": "<currency_type>"
    }
  },
  "metadata": {
    "purchase_timestamp": "<ISO_8601_timestamp>",
    "buyer_contact": "<optional_contact_info>"
  },
  "inputs": [
    {
      "fulfills": {
        "transaction_id": "<buyer_asset_tx_id>",
        "output_index": 0
      },
      "owners_before": ["<buyer_public_key>"],
      "fulfillment": "<cryptographic_fulfillment>"
    }
  ],
  "outputs": [
    {
      "amount": "<payment_amount>",
      "condition": {
        "details": {
          "type": "ed25519-sha-256",
          "public_key": "<seller_public_key>"
        },
        "uri": "<condition_uri>"
      },
      "public_keys": ["<seller_public_key>"]
    }
  ]
}
```

### Validation Rules

#### 1. Advertisement Existence
- **Rule**: The advertisement must exist and be open
- **Support Data**: Advertisement transaction and its current status
- **SHACL Pattern**:
```turtle
:BuyAdvertisementRule a sh:NodeShape ;
    sh:targetClass :BuyTransaction ;
    sh:sparql [
        sh:select """
            SELECT ?tx ?adId ?adStatus
            WHERE {
                ?tx a :BuyTransaction ;
                    :advertisementId ?adId .
                ?adId :status ?adStatus .
                FILTER (?adStatus != :OPEN)
            }
        """ ;
        sh:message "Advertisement must exist and be open" ;
    ] .
```

#### 2. Advertisement Not Expired
- **Rule**: Advertisement must not be expired
- **Support Data**: Advertisement expiry time and current timestamp
- **SHACL Pattern**:
```turtle
:BuyExpiryRule a sh:NodeShape ;
    sh:targetClass :BuyTransaction ;
    sh:sparql [
        sh:select """
            SELECT ?tx ?adId ?expiryTime
            WHERE {
                ?tx a :BuyTransaction ;
                    :advertisementId ?adId .
                ?adId :expiryTime ?expiryTime .
                FILTER (?expiryTime < "now"^^xsd:dateTime)
            }
        """ ;
        sh:message "Advertisement must not be expired" ;
    ] .
```

#### 3. Payment Amount Validation
- **Rule**: Payment amount must match advertisement price
- **Support Data**: Advertisement price from the ADVERTISE transaction
- **SHACL Pattern**:
```turtle
:BuyPaymentRule a sh:NodeShape ;
    sh:targetClass :BuyTransaction ;
    sh:sparql [
        sh:select """
            SELECT ?tx ?adId ?paymentAmount ?adPrice
            WHERE {
                ?tx a :BuyTransaction ;
                    :advertisementId ?adId ;
                    :paymentAmount ?paymentAmount .
                ?adId :price ?adPrice .
                FILTER (?paymentAmount != ?adPrice)
            }
        """ ;
        sh:message "Payment amount must match advertisement price" ;
    ] .
```

#### 4. Buyer Sufficient Funds
- **Rule**: Buyer must have sufficient funds for payment
- **Support Data**: Buyer's current balance
- **SHACL Pattern**:
```turtle
:BuyFundsRule a sh:NodeShape ;
    sh:targetClass :BuyTransaction ;
    sh:sparql [
        sh:select """
            SELECT ?tx ?buyer ?paymentAmount ?balance
            WHERE {
                ?tx a :BuyTransaction ;
                    :buyer ?buyer ;
                    :paymentAmount ?paymentAmount .
                ?buyer :balance ?balance .
                FILTER (?balance < ?paymentAmount)
            }
        """ ;
        sh:message "Buyer must have sufficient funds" ;
    ] .
```

#### 5. Advertisement Still Available
- **Rule**: Advertisement must not be locked or closed
- **Support Data**: Current advertisement status
- **SHACL Pattern**:
```turtle
:BuyAvailabilityRule a sh:NodeShape ;
    sh:targetClass :BuyTransaction ;
    sh:sparql [
        sh:select """
            SELECT ?tx ?adId ?adStatus
            WHERE {
                ?tx a :BuyTransaction ;
                    :advertisementId ?adId .
                ?adId :status ?adStatus .
                FILTER (?adStatus IN (:LOCKED, :CLOSED, :CANCELLED))
            }
        """ ;
        sh:message "Advertisement must still be available for purchase" ;
    ] .
```

### Support Data Requirements
1. **Advertisement Transaction**: The original ADVERTISE transaction
2. **Advertisement Status**: Current status (OPEN, LOCKED, CLOSED, CANCELLED)
3. **Advertisement Expiry**: Expiry time from advertisement
4. **Advertisement Price**: Price from advertisement
5. **Buyer Balance**: Current balance of the buyer
6. **Asset Ownership**: Current owner of the advertised asset

### Invalidating Patterns
- **Advertisement Closure**: Advertisement closed, locked, or cancelled
- **Advertisement Expiry**: Advertisement expiry time reached
- **Ownership Change**: Asset ownership changed (advertisement invalidated)
- **Price Change**: Advertisement price modified
- **Insufficient Funds**: Buyer's balance insufficient

---

## Cross-Transaction Constraints

### 1. No Double-Spending
- **Rule**: Same asset cannot be sold twice
- **Scope**: All transactions in a block
- **SHACL Pattern**:
```turtle
:NoDoubleSellingRule a sh:NodeShape ;
    sh:targetClass :Block ;
    sh:sparql [
        sh:select """
            SELECT ?tx1 ?tx2 ?assetId
            WHERE {
                ?tx1 a :BuyTransaction ;
                     :advertisementId ?ad1 .
                ?tx2 a :BuyTransaction ;
                     :advertisementId ?ad2 .
                ?ad1 :assetId ?assetId .
                ?ad2 :assetId ?assetId .
                FILTER (?tx1 != ?tx2)
            }
        """ ;
        sh:message "Same asset cannot be sold twice" ;
    ] .
```

### 2. Advertisement Consistency
- **Rule**: All BUY transactions must reference valid advertisements
- **Scope**: All transactions in a block
- **SHACL Pattern**:
```turtle
:AdvertisementConsistencyRule a sh:NodeShape ;
    sh:targetClass :Block ;
    sh:sparql [
        sh:select """
            SELECT ?tx ?adId
            WHERE {
                ?tx a :BuyTransaction ;
                    :advertisementId ?adId .
                FILTER NOT EXISTS {
                    ?adId a :AdvertiseTransaction
                }
            }
        """ ;
        sh:message "All BUY transactions must reference valid advertisements" ;
    ] .
```

## Implementation Notes

### Database Queries Required
1. **Asset Ownership**: `SELECT current_owner FROM assets WHERE asset_id = ?`
2. **Open Advertisements**: `SELECT * FROM advertisements WHERE asset_id = ? AND status = 'OPEN'`
3. **Advertisement Details**: `SELECT * FROM advertisements WHERE advertisement_id = ?`
4. **Buyer Balance**: `SELECT balance FROM accounts WHERE public_key = ?`

### Caching Strategy
- Cache asset ownership (invalidate on transfer)
- Cache open advertisements (invalidate on new/close)
- Cache advertisement details (invalidate on update)
- Cache account balances (invalidate on transaction)

### Event-Driven Invalidation
- **Asset Transfer Events**: Invalidate all related advertisements
- **Advertisement Events**: Invalidate related BUY transactions
- **Time Events**: Invalidate expired advertisements
- **Balance Events**: Invalidate pending BUY transactions
