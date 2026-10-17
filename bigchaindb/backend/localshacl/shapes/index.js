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
import { validateState } from './state_validator.js';
import { extractTransactionData } from './transaction_graph.js';

const SHACL_DEBUG = /^(1|true|yes|on)$/i.test(process.env.SHACL_DEBUG || '');
const dlog = (...args) => { if (SHACL_DEBUG) console.log(...args); };

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
        console.warn('State validation unavailable; requests will be rejected');
        return false;
    }
}

/**
 * Extract transaction data from parsed RDF dataset
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
  res.status(db ? 200 : 503).json({
      message: 'SHACL validation server with MongoDB integration is running',
      loaded_shapes: [...shapesCache.keys()],
      mongodb_connected: db !== null,
      validation_mode: db ? 'Full (SHACL + State)' : 'Unavailable'
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

  if (!db) return res.status(503).json({ error: 'Ledger state is unavailable' });

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
    let stateReadSet = { tx_ids: [], queries: 0, collections: [] };
    let validUntil = null;
    if (conforms && db) {
        const tState = process.hrtime.bigint();
        const txData = extractTransactionData(dataDataset, shapeType);
        const state = await validateState(txData, {db,
            pendingTransactions: req.body.pendingTransactions || [],
            validationTime: req.body.validationTime});
        const stateErrors = state.errors;
        stateReadSet = state.read_set;
        validUntil = state.valid_until;
        stateMs = msSince(tState);

        if (stateErrors.length > 0) {
            results = results.concat(stateErrors);
            conforms = false;
        }
    }

    res.json({
      validation_protocol: 2,
      conforms: conforms,
      results,
      validation_phases: {
          shacl: 'completed',
          state: conforms ? 'completed' : (stateMs ? 'completed' : 'not_required')
      },
      read_set: stateReadSet,
      valid_until: validUntil,
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
