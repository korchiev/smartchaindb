# Three-Phase Validation Lifecycle

## Overview

SmartChainDB implements a three-phase validation lifecycle to ensure transaction integrity across different stages of processing. Each phase serves a specific purpose and requires re-validation due to the dynamic nature of distributed ledger systems.

## Lifecycle Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        THREE-PHASE VALIDATION LIFECYCLE                     │
└─────────────────────────────────────────────────────────────────────────────┘

Phase 1: PRE-COMMIT VALIDATION
┌─────────────────────────────────────────────────────────────────────────────┐
│  Transaction Received → Schema Validation → Business Rules Validation      │
│                                                                             │
│  • Validate transaction structure and signatures                            │
│  • Check business rules against current blockchain state                   │
│  • Validate ownership, amounts, uniqueness, expiry, etc.                   │
│  • Result: Transaction accepted into mempool                                │
└─────────────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
Phase 2: BLOCK PROPOSAL VALIDATION  
┌─────────────────────────────────────────────────────────────────────────────┐
│  Block Assembly → Re-validate All Transactions → Cross-Tx Constraints       │
│                                                                             │
│  • Re-check all transactions in proposed block                              │
│  • Validate cross-transaction constraints (e.g., no double-spending)        │
│  • Ensure no conflicting operations within the block                        │
│  • Result: Block proposed to network                                        │
└─────────────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
Phase 3: COMMIT VALIDATION
┌─────────────────────────────────────────────────────────────────────────────┐
│  Block Finalization → Final State Check → Database Update                   │
│                                                                             │
│  • Final validation against committed state                                 │
│  • Check for any state changes since Phase 2                                │
│  • Ensure transaction still valid in final context                          │
│  • Result: Transaction permanently committed                                │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                           INVALIDATION EVENTS                               │
│                                                                             │
│  • Ownership changes (asset transferred)                                    │
│  • New conflicting transactions (duplicate advertisements)                  │
│  • Time-based expirations (advertisement expiry)                            │
│  • State transitions (advertisement closed/locked)                          |
│  • etc...                                                                   │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Why Re-validation is Required

### 1. **Concurrent Transaction Processing**
- Multiple transactions may be processed simultaneously
- State changes from one transaction can invalidate others
- Re-validation ensures consistency across the entire block

### 2. **Network Consensus Delays**
- Time gap between Phase 1 and Phase 3 can be significant
- Other nodes may have committed conflicting transactions
- Final validation prevents double-spending and conflicts

### 3. **Dynamic State Dependencies**
- Transactions depend on current blockchain state
- State can change between validation phases
- Re-validation ensures transactions remain valid in final context

## Phase-Specific Validation Requirements

### Phase 1: Pre-Commit (Individual Transaction)
**Purpose**: Validate transaction in isolation
**Data Requirements**:
- Transaction structure and signatures
- Current asset ownership
- Basic business rule compliance
- No conflicting operations

**SHACL Rules**:
```turtle
:PreCommitValidation a sh:NodeShape ;
    sh:targetClass :Transaction ;
    sh:property [
        sh:path :signature ;
        sh:minCount 1 ;
        sh:message "Transaction must be signed" ;
    ] ;
    sh:property [
        sh:path :assetOwner ;
        sh:hasValue :currentOwner ;
        sh:message "Asset must be owned by transaction creator" ;
    ] .
```

### Phase 2: Block Proposal (Cross-Transaction)
**Purpose**: Validate transaction within block context
**Data Requirements**:
- All transactions in the block
- Cross-transaction constraints
- No double-spending within block
- No conflicting operations

**SHACL Rules**:
```turtle
:BlockValidation a sh:NodeShape ;
    sh:targetClass :Block ;
    sh:sparql [
        sh:select """
            SELECT ?tx1 ?tx2 ?assetId
            WHERE {
                ?tx1 a :AdvertiseTransaction ;
                     :assetId ?assetId .
                ?tx2 a :AdvertiseTransaction ;
                     :assetId ?assetId .
                FILTER (?tx1 != ?tx2)
            }
        """ ;
        sh:message "Only one advertisement per asset per block" ;
    ] .
```

### Phase 3: Commit (Final State)
**Purpose**: Final validation against committed state
**Data Requirements**:
- Complete blockchain state
- All committed transactions
- Final consistency check
- State change verification

**SHACL Rules**:
```turtle
:CommitValidation a sh:NodeShape ;
    sh:targetClass :CommittedTransaction ;
    sh:sparql [
        sh:select """
            SELECT ?tx ?assetId ?currentOwner
            WHERE {
                ?tx a :AdvertiseTransaction ;
                    :assetId ?assetId ;
                    :assetOwner ?advertiser .
                ?assetId :currentOwner ?currentOwner .
                FILTER (?advertiser != ?currentOwner)
            }
        """ ;
        sh:message "Asset ownership must not have changed since Phase 1" ;
    ] .
```

## Optimization Strategies

### Support-Set Hashing (Approach A)
- Hash the complete support set for each phase
- Skip SHACL validation if hash unchanged
- Still requires database queries each phase

### Delta/Invalidation (Approach B)
- Track invalidating events in memory
- Only re-validate when relevant events occur
- Minimal database overhead for unchanged state

## Implementation Considerations

### Event Sources
- Block commit events
- Transaction state changes
- Time-based expirations
- Ownership transfers

### Caching Strategy
- Cache validation results per phase
- Invalidate cache on state changes
- Maintain support-set hashes

### Performance Metrics
- Database queries per phase
- SHACL validation time
- Cache hit rates
- Event processing latency

This three-phase approach ensures transaction integrity while providing opportunities for optimization through intelligent caching and event-driven invalidation.
