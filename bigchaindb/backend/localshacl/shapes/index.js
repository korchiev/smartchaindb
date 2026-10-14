// SHACL Validation Microservice with MongoDB Integration
// Comprehensive validation: syntactic, semantic, and state consistency

import express from 'express';
import { Readable } from 'stream';
import fs from 'fs/promises';
import path from 'path';
import { Validator } from 'shacl-engine';
import ParserN3 from '@rdfjs/parser-n3';
import rdfDataset from '@rdfjs/dataset';
import rdfDataModel from '@rdfjs/data-model';
import mongodb from 'mongodb';
import { AsyncLocalStorage } from 'async_hooks';

const SHACL_DEBUG = /^(1|true|yes|on)$/i.test(process.env.SHACL_DEBUG || '');
const dlog = (...args) => { if (SHACL_DEBUG) console.log(...args); };

// Per-request read set: every MongoDB filter the state checks issue is
// recorded so the validator can verify that the facts it read are covered by
// the declared dependency projection (the SHACL+Δ cache key).
const readSetStore = new AsyncLocalStorage();
const HEX64 = /^[0-9a-f]{64}$/;

function recordRead(collectionName, filter) {
  const rs = readSetStore.getStore();
  if (!rs) return;
  rs.queries += 1;
  rs.collections.add(collectionName);
  const walk = (value) => {
    if (Array.isArray(value)) { value.forEach(walk); return; }
    if (value && typeof value === 'object') { Object.values(value).forEach(walk); return; }
    if (typeof value === 'string' && HEX64.test(value)) rs.ids.add(value);
  };
  walk(filter);
}

function tracked(collectionName) {
  const col = db.collection(collectionName);
  return {
    findOne: (filter, ...rest) => { recordRead(collectionName, filter); return col.findOne(filter, ...rest); },
    find: (filter, ...rest) => { recordRead(collectionName, filter); return col.find(filter, ...rest); },
    countDocuments: (filter, ...rest) => { recordRead(collectionName, filter); return col.countDocuments(filter, ...rest); },
  };
}

const { MongoClient } = mongodb;

const app = express();
const port = process.env.PORT || 3000;
const shapesCache = new Map();

// MongoDB connection
let mongoClient = null;
let db = null;

// Middleware to parse JSON bodies
app.use(express.json({ limit: '5mb' }));

// Helper function to parse a Turtle string into an RDF/JS dataset
async function parseTurtle(turtleString) {
  const parser = new ParserN3();
  const stream = Readable.from(turtleString);
  const quads = rdfDataset.dataset(); 
  
  return new Promise((resolve, reject) => {
    parser.import(stream)
      .on('data', quad => quads.add(quad))
      .on('end', () => resolve(quads))
      .on('error', error => reject(error));
  });
}

/**
 * Initialize MongoDB connection
 */
async function initMongoDB() {
    const mongoHost = process.env.MONGO_HOST || 'mongodb';
    const mongoPort = process.env.MONGO_PORT || '27017';
    const mongoUser = process.env.MONGO_USER || 'admin';
    const mongoPassword = process.env.MONGO_PASSWORD || 'admin';
    const mongoDatabase = process.env.MONGO_DATABASE || 'bigchain';
    
    const mongoUrl = `mongodb://${mongoUser}:${mongoPassword}@${mongoHost}:${mongoPort}/?authSource=admin`;
    
    console.log(`Connecting to MongoDB at ${mongoHost}:${mongoPort}...`);
    
    try {
        mongoClient = await MongoClient.connect(mongoUrl, {
            useNewUrlParser: true,
            useUnifiedTopology: true
        });
        db = mongoClient.db(mongoDatabase);
        console.log('✓ MongoDB connected successfully');
        return true;
    } catch (error) {
        console.error('✗ MongoDB connection failed:', error.message);
        console.warn('⚠ Running in SHACL-only mode (no state validation)');
        return false;
    }
}

/**
 * Extract transaction data from parsed RDF dataset
 */
