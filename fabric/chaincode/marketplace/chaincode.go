package main

import (
	"encoding/json"
	"errors"
	"fmt"
	"time"

	"github.com/hyperledger/fabric-contract-api-go/contractapi"
)

// MarketplaceContract implements SmartChainDB marketplace semantics on Fabric.
type MarketplaceContract struct {
	contractapi.Contract
}

type Asset struct {
	ID          string `json:"id"`
	Owner       string `json:"owner"`
	Description string `json:"description"`
}

type Advertisement struct {
	ID         string `json:"id"`
	AssetID    string `json:"asset_id"`
	Advertiser string `json:"advertiser"`
	Status     string `json:"status"` // OPEN | LOCKED | CLOSED
	Price      string `json:"price"`
}

type BuyOffer struct {
	ID              string `json:"id"`
	AdvertisementID string `json:"advertisement_id"`
	Buyer           string `json:"buyer"`
	Amount          string `json:"amount"`
	Status          string `json:"status"` // OPEN | WITHDRAWN | ACCEPTED | EXPIRED
	Expiry          string `json:"expiry"`
}

type Sale struct {
	ID              string `json:"id"`
	OfferID         string `json:"offer_id"`
	AdvertisementID string `json:"advertisement_id"`
	AssetID         string `json:"asset_id"`
	Seller          string `json:"seller"`
	Buyer           string `json:"buyer"`
	Amount          string `json:"amount"`
	Timestamp       string `json:"timestamp"`
}

type ReturnRequest struct {
	ID        string `json:"id"`
	SaleID    string `json:"sale_id"`
	AssetID   string `json:"asset_id"`
	Requester string `json:"requester"`
	Reason    string `json:"reason"`
	Status    string `json:"status"` // OPEN | ACCEPTED | CLOSED
	Timestamp string `json:"timestamp"`
}

type AcceptReturn struct {
	ID        string `json:"id"`
	RequestID string `json:"request_id"`
	SaleID    string `json:"sale_id"`
	AssetID   string `json:"asset_id"`
	Seller    string `json:"seller"`
	Timestamp string `json:"timestamp"`
}

func assetKey(id string) string          { return "ASSET_" + id }
func advKey(id string) string            { return "ADV_" + id }
func offerKey(id string) string          { return "OFFER_" + id }
func saleKey(id string) string           { return "SALE_" + id }
func returnKey(id string) string         { return "RETURN_" + id }
func acceptKey(id string) string         { return "ACCEPT_" + id }
func openAdvIndex(assetID string) string { return "IDX_OPEN_ADV_" + assetID }
func soldOfferIndex(offerID string) string {
	return "IDX_SALE_OFFER_" + offerID
}
func returnBySaleIndex(saleID string) string {
	return "IDX_RETURN_SALE_" + saleID
}
func acceptByReturnIndex(requestID string) string {
	return "IDX_ACCEPT_RETURN_" + requestID
}

func putJSON(ctx contractapi.TransactionContextInterface, key string, v interface{}) error {
	b, err := json.Marshal(v)
	if err != nil {
		return err
	}
	return ctx.GetStub().PutState(key, b)
}

func getJSON(ctx contractapi.TransactionContextInterface, key string) ([]byte, error) {
	b, err := ctx.GetStub().GetState(key)
	if err != nil {
		return nil, err
	}
	if b == nil {
		return nil, nil
	}
	return b, nil
}

func nowRFC3339() string {
	return time.Now().UTC().Format(time.RFC3339)
}

func allowedStatusTransition(current, next string) bool {
	if next == "" || next == current {
		return true
	}
	allowed := map[string][]string{
		"OPEN":   {"LOCKED", "CLOSED"},
		"LOCKED": {"CLOSED"},
		"CLOSED": {},
	}
	for _, v := range allowed[current] {
		if v == next {
			return true
		}
	}
	return false
}

// CreateAsset mints a new asset (CREATE).
func (c *MarketplaceContract) CreateAsset(ctx contractapi.TransactionContextInterface, assetID, owner, description string) error {
	if assetID == "" || owner == "" {
		return errors.New("assetID and owner are required")
	}
	existing, err := getJSON(ctx, assetKey(assetID))
	if err != nil {
		return err
	}
	if existing != nil {
		return fmt.Errorf("asset %s already exists", assetID)
	}
	return putJSON(ctx, assetKey(assetID), Asset{ID: assetID, Owner: owner, Description: description})
}

