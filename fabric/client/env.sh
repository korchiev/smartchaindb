# Source from Ubuntu-26.04 before enroll / submit / smoke.
export FABRIC_CONNECTION_PROFILE="${FABRIC_CONNECTION_PROFILE:-$HOME/fabric-samples/test-network/organizations/peerOrganizations/org1.example.com/connection-org1.json}"
export FABRIC_WALLET_DIR="${FABRIC_WALLET_DIR:-$HOME/fabric-wallet}"
export FABRIC_IDENTITY="${FABRIC_IDENTITY:-appUser}"
export FABRIC_CHANNEL="${FABRIC_CHANNEL:-mychannel}"
export FABRIC_CONTRACT="${FABRIC_CONTRACT:-marketplace}"
export SHACL_ENDPOINT="${SHACL_ENDPOINT:-http://localhost:3001}"
export PATH="$HOME/fabric-samples/bin:$PATH"
