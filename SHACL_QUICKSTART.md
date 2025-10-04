# SHACL-Only Validation - Quick Start Guide

## 🎯 **New Architecture: Pure SHACL Validation**

All transaction validation is now handled by the SHACL microservice using declarative constraints + MongoDB state queries.

---

## 🚀 **5-Minute Setup**

### 1. Start Services

```bash
cd smartchaindb
docker-compose up -d

# Wait for services to initialize (~30 seconds)
```

### 2. Verify SHACL Service

```bash
curl http://localhost:3000/

# Expected output:
# {
#   "message": "SHACL validation server with MongoDB integration is running",
#   "loaded_shapes": ["CREATE", "ADVERTISEMENT", "BUY_OFFER", "SELL", "TRANSFER"],
#   "mongodb_connected": true,
#   "validation_mode": "Full (SHACL + State)"
# }
```

✅ If `mongodb_connected: true`, you're ready!

### 3. Test Transaction Flow

```bash
cd ../smartchaindb-driver
mvn clean package
java -jar target/smartchaindb-driver.jar
```

**All validation happens automatically via SHACL!** 🎉

---

## 📝 **What SHACL Validates**

### **Phase 1: Syntactic (SHACL Shapes)**
- ✅ Structure (required fields, types)
- ✅ Patterns (regex for amounts, keys, dates)
- ✅ Constraints (min/max, ranges, enumerations)

### **Phase 2: State Consistency (MongoDB)**
- ✅ Advertisement exists and is OPEN (for BUY_OFFER)
- ✅ Buy offer exists and not expired (for SELL)
- ✅ Amounts match between transactions
- ✅ No double-spending/double-selling
- ✅ Asset ownership verification

**Note:** BigchainDB stores metadata in a separate `metadata` collection (not in the transaction document itself). The SHACL service queries both `transactions` and `metadata` collections for complete validation.

---

## 🔍 **Example: BUY_OFFER Validation**

When you send a BUY_OFFER transaction:

```json
{
  "operation": "BUY_OFFER",
  "asset": {
    "id": "abc...",
    "data": {
      "advertisement_id": "xyz..."
    }
  },
  "metadata": {
    "buyer_public_key": "...",
    "offer_amount": "900",
    "offer_currency": "USD",
    "offer_expiry": "2025-10-10T00:00:00Z"
  }
}
```

**SHACL validates**:
1. ✅ `offer_amount` is numeric string (pattern: `^[0-9]{1,20}$`)
2. ✅ `buyer_public_key` is valid base58
3. ✅ `offer_expiry` is valid ISO 8601 date
4. ✅ Advertisement `xyz...` exists in MongoDB
5. ✅ Advertisement status is "OPEN"
6. ✅ Offer hasn't expired

**If any check fails → Transaction rejected immediately** ❌

---

## ⚙️ **Configuration**

### **Default (already set)**

SHACL validation is **enabled by default** in `bigchaindb/__init__.py`:

```python
"shacl": {
    "enabled": True,  # Required
    "endpoint": "http://shacleng:3000",
    "timeout": 10
}
```

### **Environment Variables**

Override via environment:

```bash
export BIGCHAINDB_SHACL_ENABLED=true
export BIGCHAINDB_SHACL_ENDPOINT=http://shacleng:3000
export BIGCHAINDB_SHACL_TIMEOUT=10
```

---

## 🐛 **Troubleshooting**

### **Service Not Starting**

```bash
# Check logs
docker-compose logs shacleng

# Common issues:
# - Port 3000 in use
# - MongoDB connection failed
# - Missing .ttl files
```

### **MongoDB Not Connected**

```bash
# Check MongoDB
docker-compose logs mongodb

# Restart services
docker-compose restart mongodb shacleng bigchaindb
```

### **Validation Failing**

```bash
# Check what failed
docker-compose logs shacleng | tail -50

# Look for MongoDB query errors or SHACL violations
```

### **Check Health**

```bash
# SHACL service
curl http://localhost:3000/

# BigchainDB
curl http://localhost:9984/

# MongoDB (from inside container)
docker-compose exec mongodb mongo -u admin -p password --eval "db.adminCommand('ping')"
```

---

## 📚 **Key Files**

| File | Purpose |
|------|---------|
| `bigchaindb/backend/localshacl/shapes/index.js` | SHACL service with MongoDB validation |
| `bigchaindb/backend/localshacl/shapes/shapes/*.ttl` | SHACL constraint definitions |
| `bigchaindb/models.py` | Calls SHACL validation |
| `bigchaindb/__init__.py` | Configuration |

---

## 🔧 **Adding New Validation Rules**

### **For Syntactic Rules (patterns, types)**

Edit the `.ttl` file in `bigchaindb/backend/localshacl/shapes/shapes/`:

```turtle
# Add to BUY_OFFER.ttl
sh:property [
    sh:path bdb:new_field ;
    sh:datatype xsd:string ;
    sh:minLength 1 ;
    sh:message "new_field is required" ;
] .
```

Restart SHACL service: `docker-compose restart shacleng`

### **For State Rules (database checks)**

Edit `validateBuyOffer()` in `bigchaindb/backend/localshacl/shapes/index.js`:

```javascript
// Add new MongoDB query
const something = await transactions.findOne({...});
if (!something) {
    errors.push({message: ['Custom error']});
}
```

Restart SHACL service: `docker-compose restart shacleng`

---

## 🧪 **Testing**

### **Quick Test**

```bash
# Test SHACL service directly
curl -X POST http://localhost:3000/validate \
  -H "Content-Type: application/json" \
  -d '{
    "shapeType": "CREATE",
    "data": "@prefix bdb: <http://bigchaindb.com/ns#> .\n<urn:tx:test> a bdb:CREATETransaction ;\n  bdb:operation \"CREATE\" ."
  }'
```

### **Run Test Suite**

```bash
# Unit tests
pytest tests/test_shacl_validation.py -v

# Integration tests (requires running services)
pytest tests/integration/test_shacl_integration.py -v
```

---

## 📖 **Learn More**

- **Architecture**: `docs/SHACL_REFACTORING_SUMMARY.md`
- **Full Documentation**: `bigchaindb/backend/localshacl/README.md`
- **SHACL Specification**: https://www.w3.org/TR/shacl/

---

## 🎉 **You're Ready!**

Your transactions are now validated using **pure declarative SHACL constraints** with **state consistency checks** via MongoDB.

**No more imperative Python validation code!** 🚀

---

**Need Help?** Check logs: `docker-compose logs shacleng bigchaindb`
