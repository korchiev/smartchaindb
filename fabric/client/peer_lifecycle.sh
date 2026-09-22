#!/bin/bash
set -euo pipefail
export PATH="$HOME/fabric-samples/bin:$PATH"
export FABRIC_CFG_PATH="$HOME/fabric-samples/config"
export CORE_PEER_TLS_ENABLED=true
export CORE_PEER_LOCALMSPID=Org1MSP
export CORE_PEER_TLS_ROOTCERT_FILE="$HOME/fabric-samples/test-network/organizations/peerOrganizations/org1.example.com/peers/peer0.org1.example.com/tls/ca.crt"
export CORE_PEER_MSPCONFIGPATH="$HOME/fabric-samples/test-network/organizations/peerOrganizations/org1.example.com/users/User1@org1.example.com/msp"
export CORE_PEER_ADDRESS=localhost:7051

TN="$HOME/fabric-samples/test-network"
ORDERER_CA="${TN}/organizations/ordererOrganizations/example.com/orderers/orderer.example.com/msp/tlscacerts/tlsca.example.com-cert.pem"
P1="${TN}/organizations/peerOrganizations/org1.example.com/peers/peer0.org1.example.com/tls/ca.crt"
P2="${TN}/organizations/peerOrganizations/org2.example.com/peers/peer0.org2.example.com/tls/ca.crt"

invoke() {
  peer chaincode invoke \
    -o localhost:7050 --ordererTLSHostnameOverride orderer.example.com \
    --tls --cafile "$ORDERER_CA" \
    -C mychannel -n marketplace \
    --peerAddresses localhost:7051 --tlsRootCertFiles "$P1" \
    --peerAddresses localhost:9051 --tlsRootCertFiles "$P2" \
    --waitForEvent \
    -c "$1"
}

SID="p$(date +%s)"
ASSET="asset_${SID}"
ADV="adv_${SID}"
OFFER="offer_${SID}"
SELL="sell_${SID}"
RET="ret_${SID}"
ACC="acc_${SID}"
EXPIRY="2099-01-01T00:00:00Z"

echo "PEER LIFECYCLE id=${SID}"
invoke "{\"Args\":[\"CreateAsset\",\"${ASSET}\",\"org1User\",\"peer lifecycle\"]}"
invoke "{\"Args\":[\"CreateAdvertisement\",\"${ADV}\",\"${ASSET}\",\"org1User\",\"100\"]}"
invoke "{\"Args\":[\"SubmitBuyOffer\",\"${OFFER}\",\"${ADV}\",\"org2User\",\"100\",\"${EXPIRY}\"]}"
invoke "{\"Args\":[\"Sell\",\"${SELL}\",\"${OFFER}\",\"org1User\"]}"
invoke "{\"Args\":[\"RequestReturn\",\"${RET}\",\"${SELL}\",\"org2User\",\"peer return\"]}"
invoke "{\"Args\":[\"SellerAcceptReturn\",\"${ACC}\",\"${RET}\",\"org1User\"]}"
peer chaincode query -C mychannel -n marketplace -c "{\"Args\":[\"ReadAsset\",\"${ASSET}\"]}"
echo
echo "PEER LIFECYCLE OK"