function extractTransactionData(dataset) {
    const data = {
        operation: null,
        id: null,
        asset: { data: {} },
        metadata: {}
    };
    
    for (const quad of dataset) {
        const predicate = quad.predicate.value;
        const value = quad.object.value;
        const predicateName = predicate.split('#')[1] || predicate.split('/').pop();
        
        if (predicateName === 'operation') {
            data.operation = value;
        } else if (predicateName === 'id' && quad.subject.value.startsWith('urn:tx:')) {
            data.id = value;
        } else if (predicateName === 'advertisement_id') {
            // Extract from asset.data
            data.asset.data.advertisement_id = value;
        } else if (predicateName === 'buy_offer_id') {
            // Extract from asset.data
            data.asset.data.buy_offer_id = value;
        } else if (predicateName === 'sell_transaction_id') {
            // Extract from asset.data for REQUEST_RETURN
            data.asset.data.sell_transaction_id = value;
        } else if (predicateName === 'request_return_id') {
            // Extract from asset.data for SELLER_ACCEPT_RETURN
            data.asset.data.request_return_id = value;
        } else if (predicateName === 'id' && quad.subject.value.includes('asset')) {
            // Extract asset.data.id for UPDATE_ADV and other transactions
            data.asset.data.id = value;
        } else if (predicateName === 'id' && quad.subject.termType === 'BlankNode') {
            // Extract asset.data.id from blank nodes (RDF representation)
            data.asset.data.id = value;
        } else if (predicateName === 'asset_id') {
            // For advertisement validation
            data.asset.id = value;
        } else if (predicateName === 'fulfillment') {
            // Extract input fulfillment
            if (!data.inputs) data.inputs = [];
            if (!data.inputs[0]) data.inputs[0] = {};
            data.inputs[0].fulfillment = value;
        } else if (predicateName === 'owners_before') {
            // Extract input owners_before
            if (!data.inputs) data.inputs = [];
            if (!data.inputs[0]) data.inputs[0] = {};
            if (!data.inputs[0].owners_before) data.inputs[0].owners_before = [];
            data.inputs[0].owners_before.push(value);
        } else if (predicateName === 'fulfills') {
            // Extract input fulfills
            if (!data.inputs) data.inputs = [];
            if (!data.inputs[0]) data.inputs[0] = {};
            data.inputs[0].fulfills = value;
        } else if (predicateName === 'amount') {
            // Extract output amount
            if (!data.outputs) data.outputs = [];
            if (!data.outputs[data.outputs.length - 1]) data.outputs.push({});
            data.outputs[data.outputs.length - 1].amount = value;
        } else if (predicateName === 'public_keys') {
            // Extract output public_keys
            if (!data.outputs) data.outputs = [];
            if (!data.outputs[data.outputs.length - 1]) data.outputs.push({});
            if (!data.outputs[data.outputs.length - 1].public_keys) data.outputs[data.outputs.length - 1].public_keys = [];
            data.outputs[data.outputs.length - 1].public_keys.push(value);
        } else if (predicateName === 'type') {
            // Extract condition details type
            if (!data.outputs) data.outputs = [];
            if (!data.outputs[data.outputs.length - 1]) data.outputs.push({});
            if (!data.outputs[data.outputs.length - 1].condition) data.outputs[data.outputs.length - 1].condition = {};
            if (!data.outputs[data.outputs.length - 1].condition.details) data.outputs[data.outputs.length - 1].condition.details = {};
            data.outputs[data.outputs.length - 1].condition.details.type = value;
        } else if (predicateName === 'public_key') {
            // Extract condition details public_key
            if (!data.outputs) data.outputs = [];
            if (!data.outputs[data.outputs.length - 1]) data.outputs.push({});
            if (!data.outputs[data.outputs.length - 1].condition) data.outputs[data.outputs.length - 1].condition = {};
            if (!data.outputs[data.outputs.length - 1].condition.details) data.outputs[data.outputs.length - 1].condition.details = {};
            data.outputs[data.outputs.length - 1].condition.details.public_key = value;
        } else if (predicateName === 'uri') {
            // Extract condition uri
            if (!data.outputs) data.outputs = [];
            if (!data.outputs[data.outputs.length - 1]) data.outputs.push({});
            if (!data.outputs[data.outputs.length - 1].condition) data.outputs[data.outputs.length - 1].condition = {};
            data.outputs[data.outputs.length - 1].condition.uri = value;
        } else if (quad.object.termType === 'Literal') {
            // Extract all other literal values as metadata
            if (!['operation', 'id', 'advertisement_id', 'buy_offer_id', 'asset_id', 'fulfillment', 'owners_before', 'fulfills', 'amount', 'public_keys', 'type', 'public_key', 'uri'].includes(predicateName)) {
                data.metadata[predicateName] = value;
            }
        }
    }
    
    return data;
}

async function metadataFor(txId) {
    const row = await tracked('metadata').findOne({ id: txId });
    return row && row.metadata ? row.metadata : null;
}

function createOwnerKeys(createTx) {
    if (!createTx || !Array.isArray(createTx.outputs) || !createTx.outputs[0]) {
        return [];
    }
    const keys = createTx.outputs[0].public_keys;
    return Array.isArray(keys) ? keys : [];
}

/**
 * Original ADVERTISEMENT metadata stays OPEN. Later UPDATE_ADV txs
 * carry the current status (same overlay Fabric applies in world state).
 */
