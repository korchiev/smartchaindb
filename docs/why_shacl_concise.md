# Why SHACL vs MongoDB: A Complex Example

## The Challenge: Multi-Asset Advertisement Validation

Consider a complex validation scenario: **validating multiple ADVERTISE transactions for related assets within the same block**, where:

- Each asset can only have one open advertisement
- Related assets (same category) cannot have conflicting price ranges
- Advertisements must respect global market constraints
- Cross-transaction dependencies must be validated together

## MongoDB Approach: The Imperative Nightmare

```javascript
// MongoDB: Scattered validation logic across multiple functions
async function validateAdvertiseBatch(transactions) {
    const results = [];
    
    for (const tx of transactions) {
        // Individual validation - no composition
        const assetId = tx.asset.data.asset_id;
        const category = tx.asset.data.category;
        const price = parseFloat(tx.asset.data.price);
        
        // Check 1: Asset ownership
        const owner = await db.collection('transactions')
            .findOne({id: assetId, 'outputs.public_keys': tx.advertiser});
        if (!owner) {
            results.push({valid: false, error: 'Not owner'});
            continue;
        }
        
        // Check 2: No duplicate advertisements
        const existing = await db.collection('transactions')
            .find({operation: 'ADVERTISE', 'asset.data.asset_id': assetId, 'metadata.status': 'OPEN'});
        if (existing.length > 0) {
            results.push({valid: false, error: 'Duplicate advertisement'});
            continue;
        }
        
        // Check 3: Category price consistency (requires cross-transaction check)
        const categoryAds = await db.collection('transactions')
            .find({operation: 'ADVERTISE', 'asset.data.category': category, 'metadata.status': 'OPEN'});
        for (const ad of categoryAds) {
            const adPrice = parseFloat(ad.asset.data.price);
            if (Math.abs(price - adPrice) > adPrice * 0.5) { // 50% price difference limit
                results.push({valid: false, error: 'Price conflict with category'});
                continue;
            }
        }
        
        // Check 4: Global market constraints
        const globalAds = await db.collection('transactions')
            .find({operation: 'ADVERTISE', 'metadata.status': 'OPEN'});
        const totalValue = globalAds.reduce((sum, ad) => sum + parseFloat(ad.asset.data.price), 0);
        if (totalValue + price > 1000000) { // $1M global limit
            results.push({valid: false, error: 'Exceeds global market limit'});
            continue;
        }
        
        results.push({valid: true});
    }
    
    return results;
}
```

**Problems:**
- **No compositionality**: Each check is independent, hard to combine
- **No batching**: Each transaction validated separately
- **Tight coupling**: Validation logic embedded in application code
- **Code duplication**: Similar patterns repeated across transaction types
- **Hard to maintain**: Changes require code modifications

## SHACL Approach: The Declarative Solution

