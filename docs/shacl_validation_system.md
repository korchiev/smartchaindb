# SHACL-Based Transaction Validation System

## Overview

This document describes the implementation of a **SHACL (Shapes Constraint Language) based transaction validation system** for SmartChainDB, which demonstrates the **algebraic transaction model with declarative specifications** described in the research paper.

## 🎯 Research Context

The implementation addresses the paper's key contributions:

1. **Algebraic Transaction Model**: Expressing transaction validation as declarative constraints
2. **SHACL Integration**: Using Shapes Constraint Language for formal validation semantics
3. **Stratified Architecture**: Layered validation approach enabling systematic composition
4. **Graph Pattern Constraints**: Formulating validation as constraint-checking problems
5. **Performance Optimization**: Enabling query optimization-like improvements

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Transaction Request                      │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│              Transaction Interceptor                        │
│  ┌─────────────────┐  ┌─────────────────────────────────┐  │
│  │   SHACL Path    │  │      Traditional Path          │  │
│  │  (Declarative)  │  │      (Imperative)              │  │
│  └─────────────────┘  └─────────────────────────────────┘  │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│              SHACL Validator                               │
│  ┌─────────────────┐  ┌─────────────────────────────────┐  │
│  │ Schema Validation│  │    Business Rule Validation    │  │
│  │   (Structure)   │  │      (Semantics)                │  │
│  └─────────────────┘  └─────────────────────────────────┘  │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │           State Consistency Validation                  │  │
│  │              (Graph Patterns)                          │  │
│  └─────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

## 🔧 Core Components

### 1. SHACL Validator (`shacl_schemas.py`)

The core validation engine that implements SHACL constraint checking:

```python
class SHACLValidator:
    """SHACL-based transaction validator for SmartChainDB"""
    
    def validate_transaction(self, transaction_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate transaction using SHACL constraints"""
        
    def _validate_against_schema(self, data: Dict[str, Any], schema: Dict[str, Any]) -> Dict[str, Any]:
        """Validate data against a SHACL schema"""
        
    def _validate_property(self, data: Dict[str, Any], prop: Dict[str, Any]) -> List[str]:
        """Validate a single property against SHACL constraints"""
```

**Key Features:**
- **Declarative Constraints**: Express validation rules as SHACL shapes
- **XSD Datatype Support**: Full XML Schema datatype validation
- **Pattern Matching**: Regular expression validation for strings
- **Nested Validation**: Hierarchical constraint validation
- **Constraint Types**: `hasValue`, `minCount`, `maxCount`, `minInclusive`, etc.

### 2. Transaction Interceptor (`transaction_interceptor.py`)

The main entry point that intercepts transaction requests and routes them through SHACL validation:

```python
class TransactionInterceptor:
    """Intercepts transaction requests and validates them using SHACL constraints"""
    
    def intercept_and_validate(self, transaction_data: Dict[str, Any], 
                             use_shacl: bool = True) -> Tuple[bool, List[str], float]:
        """Intercept and validate a transaction using either SHACL or traditional validation"""
        
    def _validate_with_shacl(self, transaction_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate transaction using SHACL constraints (declarative approach)"""
        
    def _validate_business_rules_shacl(self, transaction_data: Dict[str, Any]) -> List[str]:
        """Validate business rules using SHACL pattern matching"""
        
    def _validate_state_consistency_shacl(self, transaction_data: Dict[str, Any]) -> List[str]:
        """Validate state consistency using SHACL graph patterns"""
```

**Key Features:**
- **Dual Validation Paths**: SHACL vs traditional validation
- **Business Rule Validation**: Semantic constraint checking
- **State Consistency**: Graph pattern-based validation
- **Performance Monitoring**: Validation timing and statistics
- **Fallback Support**: Automatic fallback to traditional validation

### 3. Configuration System (`shacl_config.py`)

Environment-based configuration for the SHACL validation system:

```python
class SHACLConfig:
    """Configuration class for SHACL validation system"""
    
    def __init__(self):
        self.enabled = self._get_env_bool('BIGCHAINDB_SHACL_ENABLED', True)
        self.strict_mode = self._get_env_bool('BIGCHAINDB_SHACL_STRICT_MODE', False)
        self.enable_business_rules = self._get_env_bool('BIGCHAINDB_SHACL_BUSINESS_RULES', True)
        self.enable_state_validation = self._get_env_bool('BIGCHAINDB_SHACL_STATE_VALIDATION', True)
        # ... more configuration options
```

**Key Features:**
- **Environment Variables**: Flexible configuration via environment
- **Operation-Specific Rules**: Custom validation rules per transaction type
- **Performance Tuning**: Caching, timeouts, and thresholds
- **Logging Control**: Detailed validation logging options

## 📋 SHACL Schema Examples

### ADVERTISEMENT Transaction Schema

```json
{
  "@context": {
    "sh": "http://www.w3.org/ns/shacl#",
    "xsd": "http://www.w3.org/2001/XMLSchema#",
    "bigchaindb": "https://bigchaindb.com/ns#"
  },
  "@type": "sh:NodeShape",
  "targetClass": "bigchaindb:AdvertisementTransaction",
  "property": [
    {
      "path": "bigchaindb:operation",
      "hasValue": "ADVERTISEMENT",
      "message": "Operation must be ADVERTISEMENT"
    },
    {
      "path": "bigchaindb:metadata",
      "node": {
        "@type": "sh:NodeShape",
        "property": [
          {
            "path": "bigchaindb:status",
            "in": ["OPEN", "LOCKED", "CLOSED"],
            "message": "Status must be one of: OPEN, LOCKED, CLOSED"
          },
          {
            "path": "bigchaindb:advertiser_public_key",
            "datatype": "xsd:string",
            "pattern": "^[1-9A-HJ-NP-Za-km-z]{43,44}$",
            "message": "Advertiser public key must be a valid base58 string"
          }
        ],
        "required": ["status", "advertiser_public_key"]
      }
    }
  ]
}
```

### BUY_OFFER Transaction Schema

```json
{
  "@context": {
    "sh": "http://www.w3.org/ns/shacl#",
    "xsd": "http://www.w3.org/2001/XMLSchema#",
    "bigchaindb": "https://bigchaindb.com/ns#"
  },
  "@type": "sh:NodeShape",
  "targetClass": "bigchaindb:BuyOfferTransaction",
  "property": [
    {
      "path": "bigchaindb:metadata",
      "node": {
        "@type": "sh:NodeShape",
        "property": [
          {
            "path": "bigchaindb:offer_amount",
            "datatype": "xsd:decimal",
            "minInclusive": 0.01,
            "message": "Offer amount must be positive"
          },
          {
            "path": "bigchaindb:offer_expiry",
            "datatype": "xsd:dateTime",
            "message": "Offer expiry must be a valid datetime"
          }
        ],
        "required": [
          "buyer_public_key", "offer_amount", "offer_currency",
          "offer_expiry", "escrow_public_key"
        ]
      }
    }
  ]
}
```

## 🚀 Validation Process

### 1. Schema Validation (Structure)

```python
def _validate_against_schema(self, data: Dict[str, Any], schema: Dict[str, Any]) -> Dict[str, Any]:
    """Validate data against a SHACL schema"""
    errors = []
    
    # Validate properties
    if 'property' in schema:
        for prop in schema['property']:
            prop_errors = self._validate_property(data, prop)
            errors.extend(prop_errors)
    
    # Validate required fields
    if 'required' in schema:
        for required_field in schema['required']:
            if required_field not in data:
                errors.append(f"Required field '{required_field}' is missing")
    
    return {
        'valid': len(errors) == 0,
        'errors': errors
    }
```

**Validates:**
- Required fields presence
- Data types (string, integer, decimal, boolean, datetime)
- Pattern matching (regex)
- Value constraints (min/max, inclusive ranges)
- Enumeration values
- Array constraints (min/max count)

### 2. Business Rule Validation (Semantics)