async function latestAdvertisementStatus(advertisementId, transactions) {
    const orig = await metadataFor(advertisementId);
    let status = orig && orig.status;
    const updates = await transactions.find({
        operation: 'UPDATE_ADV',
        $or: [
            { 'asset.id': advertisementId },
            { 'asset.data.id': advertisementId }
        ]
    }).sort({ _id: 1 }).toArray();
    for (const upd of updates) {
        const meta = await metadataFor(upd.id);
        if (meta && meta.status) {
            status = meta.status;
        }
    }
    return status;
}

/**
 * Validate state consistency using MongoDB queries
 */
async function validateStateConsistency(txData) {
    const errors = [];
    
    if (!db) {
        console.warn('MongoDB not available, skipping state validation');
        return errors;
    }
    
    const transactions = tracked('transactions');
    
    try {
        switch (txData.operation) {
            case 'ADVERTISEMENT':
                await validateAdvertisement(txData, transactions, errors);
                break;
            case 'UPDATE_ADV':
                await validateUpdateAdv(txData, transactions, errors);
                break;
            
            case 'BUY_OFFER':
                await validateBuyOffer(txData, transactions, errors);
                break;
            
            case 'SELL':
                await validateSell(txData, transactions, errors);
                break;
            
            case 'TRANSFER':
                await validateTransfer(txData, transactions, errors);
                break;
            
            case 'REQUEST_RETURN':
                await validateRequestReturn(txData, transactions, errors);
                break;
            
            case 'SELLER_ACCEPT_RETURN':
                await validateSellerAcceptReturn(txData, transactions, errors);
                break;
        }
    } catch (error) {
        console.error('State validation error:', error);
        errors.push({
            message: [`Database error during state validation: ${error.message}`],
            path: null,
            focusNode: null,
            severity: 'Violation'
        });
    }
    
    return errors;
}

/**
 * Validate ADVERTISEMENT transaction state
 */
/**
 * Validate UPDATE_ADV transaction state
 */
async function validateUpdateAdv(txData, transactions, errors) {
    dlog('Validating UPDATE_ADV transaction:', txData.id);
    const advertisementId = txData.asset.data.id;
    if (!advertisementId) {
        dlog('ERROR: asset.data.id is missing');
        errors.push({
            message: ['asset.data.id is required for UPDATE_ADV'],
            path: 'http://bigchaindb.com/ns#id',
            focusNode: `urn:tx:${txData.id}`,
            severity: 'Violation'
        });
        return;
    }

    const adv = await transactions.findOne({ id: advertisementId, operation: 'ADVERTISEMENT' });
    if (!adv) {
        dlog('ERROR: Advertisement not found:', advertisementId);
        errors.push({
            message: [`Advertisement '${advertisementId}' does not exist`],
            path: 'http://bigchaindb.com/ns#id',
            focusNode: `urn:tx:${txData.id}`,
            severity: 'Violation'
        });
        return;
    }

    // Owner check: updater must match advertiser
    const advMeta = await tracked('metadata').findOne({ id: advertisementId });
    const advertiser = advMeta && advMeta.metadata && (advMeta.metadata.advertiser_public_key || advMeta.metadata.seller_public_key);
    const inputOwner = (txData.inputs && txData.inputs[0] && txData.inputs[0].owners_before && txData.inputs[0].owners_before[0]) || null;
    dlog('Advertisement metadata:', advMeta);
    dlog('Advertiser:', advertiser);
    dlog('Input owner:', inputOwner);
    if (!inputOwner || !advertiser || inputOwner !== advertiser) {
        dlog('ERROR: Owner mismatch');
        errors.push({
            message: ['Only the advertiser can update the advertisement'],
            path: 'http://bigchaindb.com/ns#updater_public_key',
            focusNode: `urn:tx:${txData.id}`,
            severity: 'Violation'
        });
    }

    // Status transition check
    const currentStatus = advMeta && advMeta.metadata && advMeta.metadata.status;
    const nextStatus = txData.metadata.status;
    const allowed = { OPEN: ['LOCKED', 'CLOSED'], LOCKED: ['CLOSED'], CLOSED: [] };
    if (nextStatus && currentStatus && !allowed[currentStatus]?.includes(nextStatus) && nextStatus !== currentStatus) {
        errors.push({
            message: [`Invalid status transition ${currentStatus} -> ${nextStatus}`],
            path: 'http://bigchaindb.com/ns#status',
            focusNode: `urn:tx:${txData.id}`,
            severity: 'Violation'
        });
    }

    // Expiry check
    if (txData.metadata.expiry && new Date(txData.metadata.expiry) <= new Date()) {
        errors.push({
            message: ['expiry must be in the future'],
            path: 'http://bigchaindb.com/ns#expiry',
            focusNode: `urn:tx:${txData.id}`,
            severity: 'Violation'
        });
    }
}
async function validateAdvertisement(txData, transactions, errors) {
    // Check if asset exists (if asset.id is provided)
    const assetId = txData.metadata.asset_id || txData.asset.id || (txData.asset.data && txData.asset.data.id);
    
    if (assetId) {
        const asset = await transactions.findOne({
            id: assetId,
            operation: 'CREATE'
        });
        
        if (!asset) {
            errors.push({
                message: [`Asset with id '${assetId}' does not exist`],
                path: 'http://bigchaindb.com/ns#asset',
                focusNode: `urn:tx:${txData.id}`,
                severity: 'Violation'
            });
        } else {
            const advertiser = txData.metadata && txData.metadata.advertiser_public_key;
            const owners = createOwnerKeys(asset);
            if (!advertiser || owners.length === 0 || owners.indexOf(advertiser) === -1) {
                errors.push({
                    message: ['Advertiser must be the original owner of the asset'],
                    path: 'http://bigchaindb.com/ns#advertiser_public_key',
                    focusNode: `urn:tx:${txData.id}`,
                    severity: 'Violation'
                });
            }
        }
        
        // Check if asset is already advertised
        const existingAd = await transactions.findOne({
            operation: 'ADVERTISEMENT',
            'asset.id': assetId,
            'metadata.status': { $in: ['OPEN', 'LOCKED'] }
        });
        
        if (existingAd && existingAd.id !== txData.id) {
            errors.push({
                message: [`Asset '${assetId}' is already advertised (status: ${existingAd.metadata.status})`],
                path: 'http://bigchaindb.com/ns#asset',
                focusNode: `urn:tx:${txData.id}`,
                severity: 'Violation'
            });
        }
    }
}