```turtle
# SHACL: Composable, declarative rules
@prefix sc: <http://smartchaindb.org/ns#> .
@prefix sh: <http://www.w3.org/ns/shacl#> .

# Base rule: Asset ownership
sc:OwnershipRule a sh:NodeShape ;
    sh:targetClass sc:AdvertiseTransaction ;
    sh:sparql [
        sh:select """
            SELECT ?tx ?assetId ?advertiser ?currentOwner
            WHERE {
                ?tx a sc:AdvertiseTransaction ;
                    sc:assetId ?assetId ;
                    sc:advertiser ?advertiser .
                ?assetId sc:currentOwner ?currentOwner .
                FILTER (?advertiser != ?currentOwner)
            }
        """ ;
        sh:message "Advertiser must own the asset" ;
    ] .

# Base rule: Uniqueness per asset
sc:UniquenessRule a sh:NodeShape ;
    sh:targetClass sc:AdvertiseTransaction ;
    sh:sparql [
        sh:select """
            SELECT ?tx1 ?tx2 ?assetId
            WHERE {
                ?tx1 a sc:AdvertiseTransaction ;
                     sc:assetId ?assetId ;
                     sc:status sc:OPEN .
                ?tx2 a sc:AdvertiseTransaction ;
                     sc:assetId ?assetId ;
                     sc:status sc:OPEN .
                FILTER (?tx1 != ?tx2)
            }
        """ ;
        sh:message "Only one advertisement per asset" ;
    ] .

# Base rule: Category price consistency
sc:CategoryPriceRule a sh:NodeShape ;
    sh:targetClass sc:AdvertiseTransaction ;
    sh:sparql [
        sh:select """
            SELECT ?tx1 ?tx2 ?category ?price1 ?price2
            WHERE {
                ?tx1 a sc:AdvertiseTransaction ;
                     sc:category ?category ;
                     sc:price ?price1 ;
                     sc:status sc:OPEN .
                ?tx2 a sc:AdvertiseTransaction ;
                     sc:category ?category ;
                     sc:price ?price2 ;
                     sc:status sc:OPEN .
                FILTER (?tx1 != ?tx2 && ABS(?price1 - ?price2) > ?price2 * 0.5)
            }
        """ ;
        sh:message "Price conflict within category" ;
    ] .

# Base rule: Global market limit
sc:GlobalLimitRule a sh:NodeShape ;
    sh:targetClass sc:AdvertiseTransaction ;
    sh:sparql [
        sh:select """
            SELECT ?tx ?price ?totalValue
            WHERE {
                ?tx a sc:AdvertiseTransaction ;
                    sc:price ?price .
                {
                    SELECT (SUM(?p) as ?totalValue)
                    WHERE {
                        ?otherTx a sc:AdvertiseTransaction ;
                                 sc:price ?p ;
                                 sc:status sc:OPEN .
                    }
                }
                FILTER (?totalValue + ?price > 1000000)
            }
        """ ;
        sh:message "Exceeds global market limit" ;
    ] .

# COMPOSITION: Combine all rules naturally
sc:AdvertiseValidation a sh:NodeShape ;
    sh:targetClass sc:AdvertiseTransaction ;
    sh:and (sc:OwnershipRule, sc:UniquenessRule, 
           sc:CategoryPriceRule, sc:GlobalLimitRule) .

# BATCH VALIDATION: Validate multiple transactions together
sc:BatchValidation a sh:NodeShape ;
    sh:targetClass sc:Block ;
    sh:sparql [
        sh:select """
            SELECT ?block ?tx1 ?tx2 ?conflict
            WHERE {
                ?block a sc:Block .
                ?tx1 sc:inBlock ?block ;
                     a sc:AdvertiseTransaction .
                ?tx2 sc:inBlock ?block ;
                     a sc:AdvertiseTransaction .
                # Cross-transaction constraints
                FILTER (?tx1 != ?tx2 && 
                        ?tx1/sc:assetId = ?tx2/sc:assetId)
            }
        """ ;
        sh:message "Block contains conflicting advertisements" ;
    ] .
```

**Benefits:**
- **Compositionality**: Rules combine naturally with `sh:and`
- **Reusability**: Base rules can be reused across transaction types
- **Batching**: Single SPARQL query validates all transactions together
- **Declarative**: Rules describe what should be true, not how to check

## Middleware Integration: The Drop-in Solution

```python
# SHACL: Non-invasive middleware
class SHACLValidationMiddleware:
    def __init__(self, bigchaindb_instance):
        self.bigchaindb = bigchaindb_instance
        self.shacl_validator = SHACLValidator()
    
    def validate_batch(self, transactions, phase="block_proposal"):
        # Convert all transactions to RDF in one pass
        rdf_graph = self._transactions_to_rdf(transactions, phase)
        
        # Single SHACL validation for entire batch
        conforms, report, _ = validate(rdf_graph, self.shacl_rules)
        
        return self._parse_results(report, transactions)

# Usage: Drop-in replacement
middleware = SHACLValidationMiddleware(bigchaindb)
results = middleware.validate_batch(advertise_transactions, "block_proposal")
```

**MongoDB**: Requires rewriting validation logic for each new constraint
**SHACL**: Add new rules to the RDF graph, no code changes needed

## The Key Differences

| Aspect | MongoDB | SHACL |
|--------|---------|-------|
| **Composition** | Application logic | Built-in operators (`sh:and`, `sh:or`) |
| **Batching** | Loop through transactions | Single graph traversal |
| **Maintenance** | Code modifications | Rule data updates |
| **Reusability** | Copy-paste patterns | Reusable rule components |
| **Middleware** | Tight coupling | Drop-in validation layer |

## The Bottom Line

**MongoDB queries** are like writing assembly code - direct, fast, but verbose and hard to maintain.

**SHACL rules** are like writing in a high-level language - more overhead, but composable, maintainable, and expressive.

For complex validation scenarios with multiple constraints and cross-transaction dependencies, SHACL's compositional approach and batch validation potential provide genuine architectural benefits that justify the performance cost.