func (c *MarketplaceContract) ReadAsset(ctx contractapi.TransactionContextInterface, assetID string) (*Asset, error) {
	b, err := getJSON(ctx, assetKey(assetID))
	if err != nil {
		return nil, err
	}
	if b == nil {
		return nil, fmt.Errorf("asset %s not found", assetID)
	}
	var a Asset
	if err := json.Unmarshal(b, &a); err != nil {
		return nil, err
	}
	return &a, nil
}

// CreateAdvertisement lists an owned asset (ADVERTISEMENT).
func (c *MarketplaceContract) CreateAdvertisement(ctx contractapi.TransactionContextInterface, advID, assetID, advertiser, price string) error {
	if advID == "" || assetID == "" || advertiser == "" {
		return errors.New("advID, assetID, advertiser are required")
	}
	a, err := c.ReadAsset(ctx, assetID)
	if err != nil {
		return err
	}
	if a.Owner != advertiser {
		return fmt.Errorf("advertiser must be current owner")
	}
	existingAdv, err := getJSON(ctx, advKey(advID))
	if err != nil {
		return err
	}
	if existingAdv != nil {
		return fmt.Errorf("advertisement %s already exists", advID)
	}
	open, err := getJSON(ctx, openAdvIndex(assetID))
	if err != nil {
		return err
	}
	if open != nil {
		return fmt.Errorf("asset %s already has an active advertisement", assetID)
	}
	adv := Advertisement{
		ID:         advID,
		AssetID:    assetID,
		Advertiser: advertiser,
		Status:     "OPEN",
		Price:      price,
	}
	if err := putJSON(ctx, advKey(advID), adv); err != nil {
		return err
	}
	return ctx.GetStub().PutState(openAdvIndex(assetID), []byte(advID))
}

func (c *MarketplaceContract) GetOpenAdvertisementId(ctx contractapi.TransactionContextInterface, assetID string) (string, error) {
	b, err := getJSON(ctx, openAdvIndex(assetID))
	if err != nil {
		return "", err
	}
	if b == nil {
		return "", nil
	}
	return string(b), nil
}

func (c *MarketplaceContract) ReadAdvertisement(ctx contractapi.TransactionContextInterface, advID string) (*Advertisement, error) {
	b, err := getJSON(ctx, advKey(advID))
	if err != nil {
		return nil, err
	}
	if b == nil {
		return nil, fmt.Errorf("advertisement %s not found", advID)
	}
	var adv Advertisement
	if err := json.Unmarshal(b, &adv); err != nil {
		return nil, err
	}
	return &adv, nil
}

// UpdateAdvertisement changes price/status (UPDATE_ADV).
func (c *MarketplaceContract) UpdateAdvertisement(ctx contractapi.TransactionContextInterface, advID, updater, nextStatus, price string) error {
	adv, err := c.ReadAdvertisement(ctx, advID)
	if err != nil {
		return err
	}
	if adv.Advertiser != updater {
		return errors.New("only the advertiser can update the advertisement")
	}
	if nextStatus != "" && !allowedStatusTransition(adv.Status, nextStatus) {
		return fmt.Errorf("invalid status transition %s -> %s", adv.Status, nextStatus)
	}
	if nextStatus != "" {
		adv.Status = nextStatus
	}
	if price != "" {
		adv.Price = price
	}
	if err := putJSON(ctx, advKey(advID), adv); err != nil {
		return err
	}
	if adv.Status == "CLOSED" {
		return ctx.GetStub().DelState(openAdvIndex(adv.AssetID))
	}
	return nil
}

// SubmitBuyOffer posts an offer against an OPEN advertisement (BUY_OFFER).
func (c *MarketplaceContract) SubmitBuyOffer(ctx contractapi.TransactionContextInterface, offerID, advID, buyer, amount, expiry string) error {
	if offerID == "" || advID == "" || buyer == "" {
		return errors.New("offerID, advID, buyer are required")
	}
	adv, err := c.ReadAdvertisement(ctx, advID)
	if err != nil {
		return err
	}
	if adv.Status != "OPEN" {
		return fmt.Errorf("advertisement %s is not open", advID)
	}
	if expiry != "" {
		exp, err := time.Parse(time.RFC3339, expiry)
		if err == nil && exp.Before(time.Now().UTC()) {
			return fmt.Errorf("offer has already expired at %s", expiry)
		}
	}
	existing, err := getJSON(ctx, offerKey(offerID))
	if err != nil {
		return err
	}
	if existing != nil {
		return fmt.Errorf("offer %s already exists", offerID)
	}
	o := BuyOffer{
		ID:              offerID,
		AdvertisementID: advID,
		Buyer:           buyer,
		Amount:          amount,
		Status:          "OPEN",
		Expiry:          expiry,
	}
	return putJSON(ctx, offerKey(offerID), o)
}