/**
 * Validate BUY_OFFER transaction state
 */
async function validateBuyOffer(txData, transactions, errors) {
    const advertisementId = txData.asset.data.advertisement_id;
    
    if (!advertisementId) {
        errors.push({
            message: ['advertisement_id is required in asset data'],
            path: 'http://bigchaindb.com/ns#advertisement_id',
            focusNode: `urn:tx:${txData.id}`,
            severity: 'Violation'
        });
        return;
    }
    
    // Check if advertisement exists
    const advertisement = await transactions.findOne({
        id: advertisementId,
        operation: 'ADVERTISEMENT'
    });
    
    if (!advertisement) {
        errors.push({
            message: [`Advertisement with id '${advertisementId}' does not exist`],
            path: 'http://bigchaindb.com/ns#advertisement_id',
            focusNode: `urn:tx:${txData.id}`,
            severity: 'Violation'
        });
        return;
    }
    
    const adAssetId = advertisement.asset && advertisement.asset.id;
    // The asset id arrives as bdb:id on the asset blank node, which the RDF
    // extraction stores under asset.data.id.
    const offerAssetId = txData.asset && (txData.asset.id || (txData.asset.data && txData.asset.data.id));
    if (adAssetId && offerAssetId && offerAssetId !== adAssetId) {
        errors.push({
            message: [`Buy offer asset does not match the advertisement's asset`],
            path: 'http://bigchaindb.com/ns#advertisement_id',
            focusNode: `urn:tx:${txData.id}`,
            severity: 'Violation'
        });
    }

    const status = await latestAdvertisementStatus(advertisementId, transactions);
    if (status !== 'OPEN') {
        errors.push({
            message: [`Advertisement '${advertisementId}' is not open for offers (status: ${status || 'unknown'})`],
            path: 'http://bigchaindb.com/ns#advertisement_id',
            focusNode: `urn:tx:${txData.id}`,
            severity: 'Violation'
        });
    }

    const adMeta = await metadataFor(advertisementId);
    const advertiser = adMeta && adMeta.advertiser_public_key;
    const buyer = txData.metadata && txData.metadata.buyer_public_key;
    if (buyer && advertiser && buyer === advertiser) {
        errors.push({
            message: ['Buyer cannot be the same as advertiser'],
            path: 'http://bigchaindb.com/ns#buyer_public_key',
            focusNode: `urn:tx:${txData.id}`,
            severity: 'Violation'
        });
    }
    
    // Check if offer has expired
    const offerExpiry = txData.metadata.offer_expiry;
    if (offerExpiry && new Date(offerExpiry) < new Date()) {
        errors.push({
            message: [`Offer has already expired at ${offerExpiry}`],
            path: 'http://bigchaindb.com/ns#offer_expiry',
            focusNode: `urn:tx:${txData.id}`,
            severity: 'Violation'
        });
    }
    
    // Check if payment_asset_id exists (if provided)
    const paymentAssetId = txData.metadata.payment_asset_id;
    if (paymentAssetId) {
        const paymentAsset = await transactions.findOne({
            id: paymentAssetId
        });
        
        if (!paymentAsset) {
            errors.push({
                message: [`Payment asset '${paymentAssetId}' does not exist`],
                path: 'http://bigchaindb.com/ns#payment_asset_id',
                focusNode: `urn:tx:${txData.id}`,
                severity: 'Violation'
            });
        }
    }
}

