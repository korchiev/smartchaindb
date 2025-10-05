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
    const mongoPassword = process.env.MONGO_PASSWORD || 'password';
    const mongoDatabase = process.env.MONGO_DATABASE || 'bigchain';
    
    const mongoUrl = `mongodb://${mongoUser}:${mongoPassword}@${mongoHost}:${mongoPort}`;
    
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

/**
 * Validate state consistency using MongoDB queries
 */
async function validateStateConsistency(txData) {
    const errors = [];
    
    if (!db) {
        console.warn('MongoDB not available, skipping state validation');
        return errors;
    }
    
    const transactions = db.collection('transactions');
    
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
    console.log('Validating UPDATE_ADV transaction:', txData.id);
    const advertisementId = txData.asset.data.id;
    if (!advertisementId) {
        console.log('ERROR: asset.data.id is missing');
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
        console.log('ERROR: Advertisement not found:', advertisementId);
        errors.push({
            message: [`Advertisement '${advertisementId}' does not exist`],
            path: 'http://bigchaindb.com/ns#id',
            focusNode: `urn:tx:${txData.id}`,
            severity: 'Violation'
        });
        return;
    }

    // Owner check: updater must match advertiser
    const advMeta = await db.collection('metadata').findOne({ id: advertisementId });
    const advertiser = advMeta && advMeta.metadata && (advMeta.metadata.advertiser_public_key || advMeta.metadata.seller_public_key);
    const inputOwner = (txData.inputs && txData.inputs[0] && txData.inputs[0].owners_before && txData.inputs[0].owners_before[0]) || null;
    console.log('Advertisement metadata:', advMeta);
    console.log('Advertiser:', advertiser);
    console.log('Input owner:', inputOwner);
    if (!inputOwner || !advertiser || inputOwner !== advertiser) {
        console.log('ERROR: Owner mismatch');
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
    const assetId = txData.metadata.asset_id || txData.asset.id;
    
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
    
    // BigchainDB stores metadata in a separate collection
    const metadata = await db.collection('metadata').findOne({
        id: advertisementId
    });
    
    if (metadata && metadata.metadata && metadata.metadata.status !== 'OPEN') {
        errors.push({
            message: [`Advertisement '${advertisementId}' is not open for offers (status: ${metadata.metadata.status})`],
            path: 'http://bigchaindb.com/ns#advertisement_id',
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
    console.log('Validating SELL transaction:', txData.id);
    const buyOfferId = txData.asset.data.buy_offer_id;
    
    if (!buyOfferId) {
        console.log('ERROR: buy_offer_id is missing');
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
        console.log('ERROR: Buy offer not found:', buyOfferId);
        errors.push({
            message: [`Buy offer with id '${buyOfferId}' does not exist`],
            path: 'http://bigchaindb.com/ns#buy_offer_id',
            focusNode: `urn:tx:${txData.id}`,
            severity: 'Violation'
        });
        return;
    }
    
    console.log('Buy offer found:', buyOffer.id);
    
    // Get buy offer metadata from separate collection
    const buyOfferMetadata = await db.collection('metadata').findOne({
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
    console.log('Validating REQUEST_RETURN transaction:', txData.id);
    const sellTransactionId = txData.asset.data.sell_transaction_id;
    
    if (!sellTransactionId) {
        console.log('ERROR: sell_transaction_id is missing');
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
        console.log('ERROR: Sell transaction not found:', sellTransactionId);
        errors.push({
            message: [`Sell transaction with id '${sellTransactionId}' does not exist`],
            path: 'http://bigchaindb.com/ns#sell_transaction_id',
            focusNode: `urn:tx:${txData.id}`,
            severity: 'Violation'
        });
        return;
    }
    
    console.log('Sell transaction found:', sellTransaction.id);
    
    // Get sell transaction metadata
    const sellMetadata = await db.collection('metadata').findOne({
        id: sellTransactionId
    });
    
    if (!sellMetadata || !sellMetadata.metadata) {
        console.log('ERROR: Sell transaction metadata not found for:', sellTransactionId);
        errors.push({
            message: [`Sell transaction '${sellTransactionId}' has no metadata`],
            path: 'http://bigchaindb.com/ns#sell_transaction_id',
            focusNode: `urn:tx:${txData.id}`,
            severity: 'Violation'
        });
        return;
    }
    
    // Check if return is within the return window
    const returnRequestTimestamp = txData.metadata.return_request_timestamp;
    const saleTimestamp = sellMetadata.metadata.sale_timestamp;
    const returnWindowDays = txData.metadata.return_policy_details?.return_window_days || 30;
    
    if (returnRequestTimestamp && saleTimestamp) {
        const requestDate = new Date(returnRequestTimestamp);
        const saleDate = new Date(saleTimestamp);
        const daysDiff = (requestDate - saleDate) / (1000 * 60 * 60 * 24);
        
        console.log('Return request days after sale:', daysDiff, 'Window:', returnWindowDays);
        
        if (daysDiff > returnWindowDays) {
            console.log('ERROR: Return request exceeds return window');
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
        console.log('ERROR: Return request already exists for sell transaction:', sellTransactionId);
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
    console.log('Validating SELLER_ACCEPT_RETURN transaction:', txData.id);
    const requestReturnId = txData.asset.data.request_return_id;
    
    if (!requestReturnId) {
        console.log('ERROR: request_return_id is missing');
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
        console.log('ERROR: REQUEST_RETURN transaction not found:', requestReturnId);
        errors.push({
            message: [`REQUEST_RETURN transaction with id '${requestReturnId}' does not exist`],
            path: 'http://bigchaindb.com/ns#request_return_id',
            focusNode: `urn:tx:${txData.id}`,
            severity: 'Violation'
        });
        return;
    }
    
    console.log('REQUEST_RETURN transaction found:', requestReturnTransaction.id);
    
    // Get REQUEST_RETURN metadata
    const requestReturnMetadata = await db.collection('metadata').findOne({
        id: requestReturnId
    });
    
    if (!requestReturnMetadata || !requestReturnMetadata.metadata) {
        console.log('ERROR: REQUEST_RETURN metadata not found for:', requestReturnId);
        errors.push({
            message: [`REQUEST_RETURN transaction '${requestReturnId}' has no metadata`],
            path: 'http://bigchaindb.com/ns#request_return_id',
            focusNode: `urn:tx:${txData.id}`,
            severity: 'Violation'
        });
        return;
    }
    
    // Check if a SELLER_ACCEPT_RETURN already exists for this REQUEST_RETURN
    const existingSellerAcceptReturn = await transactions.findOne({
        operation: 'SELLER_ACCEPT_RETURN',
        'asset.data.request_return_id': requestReturnId
    });
    
    if (existingSellerAcceptReturn && existingSellerAcceptReturn.id !== txData.id) {
        console.log('ERROR: SELLER_ACCEPT_RETURN already exists for REQUEST_RETURN:', requestReturnId);
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

  console.log('=== SHACL Validation Request ===');
  console.log('Shape Type:', shapeType);
  console.log('RDF Data received:');
  console.log(data);
  console.log('================================');

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
    const dataDataset = await parseTurtle(data);
    
    console.log('=== Parsed RDF Dataset ===');
    console.log('Dataset size:', dataDataset.size);
    for (const quad of dataDataset) {
      console.log(`Subject: ${quad.subject.value}, Predicate: ${quad.predicate.value}, Object: ${quad.object.value}`);
    }
    console.log('==========================');
    
    const validator = new Validator(shapesDataset, { factory: rdfDataModel });
    const report = await validator.validate({ dataset: dataDataset });

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
    if (conforms && db) {
        const txData = extractTransactionData(dataDataset);
        const stateErrors = await validateStateConsistency(txData);
        
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