```python
def _validate_business_rules_shacl(self, transaction_data: Dict[str, Any]) -> List[str]:
    """Validate business rules using SHACL pattern matching"""
    errors = []
    operation = transaction_data.get('operation', '')
    
    if operation == 'BUY_OFFER':
        # Business rule: Buyer ≠ advertiser
        errors.extend(self._validate_buyer_not_advertiser(transaction_data))
        
        # Business rule: Offer expiry must be in future
        errors.extend(self._validate_offer_expiry(transaction_data))
    
    elif operation == 'SELL':
        # Business rule: Sale amount ≤ offer amount
        errors.extend(self._validate_sale_amount_constraint(transaction_data))
        
        # Business rule: Seller must be advertiser
        errors.extend(self._validate_seller_is_advertiser(transaction_data))
    
    return errors
```

**Validates:**
- Cross-field relationships
- Business logic constraints
- Temporal constraints
- Ownership relationships
- Amount consistency

### 3. State Consistency Validation (Graph Patterns)

```python
def _validate_state_consistency_shacl(self, transaction_data: Dict[str, Any]) -> List[str]:
    """Validate state consistency using SHACL graph patterns"""
    errors = []
    operation = transaction_data.get('operation', '')
    
    if operation == 'ADVERTISEMENT':
        # State rule: No other OPEN ads for same asset
        errors.extend(self._validate_no_duplicate_ads(transaction_data))
        
    elif operation == 'BUY_OFFER':
        # State rule: Referenced advertisement must be OPEN
        errors.extend(self._validate_advertisement_status(transaction_data))
    
    return errors
```

**Validates:**
- Blockchain state consistency
- Transaction dependencies
- Asset ownership states
- Advertisement statuses
- Return request states

## 🔄 Integration with BigChainDB

### Traditional Validation Flow

```
Transaction Request → BigChainDB → Traditional Validation → Response
```

### SHACL Validation Flow

```
Transaction Request → Interceptor → SHACL Validation → BigChainDB → Response
```

### Configuration-Based Routing

```python
def intercept_and_validate(self, transaction_data: Dict[str, Any], 
                         use_shacl: bool = True) -> Tuple[bool, List[str], float]:
    """Intercept and validate a transaction using either SHACL or traditional validation"""
    
    if use_shacl and self.shacl_config.is_validation_enabled(operation):
        # Use SHACL-based declarative validation
        validation_result = self._validate_with_shacl(transaction_data)
        self.validation_stats['shacl_validations'] += 1
    else:
        # Use traditional imperative validation
        validation_result = self._validate_traditionally(transaction_data)
        self.validation_stats['traditional_validations'] += 1
```

## 📊 Performance Monitoring

The system provides comprehensive performance metrics:

```python
def get_validation_stats(self) -> Dict[str, Any]:
    """Get validation statistics"""
    stats = self.validation_stats.copy()
    
    if stats['validation_times']:
        stats['avg_validation_time_ms'] = sum(stats['validation_times']) / len(stats['validation_times'])
        stats['min_validation_time_ms'] = min(stats['validation_times'])
        stats['max_validation_time_ms'] = max(stats['validation_times'])
    
    return stats
```

**Metrics Tracked:**
- Total transactions processed
- SHACL vs traditional validation counts
- Validation timing (min, max, average)
- Error rates by transaction type
- Performance thresholds and alerts

## 🧪 Testing and Validation

### Test Scripts

1. **`test_shacl_validation.py`**: Comprehensive testing of the SHACL system
2. **`test_all_transactions.py`**: Testing all transaction types
3. **`docker_test_buy_offer.py`**: Docker-specific testing

### Test Coverage

- ✅ **Schema Validation**: All SHACL constraint types
- ✅ **Business Rules**: Cross-field validation logic
- ✅ **State Consistency**: Graph pattern validation
- ✅ **Performance**: Benchmarking and comparison
- ✅ **Error Handling**: Invalid transaction scenarios
- ✅ **Configuration**: Environment-based settings

## 🌟 Research Contributions Demonstrated

### 1. Algebraic Transaction Model

The implementation demonstrates how transaction validation can be expressed as **algebraic operations** on constraint sets:

```python
# Constraint composition
schema_constraints = self.shacl_validator.validate_transaction(transaction_data)
business_constraints = self._validate_business_rules_shacl(transaction_data)
state_constraints = self._validate_state_consistency_shacl(transaction_data)

# Algebraic combination
final_result = schema_constraints AND business_constraints AND state_constraints
```

### 2. Declarative Specifications

Instead of imperative validation code, the system uses **declarative SHACL constraints**:

```python
# Declarative approach (SHACL)
{
    "path": "bigchaindb:offer_amount",
    "datatype": "xsd:decimal",
    "minInclusive": 0.01,
    "message": "Offer amount must be positive"
}

# vs Imperative approach (traditional)
if not isinstance(offer_amount, (int, float)) or offer_amount <= 0:
    raise ValueError("Offer amount must be positive")
```

### 3. Stratified Architecture

The validation system implements a **layered architecture**:

1. **Schema Layer**: Basic structural constraints
2. **Business Layer**: Semantic business rules
3. **State Layer**: Graph pattern consistency
4. **Integration Layer**: BigChainDB integration

### 4. Graph Pattern Constraints

State validation uses **graph pattern matching** to ensure consistency:

```python
def _validate_advertisement_status(self, transaction_data: Dict[str, Any]) -> List[str]:
    """Validate referenced advertisement is OPEN using graph pattern"""
    advertisement_id = transaction_data.get('asset', {}).get('advertisement_id')
    if advertisement_id and self.bigchain:
        # Graph traversal: BUY_OFFER → ADVERTISEMENT → status
        ad_tx = self.bigchain.get_transaction(advertisement_id)
        if ad_tx and ad_tx.metadata:
            status = ad_tx.metadata.get('status')
            if status != 'OPEN':
                errors.append(f"Referenced advertisement must be OPEN, got: {status}")
```

### 5. Optimization Opportunities

The declarative approach enables **query optimization-like improvements**:

- **Constraint Indexing**: Pre-computed constraint sets
- **Pattern Matching**: Efficient graph traversal
- **Caching**: Validation result caching
- **Parallel Validation**: Independent constraint validation

## 🔧 Configuration Options

### Environment Variables

```bash
# Enable/disable SHACL validation
export BIGCHAINDB_SHACL_ENABLED=true

# Strict mode (all constraints must pass)
export BIGCHAINDB_SHACL_STRICT_MODE=false

# Enable business rule validation
export BIGCHAINDB_SHACL_BUSINESS_RULES=true

# Enable state consistency validation
export BIGCHAINDB_SHACL_STATE_VALIDATION=true

# Performance monitoring
export BIGCHAINDB_SHACL_PERFORMANCE_MONITORING=true

# Validation timeout (ms)
export BIGCHAINDB_SHACL_TIMEOUT_MS=5000

# Caching options
export BIGCHAINDB_SHACL_CACHING=true
export BIGCHAINDB_SHACL_CACHE_SIZE=1000
export BIGCHAINDB_SHACL_CACHE_TTL=3600

# Logging
export BIGCHAINDB_SHACL_LOG_LEVEL=INFO
export BIGCHAINDB_SHACL_LOG_DETAILS=false
export BIGCHAINDB_SHACL_LOG_PERFORMANCE=true
```

### Custom Validation Rules

Create a JSON file with custom validation rules:

```json
{
  "BUY_OFFER": {
    "enabled": true,
    "business_rules": true,
    "state_validation": true,
    "custom_constraints": [
      {
        "path": "metadata.offer_amount",
        "maxInclusive": 1000000,
        "message": "Offer amount cannot exceed $1M"
      }
    ]
  }
}
```

Set the file path:
```bash
export BIGCHAINDB_SHACL_CUSTOM_RULES_FILE=/path/to/custom_rules.json
```

## 🚀 Usage Examples

### Basic Validation

```python
from bigchaindb.common.transaction_interceptor import TransactionInterceptor

# Create interceptor
interceptor = TransactionInterceptor()

# Validate transaction with SHACL
is_valid, errors, validation_time = interceptor.intercept_and_validate(
    transaction_data, use_shacl=True
)

print(f"Validation: {'✅' if is_valid else '❌'}")
print(f"Time: {validation_time:.2f}ms")
if errors:
    for error in errors:
        print(f"Error: {error}")
```