/**
 * Validate SELL transaction state
 */
async function validateSell(txData, transactions, errors) {
    dlog('Validating SELL transaction:', txData.id);
    const buyOfferId = txData.asset.data.buy_offer_id;
    
    if (!buyOfferId) {
        dlog('ERROR: buy_offer_id is missing');
        errors.push({
            message: ['buy_offer_id is required in asset data'],
            path: 'http://bigchaindb.com/ns#buy_offer_id',
            focusNode: `urn:tx:${txData.id}`,
            severity: 'Violation'
        });
        return;
    }
    
    // Check if buy offer exists
    const buyOffer = await transactions.findOne({
        id: buyOfferId,
        operation: 'BUY_OFFER'
    });
    
    if (!buyOffer) {
        dlog('ERROR: Buy offer not found:', buyOfferId);
        errors.push({
            message: [`Buy offer with id '${buyOfferId}' does not exist`],
            path: 'http://bigchaindb.com/ns#buy_offer_id',
            focusNode: `urn:tx:${txData.id}`,
            severity: 'Violation'
        });
        return;
    }
    
    dlog('Buy offer found:', buyOffer.id);
    
    // Get buy offer metadata from separate collection
    const buyOfferMetadata = await tracked('metadata').findOne({
        id: buyOfferId
    });
    
    if (!buyOfferMetadata || !buyOfferMetadata.metadata) {
        errors.push({
            message: [`Buy offer '${buyOfferId}' has no metadata`],
            path: 'http://bigchaindb.com/ns#buy_offer_id',
            focusNode: `urn:tx:${txData.id}`,
            severity: 'Violation'
        });
        return;
    }
    
    // Check if buy offer has expired
    const offerExpiry = buyOfferMetadata.metadata.offer_expiry;
    if (offerExpiry && new Date(offerExpiry) < new Date()) {
        errors.push({
            message: [`Buy offer '${buyOfferId}' has expired at ${offerExpiry}`],
            path: 'http://bigchaindb.com/ns#buy_offer_id',
            focusNode: `urn:tx:${txData.id}`,
            severity: 'Violation'
        });
    }
    
    // Verify sale amount matches offer amount
    const saleAmount = txData.metadata.sale_amount;
    const offerAmount = buyOfferMetadata.metadata.offer_amount;
    
    if (saleAmount !== offerAmount) {
        errors.push({
            message: [`Sale amount (${saleAmount}) does not match buy offer amount (${offerAmount})`],
            path: 'http://bigchaindb.com/ns#sale_amount',
            focusNode: `urn:tx:${txData.id}`,
            severity: 'Violation'
        });
    }
    
    // Check if asset has already been sold
    const existingSale = await transactions.findOne({
        operation: 'SELL',
        'asset.data.buy_offer_id': buyOfferId
    });
    
    if (existingSale && existingSale.id !== txData.id) {
        errors.push({
            message: [`Buy offer '${buyOfferId}' has already been accepted by another SELL transaction`],
            path: 'http://bigchaindb.com/ns#buy_offer_id',
            focusNode: `urn:tx:${txData.id}`,
            severity: 'Violation'
        });
    }

    const offerAsset = buyOffer.asset || {};
    const offerData = offerAsset.data || {};
    const advertisementId = offerAsset.advertisement_id || offerData.advertisement_id;
    if (advertisementId) {
        const adMetaForSell = await metadataFor(advertisementId);
        const seller = txData.metadata && txData.metadata.seller_public_key;
        const advertiser = adMetaForSell && adMetaForSell.advertiser_public_key;
        if (seller && advertiser && seller !== advertiser) {
            errors.push({
                message: ['Seller must be the advertiser (current owner) of the asset'],
                path: 'http://bigchaindb.com/ns#seller_public_key',
                focusNode: `urn:tx:${txData.id}`,
                severity: 'Violation'
            });
        }
        const adStatus = await latestAdvertisementStatus(advertisementId, transactions);
        if (adStatus === 'LOCKED' || adStatus === 'CLOSED') {
            errors.push({
                message: [`Cannot sell asset with advertisement status ${adStatus}`],
                path: 'http://bigchaindb.com/ns#buy_offer_id',
                focusNode: `urn:tx:${txData.id}`,
                severity: 'Violation'
            });
        }
    }
}