func (c *MarketplaceContract) ReadBuyOffer(ctx contractapi.TransactionContextInterface, offerID string) (*BuyOffer, error) {
	b, err := getJSON(ctx, offerKey(offerID))
	if err != nil {
		return nil, err
	}
	if b == nil {
		return nil, fmt.Errorf("buy offer %s not found", offerID)
	}
	var o BuyOffer
	if err := json.Unmarshal(b, &o); err != nil {
		return nil, err
	}
	return &o, nil
}

// Sell accepts an OPEN offer and transfers the asset (SELL).
func (c *MarketplaceContract) Sell(ctx contractapi.TransactionContextInterface, sellID, offerID, seller string) error {
	if sellID == "" || offerID == "" || seller == "" {
		return errors.New("sellID, offerID, seller are required")
	}
	if existing, err := getJSON(ctx, saleKey(sellID)); err != nil {
		return err
	} else if existing != nil {
		return fmt.Errorf("sale %s already exists", sellID)
	}
	if sold, err := getJSON(ctx, soldOfferIndex(offerID)); err != nil {
		return err
	} else if sold != nil {
		return fmt.Errorf("buy offer %s has already been accepted", offerID)
	}
	offer, err := c.ReadBuyOffer(ctx, offerID)
	if err != nil {
		return err
	}
	if offer.Status != "OPEN" {
		return fmt.Errorf("buy offer %s is not open", offerID)
	}
	if offer.Expiry != "" {
		exp, err := time.Parse(time.RFC3339, offer.Expiry)
		if err == nil && exp.Before(time.Now().UTC()) {
			return fmt.Errorf("buy offer %s has expired at %s", offerID, offer.Expiry)
		}
	}
	adv, err := c.ReadAdvertisement(ctx, offer.AdvertisementID)
	if err != nil {
		return err
	}
	if adv.Status != "OPEN" {
		return fmt.Errorf("advertisement %s is not open", adv.ID)
	}
	if adv.Advertiser != seller {
		return errors.New("seller must be the advertiser")
	}
	asset, err := c.ReadAsset(ctx, adv.AssetID)
	if err != nil {
		return err
	}
	if asset.Owner != seller {
		return errors.New("seller no longer owns the asset")
	}

	offer.Status = "ACCEPTED"
	adv.Status = "CLOSED"
	asset.Owner = offer.Buyer
	sale := Sale{
		ID:              sellID,
		OfferID:         offerID,
		AdvertisementID: adv.ID,
		AssetID:         asset.ID,
		Seller:          seller,
		Buyer:           offer.Buyer,
		Amount:          offer.Amount,
		Timestamp:       nowRFC3339(),
	}
	if err := putJSON(ctx, offerKey(offerID), offer); err != nil {
		return err
	}
	if err := putJSON(ctx, advKey(adv.ID), adv); err != nil {
		return err
	}
	if err := putJSON(ctx, assetKey(asset.ID), asset); err != nil {
		return err
	}
	if err := putJSON(ctx, saleKey(sellID), sale); err != nil {
		return err
	}
	if err := ctx.GetStub().PutState(soldOfferIndex(offerID), []byte(sellID)); err != nil {
		return err
	}
	return ctx.GetStub().DelState(openAdvIndex(asset.ID))
}

func (c *MarketplaceContract) ReadSale(ctx contractapi.TransactionContextInterface, sellID string) (*Sale, error) {
	b, err := getJSON(ctx, saleKey(sellID))
	if err != nil {
		return nil, err
	}
	if b == nil {
		return nil, fmt.Errorf("sale %s not found", sellID)
	}
	var s Sale
	if err := json.Unmarshal(b, &s); err != nil {
		return nil, err
	}
	return &s, nil
}

// Transfer moves ownership if the asset is not actively advertised (TRANSFER).
func (c *MarketplaceContract) Transfer(ctx contractapi.TransactionContextInterface, assetID, currentOwner, newOwner string) error {
	if assetID == "" || currentOwner == "" || newOwner == "" {
		return errors.New("assetID, currentOwner, newOwner are required")
	}
	asset, err := c.ReadAsset(ctx, assetID)
	if err != nil {
		return err
	}
	if asset.Owner != currentOwner {
		return errors.New("only the current owner can transfer the asset")
	}
	open, err := getJSON(ctx, openAdvIndex(assetID))
	if err != nil {
		return err
	}
	if open != nil {
		return fmt.Errorf("asset %s has an active advertisement and cannot be transferred", assetID)
	}
	asset.Owner = newOwner
	return putJSON(ctx, assetKey(assetID), asset)
}