### Schema Export

```python
from bigchaindb.common.shacl_schemas import SHACLValidator

validator = SHACLValidator()

# Export BUY_OFFER schema as JSON
schema_json = validator.export_schema('BUY_OFFER', 'json')
print(schema_json)

# List supported operations
operations = validator.list_supported_operations()
print(f"Supported: {operations}")
```

### Configuration Management

```python
from bigchaindb.common.shacl_config import get_shacl_config, update_shacl_config

# Get current configuration
config = get_shacl_config()
print(config.get_environment_summary())

# Update configuration
update_shacl_config({
    'strict_mode': True,
    'validation_timeout_ms': 10000
})
```

## 🔍 Performance Analysis

### Validation Time Comparison

The system tracks performance metrics for both validation approaches:

```python
def test_performance_benchmark():
    """Benchmark SHACL vs traditional validation performance"""
    interceptor = TransactionInterceptor()
    
    # Run 100 iterations
    for _ in range(100):
        # SHACL validation
        start = time.time()
        interceptor.intercept_and_validate(tx_data, use_shacl=True)
        shacl_times.append((time.time() - start) * 1000)
        
        # Traditional validation
        start = time.time()
        interceptor.intercept_and_validate(tx_data, use_shacl=False)
        trad_times.append((time.time() - start) * 1000)
    
    # Calculate statistics
    shacl_avg = sum(shacl_times) / len(shacl_times)
    trad_avg = sum(trad_times) / len(trad_times)
    
    print(f"SHACL: {shacl_avg:.3f}ms average")
    print(f"Traditional: {trad_avg:.3f}ms average")
    print(f"Speedup: {trad_avg/shacl_avg:.2f}x")
```

### Expected Performance Characteristics

- **SHACL Validation**: 
  - ✅ **Declarative**: Easier to optimize and parallelize
  - ✅ **Caching**: Constraint result caching
  - ✅ **Indexing**: Pre-computed constraint sets
  - ⚠️ **Overhead**: Initial constraint compilation

- **Traditional Validation**:
  - ✅ **Direct**: No constraint interpretation overhead
  - ✅ **Optimized**: Hand-tuned validation logic
  - ⚠️ **Maintenance**: Harder to modify and extend
  - ⚠️ **Parallelization**: Difficult to parallelize

## 🔮 Future Enhancements

### 1. Advanced SHACL Features

- **SPARQL Integration**: Complex graph pattern queries
- **Custom Functions**: User-defined validation functions
- **Dynamic Constraints**: Runtime constraint modification
- **Constraint Composition**: Advanced constraint algebra

### 2. Performance Optimizations

- **JIT Compilation**: Just-in-time constraint compilation
- **GPU Acceleration**: Parallel constraint validation
- **Distributed Validation**: Multi-node validation
- **Smart Caching**: Intelligent cache invalidation

### 3. Integration Features

- **REST API**: HTTP-based validation endpoints
- **WebSocket**: Real-time validation streaming
- **Plugin System**: Extensible validation plugins
- **Monitoring Dashboard**: Real-time validation metrics

## 📚 References

1. **SHACL Specification**: [W3C SHACL](https://www.w3.org/TR/shacl/)
2. **XML Schema**: [W3C XML Schema](https://www.w3.org/XML/Schema)
3. **BigChainDB**: [BigChainDB Documentation](https://docs.bigchaindb.com/)
4. **Research Paper**: Algebraic Transaction Model for Blockchain Robustness

## 🤝 Contributing

To contribute to the SHACL validation system:

1. **Fork the repository**
2. **Create a feature branch**
3. **Implement your changes**
4. **Add tests**
5. **Submit a pull request**

## 📄 License

This implementation is part of the SmartChainDB project and follows the same licensing terms.

---

**Note**: This SHACL validation system demonstrates the research paper's approach to blockchain transaction validation using declarative constraints and algebraic models. It provides a robust foundation for extending blockchain capabilities while maintaining performance and safety guarantees.