/**
 * Validate TRANSFER transaction state
 */
async function validateTransfer(txData, transactions, errors) {
    // Check if asset being transferred exists
    const assetId = txData.asset.id;
    
    if (assetId) {
        const asset = await transactions.findOne({
            id: assetId
        });
        
        if (!asset) {
            errors.push({
                message: [`Asset with id '${assetId}' does not exist`],
                path: 'http://bigchaindb.com/ns#asset',
                focusNode: `urn:tx:${txData.id}`,
                severity: 'Violation'
            });
        }
    }
}

/**
 * Validate REQUEST_RETURN transaction state
 */
async function validateRequestReturn(txData, transactions, errors) {
    dlog('Validating REQUEST_RETURN transaction:', txData.id);
    const sellTransactionId = txData.asset.data.sell_transaction_id;
    
    if (!sellTransactionId) {
        dlog('ERROR: sell_transaction_id is missing');
        errors.push({
            message: ['sell_transaction_id is required in asset'],
            path: 'http://bigchaindb.com/ns#sell_transaction_id',
            focusNode: `urn:tx:${txData.id}`,
            severity: 'Violation'
        });
        return;
    }
    
    // Check if sell transaction exists
    const sellTransaction = await transactions.findOne({
        id: sellTransactionId,
        operation: 'SELL'
    });
    
    if (!sellTransaction) {
        dlog('ERROR: Sell transaction not found:', sellTransactionId);
        errors.push({
            message: [`Sell transaction with id '${sellTransactionId}' does not exist`],
            path: 'http://bigchaindb.com/ns#sell_transaction_id',
            focusNode: `urn:tx:${txData.id}`,
            severity: 'Violation'
        });
        return;
    }
    
    dlog('Sell transaction found:', sellTransaction.id);
    
    // Get sell transaction metadata
    const sellMetadata = await tracked('metadata').findOne({
        id: sellTransactionId
    });
    
    if (!sellMetadata || !sellMetadata.metadata) {
        dlog('ERROR: Sell transaction metadata not found for:', sellTransactionId);
        errors.push({
            message: [`Sell transaction '${sellTransactionId}' has no metadata`],
            path: 'http://bigchaindb.com/ns#sell_transaction_id',
            focusNode: `urn:tx:${txData.id}`,
            severity: 'Violation'
        });
        return;
    }
    
    const requester = txData.metadata && txData.metadata.requester_public_key;
    const buyer = sellMetadata.metadata.buyer_public_key;
    if (requester && buyer && requester !== buyer) {
        errors.push({
            message: ['Requester must be the buyer of the sale'],
            path: 'http://bigchaindb.com/ns#requester_public_key',
            focusNode: `urn:tx:${txData.id}`,
            severity: 'Violation'
        });
    }

    // Check if return is within the return window
    const returnRequestTimestamp = txData.metadata.return_request_timestamp;
    const saleTimestamp = sellMetadata.metadata.sale_timestamp;
    const returnWindowDays = txData.metadata.return_policy_details?.return_window_days || 30;
    
    if (returnRequestTimestamp && saleTimestamp) {
        const requestDate = new Date(returnRequestTimestamp);
        const saleDate = new Date(saleTimestamp);
        const daysDiff = (requestDate - saleDate) / (1000 * 60 * 60 * 24);
        
        dlog('Return request days after sale:', daysDiff, 'Window:', returnWindowDays);
        
        if (daysDiff > returnWindowDays) {
            dlog('ERROR: Return request exceeds return window');
            errors.push({
                message: [`Return request is ${daysDiff.toFixed(1)} days after sale, exceeds ${returnWindowDays} day window`],
                path: 'http://bigchaindb.com/ns#return_request_timestamp',
                focusNode: `urn:tx:${txData.id}`,
                severity: 'Violation'
            });
        }
    }
    
    // Check if a return request already exists for this sell transaction
    const existingReturnRequest = await transactions.findOne({
        operation: 'REQUEST_RETURN',
        'asset.data.sell_transaction_id': sellTransactionId
    });
    
    if (existingReturnRequest && existingReturnRequest.id !== txData.id) {
        dlog('ERROR: Return request already exists for sell transaction:', sellTransactionId);
        errors.push({
            message: [`A return request already exists for sell transaction '${sellTransactionId}'`],
            path: 'http://bigchaindb.com/ns#sell_transaction_id',
            focusNode: `urn:tx:${txData.id}`,
            severity: 'Violation'
        });
    }
}

/**
 * Validate SELLER_ACCEPT_RETURN transaction state
 */
