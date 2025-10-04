# SHACL Validation Microservice

This directory contains the SHACL (Shapes Constraint Language) validation microservice for BigchainDB. It provides **declarative, RDF-based transaction validation** that has **completely replaced** the legacy Python validation system.

## 🏗️ Architecture

```
BigchainDB (Python) ──HTTP──> SHACL Engine (Node.js)
                                      │
                                      ├──> SHACL Shapes (.ttl) ─── Syntactic/Semantic Rules
                                      │
                                      └──> MongoDB ────────────── State Consistency Checks
                                             │
                                             ├─ transactions collection
                                             ├─ metadata collection
                                             └─ assets collection
```

### Two-Phase Validation

1. **SHACL Validation** (Syntactic & Semantic)
   - Structure validation (required fields, data types)
   - Pattern matching (regex for hashes, amounts, etc.)
   - Cardinality constraints (min/max counts)
   - Business rules (operation-specific logic)

2. **State Validation** (MongoDB Queries)
   - Advertisement exists and is OPEN
   - Buy offer hasn't expired
   - Asset ownership verification
   - Double-spend prevention
   - Cross-transaction consistency

## 📁 Directory Structure

```
localshacl/
├── shapes/                   # SHACL microservice application
│   ├── index.js             # Express.js HTTP API server
│   ├── package.json         # Node.js dependencies
│   ├── Dockerfile           # Container definition
│   └── shapes/              # SHACL shape definitions (.ttl files)
│       ├── CREATE.ttl
│       ├── ADVERTISEMENT.ttl
│       ├── BUY_OFFER.ttl
│       ├── SELL.ttl
│       └── TRANSFER.ttl
└── README.md                # This file
```

## 🚀 Quick Start

### 1. Start the SHACL Service

The SHACL service runs automatically with Docker Compose:

```bash
cd smartchaindb
docker-compose up -d shacleng
```

Check service health:

```bash
curl http://localhost:3000/
```

Expected response:

```json
{
  "message": "SHACL validation server with MongoDB integration is running",
  "loaded_shapes": ["CREATE", "ADVERTISEMENT", "BUY_OFFER", "SELL", "TRANSFER"],
  "mongodb_connected": true,
  "validation_mode": "Full (SHACL + State)"
}
```

### 2. Enable SHACL Validation in BigchainDB

Set environment variable:

```bash
export BIGCHAINDB_SHACL_ENABLED=true
export BIGCHAINDB_SHACL_ENDPOINT=http://shacleng:3000
export BIGCHAINDB_SHACL_TIMEOUT=5
```

Or in your configuration file (`~/.bigchaindb`):

```json
{
  "shacl": {
    "enabled": true,
    "endpoint": "http://shacleng:3000",
    "timeout": 5
  }
}
```

### 3. Restart BigchainDB

```bash
docker-compose restart bigchaindb
```

## 📝 API Reference

### `GET /`

Health check endpoint.

**Response:**

```json
{
  "message": "SHACL validation server is running. POST to /validate.",
  "loaded_shapes": ["CREATE", "BUY_OFFER", "SELL"]
}
```

### `POST /validate`

Validate a transaction against a SHACL shape.

**Request:**

```json
{
  "shapeType": "BUY_OFFER",
  "data": "@prefix bdb: <http://bigchaindb.com/ns#> .\n<urn:tx:123> a bdb:BUY_OFFERTransaction ;\n  bdb:operation \"BUY_OFFER\" ."
}
```

**Response (Success):**

```json
{
  "conforms": true,
  "results": [],
  "validation_phases": {
    "shacl": "completed",
    "state": "completed"
  }
}
```

**Response (Failure):**

```json
{
  "conforms": false,
  "results": [
    {
      "message": ["offer_amount must be a positive integer string"],
      "path": "http://bigchaindb.com/ns#offer_amount",
      "focusNode": "urn:tx:123",
      "severity": "http://www.w3.org/ns/shacl#Violation",
      "sourceConstraintComponent": "http://www.w3.org/ns/shacl#PatternConstraintComponent"
    }
  ]
}
```

## 🔧 SHACL Shape Development

### Shape File Format

SHACL shapes are defined in Turtle (`.ttl`) format. Example:

```turtle
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix bdb: <http://bigchaindb.com/ns#> .

bdb:BuyOfferTransactionShape a sh:NodeShape ;
    sh:targetClass bdb:BuyOfferTransaction ;
    sh:property [
        sh:path bdb:operation ;
        sh:hasValue "BUY_OFFER" ;
        sh:minCount 1 ;
        sh:maxCount 1 ;
        sh:message "Operation must be 'BUY_OFFER'" ;
    ] ;
    sh:property [
        sh:path bdb:metadata ;
        sh:node bdb:BuyOfferMetadataShape ;
        sh:minCount 1 ;
        sh:message "Metadata is required" ;
    ] .

bdb:BuyOfferMetadataShape a sh:NodeShape ;
    sh:property [
        sh:path bdb:offer_amount ;
        sh:datatype xsd:string ;
        sh:pattern "^[0-9]{1,20}$" ;
        sh:minCount 1 ;
        sh:message "offer_amount must be a positive integer string" ;
    ] .
```

### Common SHACL Constraints