// RequestReturn opens a return against a completed sale (REQUEST_RETURN).
func (c *MarketplaceContract) RequestReturn(ctx contractapi.TransactionContextInterface, requestID, sellID, requester, reason string) error {
	if requestID == "" || sellID == "" || requester == "" {
		return errors.New("requestID, sellID, requester are required")
	}
	if existing, err := getJSON(ctx, returnKey(requestID)); err != nil {
		return err
	} else if existing != nil {
		return fmt.Errorf("return request %s already exists", requestID)
	}
	if existingSaleReturn, err := getJSON(ctx, returnBySaleIndex(sellID)); err != nil {
		return err
	} else if existingSaleReturn != nil {
		return fmt.Errorf("a return request already exists for sale %s", sellID)
	}
	sale, err := c.ReadSale(ctx, sellID)
	if err != nil {
		return err
	}
	if sale.Buyer != requester {
		return errors.New("only the buyer can request a return")
	}
	req := ReturnRequest{
		ID:        requestID,
		SaleID:    sellID,
		AssetID:   sale.AssetID,
		Requester: requester,
		Reason:    reason,
		Status:    "OPEN",
		Timestamp: nowRFC3339(),
	}
	if err := putJSON(ctx, returnKey(requestID), req); err != nil {
		return err
	}
	return ctx.GetStub().PutState(returnBySaleIndex(sellID), []byte(requestID))
}

func (c *MarketplaceContract) GetReturnRequestIdBySale(ctx contractapi.TransactionContextInterface, sellID string) (string, error) {
	b, err := getJSON(ctx, returnBySaleIndex(sellID))
	if err != nil {
		return "", err
	}
	if b == nil {
		return "", nil
	}
	return string(b), nil
}

func (c *MarketplaceContract) ReadReturnRequest(ctx contractapi.TransactionContextInterface, requestID string) (*ReturnRequest, error) {
	b, err := getJSON(ctx, returnKey(requestID))
	if err != nil {
		return nil, err
	}
	if b == nil {
		return nil, fmt.Errorf("return request %s not found", requestID)
	}
	var r ReturnRequest
	if err := json.Unmarshal(b, &r); err != nil {
		return nil, err
	}
	return &r, nil
}

func (c *MarketplaceContract) GetAcceptIdByReturn(ctx contractapi.TransactionContextInterface, requestID string) (string, error) {
	b, err := getJSON(ctx, acceptByReturnIndex(requestID))
	if err != nil {
		return "", err
	}
	if b == nil {
		return "", nil
	}
	return string(b), nil
}

// SellerAcceptReturn restores the asset to the seller (SELLER_ACCEPT_RETURN).
func (c *MarketplaceContract) SellerAcceptReturn(ctx contractapi.TransactionContextInterface, acceptID, requestID, seller string) error {
	if acceptID == "" || requestID == "" || seller == "" {
		return errors.New("acceptID, requestID, seller are required")
	}
	if existing, err := getJSON(ctx, acceptKey(acceptID)); err != nil {
		return err
	} else if existing != nil {
		return fmt.Errorf("accept %s already exists", acceptID)
	}
	if already, err := getJSON(ctx, acceptByReturnIndex(requestID)); err != nil {
		return err
	} else if already != nil {
		return fmt.Errorf("a SELLER_ACCEPT_RETURN already exists for REQUEST_RETURN %s", requestID)
	}
	req, err := c.ReadReturnRequest(ctx, requestID)
	if err != nil {
		return err
	}
	if req.Status != "OPEN" {
		return fmt.Errorf("return request %s is not open", requestID)
	}
	sale, err := c.ReadSale(ctx, req.SaleID)
	if err != nil {
		return err
	}
	if sale.Seller != seller {
		return errors.New("only the original seller can accept the return")
	}
	asset, err := c.ReadAsset(ctx, req.AssetID)
	if err != nil {
		return err
	}
	asset.Owner = seller
	req.Status = "ACCEPTED"
	acc := AcceptReturn{
		ID:        acceptID,
		RequestID: requestID,
		SaleID:    sale.ID,
		AssetID:   asset.ID,
		Seller:    seller,
		Timestamp: nowRFC3339(),
	}
	if err := putJSON(ctx, assetKey(asset.ID), asset); err != nil {
		return err
	}
	if err := putJSON(ctx, returnKey(requestID), req); err != nil {
		return err
	}
	if err := putJSON(ctx, acceptKey(acceptID), acc); err != nil {
		return err
	}
	return ctx.GetStub().PutState(acceptByReturnIndex(requestID), []byte(acceptID))
}

func main() {
	cc, err := contractapi.NewChaincode(&MarketplaceContract{})
	if err != nil {
		panic(err)
	}
	if err := cc.Start(); err != nil {
		panic(err)
	}
}