async function validateSellerAcceptReturn(txData, transactions, errors) {
    dlog('Validating SELLER_ACCEPT_RETURN transaction:', txData.id);
    const requestReturnId = txData.asset.data.request_return_id;
    
    if (!requestReturnId) {
        dlog('ERROR: request_return_id is missing');
        errors.push({
            message: ['request_return_id is required in asset'],
            path: 'http://bigchaindb.com/ns#request_return_id',
            focusNode: `urn:tx:${txData.id}`,
            severity: 'Violation'
        });
        return;
    }
    
    // Check if REQUEST_RETURN transaction exists
    const requestReturnTransaction = await transactions.findOne({
        id: requestReturnId,
        operation: 'REQUEST_RETURN'
    });
    
    if (!requestReturnTransaction) {
        dlog('ERROR: REQUEST_RETURN transaction not found:', requestReturnId);
        errors.push({
            message: [`REQUEST_RETURN transaction with id '${requestReturnId}' does not exist`],
            path: 'http://bigchaindb.com/ns#request_return_id',
            focusNode: `urn:tx:${txData.id}`,
            severity: 'Violation'
        });
        return;
    }
    
    dlog('REQUEST_RETURN transaction found:', requestReturnTransaction.id);
    
    // Get REQUEST_RETURN metadata
    const requestReturnMetadata = await tracked('metadata').findOne({
        id: requestReturnId
    });
    
    if (!requestReturnMetadata || !requestReturnMetadata.metadata) {
        dlog('ERROR: REQUEST_RETURN metadata not found for:', requestReturnId);
        errors.push({
            message: [`REQUEST_RETURN transaction '${requestReturnId}' has no metadata`],
            path: 'http://bigchaindb.com/ns#request_return_id',
            focusNode: `urn:tx:${txData.id}`,
            severity: 'Violation'
        });
        return;
    }
    
    const returnAsset = requestReturnTransaction.asset || {};
    const returnData = returnAsset.data || {};
    const acceptedSellId = returnData.sell_transaction_id || returnAsset.sell_transaction_id;
    if (acceptedSellId) {
        const acceptedSellMeta = await tracked('metadata').findOne({ id: acceptedSellId });
        const acceptor = txData.metadata && txData.metadata.seller_public_key;
        const saleSeller = acceptedSellMeta && acceptedSellMeta.metadata && acceptedSellMeta.metadata.seller_public_key;
        if (acceptor && saleSeller && acceptor !== saleSeller) {
            errors.push({
                message: ['Only the seller of the sale can accept the return'],
                path: 'http://bigchaindb.com/ns#seller_public_key',
                focusNode: `urn:tx:${txData.id}`,
                severity: 'Violation'
            });
        }
    }

    // Check if a SELLER_ACCEPT_RETURN already exists for this REQUEST_RETURN
    const existingSellerAcceptReturn = await transactions.findOne({
        operation: 'SELLER_ACCEPT_RETURN',
        'asset.data.request_return_id': requestReturnId
    });
    
    if (existingSellerAcceptReturn && existingSellerAcceptReturn.id !== txData.id) {
        dlog('ERROR: SELLER_ACCEPT_RETURN already exists for REQUEST_RETURN:', requestReturnId);
        errors.push({
            message: [`A SELLER_ACCEPT_RETURN already exists for REQUEST_RETURN '${requestReturnId}'`],
            path: 'http://bigchaindb.com/ns#request_return_id',
            focusNode: `urn:tx:${txData.id}`,
            severity: 'Violation'
        });
    }
}

/**
 * Loads all .ttl files from the './shapes' directory into memory.
 */
async function loadShapes() {
    const shapesDir = path.resolve('shapes');
    console.log(`Looking for shapes in: ${shapesDir}`);
    try {
        const files = await fs.readdir(shapesDir);
        const turtleFiles = files.filter(file => file.endsWith('.ttl'));

        if (turtleFiles.length === 0) {
            console.warn('No .ttl files found in the shapes directory.');
            return;
        }

        for (const file of turtleFiles) {
            const shapeType = path.basename(file, '.ttl');
            const filePath = path.join(shapesDir, file);
            const fileContent = await fs.readFile(filePath, 'utf-8');
            const shapeDataset = await parseTurtle(fileContent);
            shapesCache.set(shapeType, shapeDataset);
            console.log(`-> Loaded shape: ${shapeType}`);
        }
    } catch (error) {
        if (error.code === 'ENOENT') {
            console.error(`Error: The './shapes' directory was not found. Please create it.`);
        } else {
            console.error('Error loading shapes:', error);
        }
        process.exit(1);
    }
}