- `sh:minCount` / `sh:maxCount` - Cardinality constraints
- `sh:datatype` - XSD datatype (xsd:string, xsd:integer, xsd:dateTime, etc.)
- `sh:pattern` - Regular expression validation
- `sh:in` - Enumeration of allowed values
- `sh:minLength` / `sh:maxLength` - String length constraints
- `sh:minInclusive` / `sh:maxInclusive` - Numeric range constraints
- `sh:hasValue` - Exact value match
- `sh:node` - Nested shape validation

### Adding a New Shape

1. Create a new `.ttl` file in `shapes/shapes/` directory
2. Name it after the transaction operation (e.g., `MY_OPERATION.ttl`)
3. Define the shape using SHACL syntax
4. Restart the SHACL service: `docker-compose restart shacleng`

No code changes needed! Shapes are loaded automatically at startup.

## 🧪 Testing

### Manual Testing

Test validation endpoint directly:

```bash
curl -X POST http://localhost:3000/validate \
  -H "Content-Type: application/json" \
  -d '{
    "shapeType": "CREATE",
    "data": "@prefix bdb: <http://bigchaindb.com/ns#> .\n<urn:tx:test> a bdb:CREATETransaction ;\n  bdb:operation \"CREATE\" ."
  }'
```

### Automated Tests

Run Python tests:

```bash
cd smartchaindb
pytest tests/test_shacl_validation.py -v
```

## 📊 Performance

- **Shape Caching**: All shapes are loaded into memory at startup
- **MongoDB Connection Pooling**: Persistent connection to MongoDB for fast queries
- **Concurrent Requests**: Express.js handles multiple validation requests
- **Timeout**: Configurable timeout (default 10 seconds)
- **Validation Frequency**: Called 3 times per transaction (HTTP POST, CheckTx, DeliverTx)

### Performance Considerations

The SHACL service is called **3 times** for each transaction:
1. Initial HTTP POST to BigchainDB API
2. Tendermint CheckTx (mempool validation)
3. Tendermint DeliverTx (block commitment)

For high-throughput scenarios, consider implementing validation result caching.

## 🐛 Troubleshooting

### SHACL service not starting

Check logs:

```bash
docker-compose logs shacleng
```

Common issues:
- Port 3000 already in use
- Missing `node_modules` (run `npm install` in `shapes/` directory)
- Syntax errors in `.ttl` files

### Validation always fails

- Check that shape file name matches operation name
- Verify Turtle syntax in shape files
- Enable DEBUG logging to see RDF conversion
- Check MongoDB connectivity: `docker-compose logs shacleng`
- Verify metadata collection structure (BigchainDB stores metadata separately)

### Service timeout

- Increase timeout in configuration
- Check network connectivity between BigchainDB and SHACL service
- Verify service is running: `docker-compose ps shacleng`
- Check MongoDB queries aren't slow (add indexes if needed)

### MongoDB connection issues

- Ensure MongoDB is running: `docker-compose ps mongodb`
- Check MongoDB credentials in `docker-compose.yml`
- Verify network connectivity: SHACL service should be in same Docker network
- Check environment variables: `MONGO_HOST`, `MONGO_PORT`, `MONGO_USER`, `MONGO_PASSWORD`

## 🗄️ BigchainDB MongoDB Structure

**Important Discovery:** BigchainDB stores transactions in a **separated schema**:

### Collections

1. **`transactions`** - Transaction structure (WITHOUT metadata)
   ```json
   {
     "id": "abc123...",
     "operation": "ADVERTISEMENT",
     "asset": {"id": "xyz..."},
     "inputs": [...],
     "outputs": [...],
     "version": "2.0"
   }
   ```

2. **`metadata`** - Transaction metadata (SEPARATE collection)
   ```json
   {
     "id": "abc123...",
     "metadata": {
       "status": "OPEN",
       "advertiser_public_key": "...",
       "price": "1000.00",
       ...
     }
   }
   ```

3. **`assets`** - Asset data (SEPARATE collection)

### State Validation Queries

The SHACL service queries MongoDB for state consistency:

```javascript
// Check advertisement exists
const advertisement = await db.collection('transactions').findOne({
    id: advertisementId,
    operation: 'ADVERTISEMENT'
});

// Get advertisement metadata from separate collection
const metadata = await db.collection('metadata').findOne({
    id: advertisementId
});

// Validate status
if (metadata.metadata.status !== 'OPEN') {
    // Reject transaction
}
```

This separation allows for efficient queries and flexible metadata updates without modifying transaction records.

## 📚 Resources

- [SHACL W3C Specification](https://www.w3.org/TR/shacl/)
- [RDF Turtle Format](https://www.w3.org/TR/turtle/)
- [shacl-engine Documentation](https://github.com/zazuko/shacl-engine)
- [BigchainDB Documentation](https://docs.bigchaindb.com/)
- [MongoDB Node.js Driver](https://mongodb.github.io/node-mongodb-native/)

## 🤝 Contributing

To add or modify SHACL shapes:

1. Edit or create `.ttl` files in `shapes/shapes/`
2. Test locally using the `/validate` endpoint
3. Submit a pull request with your changes

Shape changes do not require code changes in BigchainDB!

