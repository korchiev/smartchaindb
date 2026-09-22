# Hyperledger Fabric Integration (Plan B)

This folder implements the same marketplace workflow as SmartChainDB on Hyperledger Fabric, plus optional SHACL pre-validation.

## Same functionality as SmartChainDB

| SmartChainDB operation | Fabric chaincode function | State checks |
|---|---|---|
| CREATE | `CreateAsset` | asset id unique |
| ADVERTISEMENT | `CreateAdvertisement` | asset exists, advertiser is owner, at most one OPEN ad |
| UPDATE_ADV | `UpdateAdvertisement` | only advertiser; OPEN→LOCKED/CLOSED |
| BUY_OFFER | `SubmitBuyOffer` | advertisement exists and OPEN |
| SELL | `Sell` | offer OPEN, ad OPEN, seller owns asset, offer not already sold; transfers asset and closes ad |
| TRANSFER | `Transfer` | current owner matches; reject if asset has an OPEN ad |
| REQUEST_RETURN | `RequestReturn` | sale exists; requester is buyer; one return per sale |
| SELLER_ACCEPT_RETURN | `SellerAcceptReturn` | return OPEN; original seller accepts; asset restored |

Direct path: client → Fabric endorsement/order/commit, with those checks in Go chaincode.

## How SHACL is used on Fabric

Fabric is execute-order-validate. SHACL cannot replace endorsement, but it can sit in the **pre-execution** slot:

1. Client queries current world state (`ReadAsset`, `ReadAdvertisement`, `ReadBuyOffer`, …).
2. Client builds an RDF graph of the proposed transaction **plus** those state facts (`assetExists`, `advertiserIsOwner`, `offerOpen`, …).
3. Fabric SHACL validator (`fabric/shacl`) checks the graph against shapes in `fabric/shacl/shapes/`.
4. If SHACL fails, the client **does not submit** (fail closed).
5. If SHACL passes, the client submits; chaincode still enforces the same rules at endorsement.

This matches the paper’s “declarative pre-validation” path without claiming Fabric VM integration.

```
Client  --evaluate-->  peer world state
   |
   +-- Turtle graph --> fabric/shacl:3001  --pass-->  submitTransaction
                                              fail-->  abort, no wasted endorsement
```

Shapes are Fabric-adapted (string IDs, no BigchainDB hex/base58 patterns) but encode the **same semantic constraints**.

## Prerequisites (already installed on Ubuntu-26.04)

- Docker CE 27.5.1 (Fabric 2.5 needs this; Docker 29 breaks chaincode builds)
- Go 1.20+, Node 18+
- Fabric 2.5.12 at `~/fabric-samples`

Run **all of this from Ubuntu-26.04 (WSL)**, including both SHACL processes and the Node client. Do not start `node server.js` or `node index.js` from Windows PowerShell — those bind the shared localhost ports and the WSL client cannot use them reliably.

## Bring-up

```bash
# 1) Docker
sudo service docker start

# 2) Network + chaincode (language must be "go")
cd ~/fabric-samples/test-network
export PATH=$HOME/fabric-samples/bin:$PATH
./network.sh deployCC -c mychannel -ccn marketplace \
  -ccp /mnt/c/Users/korchien/Research/smartchaindb/fabric/chaincode/marketplace \
  -ccl go -ccv 1.2 -ccs 3

# 3) SHACL validators (WSL Node, not Windows)
# BigchainDB SHACL :3000
cd /mnt/c/Users/korchien/Research/smartchaindb/bigchaindb/backend/localshacl/shapes
MONGO_HOST=127.0.0.1 PORT=3000 node index.js

# Fabric SHACL :3001 (separate terminal)
cd /mnt/c/Users/korchien/Research/smartchaindb/fabric/shacl
npm install
node server.js
```

Enroll a client identity once, then submit with or without SHACL:

```bash
cd /mnt/c/Users/korchien/Research/smartchaindb/fabric/client
npm install
source ./env.sh
node enroll.js                 # $HOME/fabric-wallet; cryptogen User1 if CA is down
# Live check (network already up, marketplace v1.2 seq 3, SHACL on :3001):
USE_SHACL=true npm run smoke

# Direct (imperative chaincode only)
node index.js submit CreateAsset --payload '{"assetId":"a1","owner":"org1User","description":"demo"}' --use-shacl=false

# SHACL pre-validate, then submit
node index.js submit CreateAsset --payload '{"assetId":"a2","owner":"org1User","description":"demo"}' --use-shacl=true

# Full lifecycle + SHACL reject of a bad advertise
USE_SHACL=true npm run smoke

# Sequential workload
N=5 RETURNS=0.2 USE_SHACL=true npm run workload
```

WAN profile (after network is up):

```bash
bash fabric/scripts/wan_profile.sh 40 5
```

## Evaluation rule

Report **within-Fabric** deltas only: Direct chaincode vs SHACL-prevalidate+chaincode. Do not headline cross-platform TPS vs BigchainDB or Quorum.

Directory layout:

```
fabric/
  chaincode/marketplace/   Go chaincode (all 8 operations)
  shacl/shapes/            Fabric SHACL shapes
  shacl/server.js          SHACL validator on :3001
  client/index.js          submit + optional SHACL
  client/workload.js       sequential lifecycle driver
  scripts/setup_fabric.sh
  scripts/wan_profile.sh
```
