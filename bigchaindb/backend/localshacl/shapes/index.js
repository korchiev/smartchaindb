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
        asset: {},
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
            data.asset.advertisement_id = value;
        } else if (predicateName === 'buy_offer_id') {
            // Extract from asset.data
            data.asset.buy_offer_id = value;
        } else if (predicateName === 'asset_id') {
            // For advertisement validation
            data.asset.id = value;
        } else if (quad.object.termType === 'Literal') {
            // Extract all other literal values as metadata
            if (!['operation', 'id', 'advertisement_id', 'buy_offer_id', 'asset_id'].includes(predicateName)) {
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
            
            case 'BUY_OFFER':
                await validateBuyOffer(txData, transactions, errors);
                break;
            
            case 'SELL':
                await validateSell(txData, transactions, errors);
                break;
            
            case 'TRANSFER':
                await validateTransfer(txData, transactions, errors);
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
    const advertisementId = txData.asset.advertisement_id;
    
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
    const buyOfferId = txData.asset.buy_offer_id;
    
    if (!buyOfferId) {
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
        errors.push({
            message: [`Buy offer with id '${buyOfferId}' does not exist`],
            path: 'http://bigchaindb.com/ns#buy_offer_id',
            focusNode: `urn:tx:${txData.id}`,
            severity: 'Violation'
        });
        return;
    }
    
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