// Simple route for health checks
app.get('/', (req, res) => {
  res.json({ 
      message: 'SHACL validation server with MongoDB integration is running',
      loaded_shapes: [...shapesCache.keys()],
      mongodb_connected: db !== null,
      validation_mode: db ? 'Full (SHACL + State)' : 'SHACL-only'
  });
});

// Validation endpoint

app.post('/validate', async (req, res) => {
  const { shapeType, data } = req.body;
  const tStart = process.hrtime.bigint();
  const msSince = (t) => Number(process.hrtime.bigint() - t) / 1e6;

  if (SHACL_DEBUG) {
    console.log('=== SHACL Validation Request ===');
    console.log('Shape Type:', shapeType);
    console.log('RDF Data received:');
    console.log(data);
    console.log('================================');
  }

  if (!shapeType || !data) {
    return res.status(400).json({ error: 'Request body must contain "shapeType" and "data" properties.' });
  }

  const shapesDataset = shapesCache.get(shapeType);

  if (!shapesDataset) {
      return res.status(404).json({ 
          error: `Shape type "${shapeType}" not found.`,
          available_shapes: [...shapesCache.keys()]
      });
  }

  try {
    // ═══════════════════════════════════════════════════════
    // Phase 1: SHACL Syntactic & Semantic Validation
    // ═══════════════════════════════════════════════════════
    const tParse = process.hrtime.bigint();
    const dataDataset = await parseTurtle(data);
    const parseMs = msSince(tParse);
    
    if (SHACL_DEBUG) {
      console.log('=== Parsed RDF Dataset ===');
      console.log('Dataset size:', dataDataset.size);
      for (const quad of dataDataset) {
        console.log(`Subject: ${quad.subject.value}, Predicate: ${quad.predicate.value}, Object: ${quad.object.value}`);
      }
      console.log('==========================');
    }
    
    const tShacl = process.hrtime.bigint();
    const validator = new Validator(shapesDataset, { factory: rdfDataModel });
    const report = await validator.validate({ dataset: dataDataset });
    const shaclMs = msSince(tShacl);

    let results = report.results.map(result => ({
        message: result.message.map(m => m.value),
        path: result.path ? result.path.value : null,
        focusNode: result.focusNode ? result.focusNode.value : null,
        severity: result.severity ? result.severity.value : null,
        sourceConstraintComponent: result.sourceConstraintComponent ? result.sourceConstraintComponent.value : null,
        sourceShape: result.sourceShape ? result.sourceShape.value : null,
    }));

    // Track overall conformance (can't modify report.conforms directly)
    let conforms = report.conforms;

    // ═══════════════════════════════════════════════════════
    // Phase 2: State Consistency Validation (MongoDB)
    // ═══════════════════════════════════════════════════════
    let stateMs = 0;
    const readSet = { ids: new Set(), queries: 0, collections: new Set() };
    if (conforms && db) {
        const tState = process.hrtime.bigint();
        const txData = extractTransactionData(dataDataset);
        const stateErrors = await readSetStore.run(readSet, () => validateStateConsistency(txData));
        stateMs = msSince(tState);
        
        if (stateErrors.length > 0) {
            results = results.concat(stateErrors);
            conforms = false;
        }
    }

    res.json({
      conforms: conforms,
      results,
      validation_phases: {
          shacl: 'completed',
          state: db ? 'completed' : 'skipped'
      },
      read_set: {
          tx_ids: [...readSet.ids],
          queries: readSet.queries,
          collections: [...readSet.collections]
      },
      timings_ms: {
          parse: parseMs,
          shacl: shaclMs,
          state: stateMs,
          total: msSince(tStart)
      }
    });

  } catch (error) {
    console.error('Validation Error:', error);
    res.status(500).json({ error: 'An error occurred during validation.', details: error.message });
  }
});

/**
 * Main function to start the server after loading shapes and connecting to MongoDB.
 */
async function startServer() {
    await loadShapes();
    await initMongoDB();
    
    app.listen(port, () => {
      console.log(`\n${'='.repeat(60)}`);
      console.log(`🚀 SHACL Validation Service Running`);
      console.log(`${'='.repeat(60)}`);
      console.log(`   Port:            ${port}`);
      console.log(`   Loaded Shapes:   ${[...shapesCache.keys()].join(', ') || 'None'}`);
      console.log(`   MongoDB:         ${db ? '✓ Connected' : '✗ Not Connected'}`);
      console.log(`   Validation Mode: ${db ? 'Full (SHACL + State)' : 'SHACL-only'}`);
      console.log(`${'='.repeat(60)}\n`);
    });
}

// Handle graceful shutdown
process.on('SIGTERM', async () => {
    console.log('SIGTERM received, closing MongoDB connection...');
    if (mongoClient) {
        await mongoClient.close();
    }
    process.exit(0);
});

startServer();
