import fs from 'fs';
import path from 'path';
import { Gateway, Wallets } from 'fabric-network';
import fetch from 'node-fetch';
import yargs from 'yargs';
import { hideBin } from 'yargs/helpers';

const args = yargs(hideBin(process.argv))
  .command('submit <fn>', 'Submit a marketplace transaction', (y) => {
    y.positional('fn', { describe: 'Chaincode function name', type: 'string' });
  })
  .option('payload', { type: 'string', default: '{}', describe: 'JSON payload' })
  .option('use-shacl', { type: 'boolean', default: false, describe: 'SHACL pre-validate using world state' })
  .help().argv;

const SHACL_ENDPOINT = process.env.SHACL_ENDPOINT || 'http://localhost:3001';
const METRICS_PATH = path.resolve('metrics.fabric.jsonl');

function nowMs() {
  return Date.now();
}

function logMetric(kind, obj) {
  fs.appendFileSync(METRICS_PATH, JSON.stringify({ ts: new Date().toISOString(), kind, ...obj }) + '\n');
}

function lit(v) {
  if (typeof v === 'boolean') return v ? 'true' : 'false';
  if (typeof v === 'number') return String(v);
  return `"${String(v).replace(/\\/g, '\\\\').replace(/"/g, '\\"')}"`;
}

function buildTurtle(operation, facts) {
  const id = facts.txId || facts.assetId || facts.advId || facts.offerId || facts.sellId || facts.requestId || 'tx';
  let ttl = '@prefix fabric: <http://smartchaindb.org/fabric#> .\n@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .\n\n';
  ttl += `<urn:tx:${id}> a fabric:${operation} ;\n`;
  ttl += `  fabric:operation "${operation}" ;\n`;
  for (const [k, v] of Object.entries(facts)) {
    if (v === undefined || v === null || k === 'txId') continue;
    ttl += `  fabric:${k} ${lit(v)} ;\n`;
  }
  return ttl.replace(/;\n$/, ' .\n');
}

async function shaclValidate(operation, facts) {
  const data = buildTurtle(operation, facts);
  const t0 = nowMs();
  const res = await fetch(`${SHACL_ENDPOINT}/validate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ shapeType: operation, data }),
  });
  const duration = nowMs() - t0;
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`SHACL service error ${res.status}: ${text}`);
  }
  const body = await res.json();
  logMetric('shacl_prevalidate', { operation, conforms: !!body.conforms, duration_ms: duration });
  return { ...body, duration_ms: duration, turtle: data };
}

async function safeEvaluate(contract, fn, ...fnArgs) {
  try {
    const buf = await contract.evaluateTransaction(fn, ...fnArgs);
    const text = buf.toString();
    if (!text) return null;
    try {
      return JSON.parse(text);
    } catch {
      return text;
    }
  } catch (e) {
    const msg = e && e.message ? e.message : String(e);
    if (!/not found|query failed/i.test(msg)) {
      console.error(`evaluate ${fn}(${fnArgs.join(',')}) failed:`, msg);
    }
    return null;
  }
}

async function gatherStateFacts(contract, fn, payload) {
  const facts = { ...payload };
  switch (fn) {
    case 'CreateAsset': {
      const asset = await safeEvaluate(contract, 'ReadAsset', payload.assetId);
      facts.assetExists = !!asset;
      break;
    }
    case 'CreateAdvertisement': {
      const asset = await safeEvaluate(contract, 'ReadAsset', payload.assetId);
      facts.assetExists = !!asset;
      facts.advertiserIsOwner = !!(asset && asset.owner === payload.advertiser);
      facts.status = payload.status || 'OPEN';
      const openAdvId = await safeEvaluate(contract, 'GetOpenAdvertisementId', payload.assetId);
      facts.hasOpenAdvertisement = !!(openAdvId && String(openAdvId).length > 0);
      break;
    }
    case 'UpdateAdvertisement': {
      const adv = await safeEvaluate(contract, 'ReadAdvertisement', payload.advId);
      facts.advertisementExists = !!adv;
      facts.updaterIsAdvertiser = !!(adv && adv.advertiser === payload.updater);
      const current = adv ? adv.status : '';
      const next = payload.nextStatus || current;
      const allowed = { OPEN: ['LOCKED', 'CLOSED', 'OPEN'], LOCKED: ['CLOSED', 'LOCKED'], CLOSED: ['CLOSED'] };
      facts.validStatusTransition = !!(adv && allowed[current] && allowed[current].includes(next));
      break;
    }
    case 'SubmitBuyOffer': {
      const adv = await safeEvaluate(contract, 'ReadAdvertisement', payload.advId);
      facts.advertisementExists = !!adv;
      facts.advertisementOpen = !!(adv && adv.status === 'OPEN');
      break;
    }
    case 'Sell': {
      const offer = await safeEvaluate(contract, 'ReadBuyOffer', payload.offerId);
      facts.offerExists = !!offer;
      facts.offerOpen = !!(offer && offer.status === 'OPEN');
      facts.offerAlreadySold = !!(offer && offer.status === 'ACCEPTED');
      let adv = null;
      let asset = null;
      if (offer) {
        adv = await safeEvaluate(contract, 'ReadAdvertisement', offer.advertisement_id);
        if (adv) asset = await safeEvaluate(contract, 'ReadAsset', adv.asset_id);
      }
      facts.advertisementOpen = !!(adv && adv.status === 'OPEN');
      facts.sellerIsAdvertiser = !!(adv && adv.advertiser === payload.seller);
      facts.sellerOwnsAsset = !!(asset && asset.owner === payload.seller);
      break;
    }
    case 'Transfer': {
      const asset = await safeEvaluate(contract, 'ReadAsset', payload.assetId);
      facts.assetExists = !!asset;
      facts.ownerMatches = !!(asset && asset.owner === payload.currentOwner);
      const openAdvId = await safeEvaluate(contract, 'GetOpenAdvertisementId', payload.assetId);
      facts.hasOpenAdvertisement = !!(openAdvId && String(openAdvId).length > 0);
      break;
    }
    case 'RequestReturn': {
      const sale = await safeEvaluate(contract, 'ReadSale', payload.sellId);
      facts.saleExists = !!sale;
      facts.requesterIsBuyer = !!(sale && sale.buyer === payload.requester);
      const existingReturn = await safeEvaluate(contract, 'GetReturnRequestIdBySale', payload.sellId);
      facts.returnAlreadyExists = !!(existingReturn && String(existingReturn).length > 0);
      break;
    }
    case 'SellerAcceptReturn': {
      const req = await safeEvaluate(contract, 'ReadReturnRequest', payload.requestId);
      facts.returnExists = !!req;
      facts.returnOpen = !!(req && req.status === 'OPEN');
      let sale = null;
      if (req) sale = await safeEvaluate(contract, 'ReadSale', req.sale_id);
      facts.sellerIsOriginalSeller = !!(sale && sale.seller === payload.seller);
      const existingAccept = await safeEvaluate(contract, 'GetAcceptIdByReturn', payload.requestId);
      facts.acceptAlreadyExists = !!(existingAccept && String(existingAccept).length > 0);
      break;
    }
    default:
      break;
  }
  return facts;
}

const operationMap = {
  CreateAsset: 'CREATE',
  CreateAdvertisement: 'ADVERTISEMENT',
  UpdateAdvertisement: 'UPDATE_ADV',
  SubmitBuyOffer: 'BUY_OFFER',
  Sell: 'SELL',
  Transfer: 'TRANSFER',
  RequestReturn: 'REQUEST_RETURN',
  SellerAcceptReturn: 'SELLER_ACCEPT_RETURN',
};

function loadConnectionProfile(ccpPath, channelName) {
  const ccp = JSON.parse(fs.readFileSync(ccpPath, 'utf8'));
  const org2Path = ccpPath
    .replace(`${path.sep}org1.example.com${path.sep}`, `${path.sep}org2.example.com${path.sep}`)
    .replace('connection-org1.json', 'connection-org2.json');
  if (fs.existsSync(org2Path)) {
    const org2 = JSON.parse(fs.readFileSync(org2Path, 'utf8'));
    ccp.peers = { ...(ccp.peers || {}), ...(org2.peers || {}) };
    ccp.organizations = { ...(ccp.organizations || {}), ...(org2.organizations || {}) };
  }
  const peerNames = Object.keys(ccp.peers || {});
  const testNetworkRoot = path.resolve(path.dirname(ccpPath), '../../..');
  const ordererTls = path.join(
    testNetworkRoot,
    'organizations/ordererOrganizations/example.com/orderers/orderer.example.com/tls/ca.crt',
  );
  if (fs.existsSync(ordererTls) && !ccp.orderers) {
    ccp.orderers = {
      'orderer.example.com': {
        url: 'grpcs://localhost:7050',
        tlsCACerts: { path: ordererTls },
        grpcOptions: { 'ssl-target-name-override': 'orderer.example.com' },
      },
    };
  }
  const ordererNames = Object.keys(ccp.orderers || {});
  if (peerNames.length && !ccp.channels) {
    ccp.channels = {
      [channelName]: {
        orderers: ordererNames,
        peers: Object.fromEntries(
          peerNames.map((name) => [
            name,
            { endorsingPeer: true, chaincodeQuery: true, ledgerQuery: true, eventSource: true },
          ]),
        ),
      },
    };
  }
  return ccp;
}

async function getGateway() {
  const ccpPath = process.env.FABRIC_CONNECTION_PROFILE;
  const walletDir = process.env.FABRIC_WALLET_DIR;
  const identity = process.env.FABRIC_IDENTITY || 'appUser';
  const channelName = process.env.FABRIC_CHANNEL || 'mychannel';
  const contractName = process.env.FABRIC_CONTRACT || 'marketplace';
  if (!ccpPath || !walletDir) {
    throw new Error('Set FABRIC_CONNECTION_PROFILE and FABRIC_WALLET_DIR');
  }
  const ccp = loadConnectionProfile(ccpPath, channelName);
  const wallet = await Wallets.newFileSystemWallet(walletDir);
  const gateway = new Gateway();
  // Discovery hangs in WSL against this static cryptogen network; merge org2 instead.
  const discoveryEnabled = process.env.FABRIC_DISCOVERY === 'true';
  await gateway.connect(ccp, {
    wallet,
    identity,
    discovery: { enabled: discoveryEnabled, asLocalhost: true },
  });
  const network = await gateway.getNetwork(channelName);
  return { gateway, contract: network.getContract(contractName) };
}

async function submit(contract, fn, payload) {
  switch (fn) {
    case 'CreateAsset':
      return contract.submitTransaction('CreateAsset', payload.assetId, payload.owner, payload.description || '');
    case 'CreateAdvertisement':
      return contract.submitTransaction('CreateAdvertisement', payload.advId, payload.assetId, payload.advertiser, payload.price || '0');
    case 'UpdateAdvertisement':
      return contract.submitTransaction('UpdateAdvertisement', payload.advId, payload.updater, payload.nextStatus || '', payload.price || '');
    case 'SubmitBuyOffer':
      return contract.submitTransaction(
        'SubmitBuyOffer',
        payload.offerId,
        payload.advId,
        payload.buyer,
        payload.amount || '0',
        payload.expiry || new Date(Date.now() + 7 * 24 * 3600 * 1000).toISOString(),
      );
    case 'Sell':
      return contract.submitTransaction('Sell', payload.sellId, payload.offerId, payload.seller);
    case 'Transfer':
      return contract.submitTransaction('Transfer', payload.assetId, payload.currentOwner, payload.newOwner);
    case 'RequestReturn':
      return contract.submitTransaction('RequestReturn', payload.requestId, payload.sellId, payload.requester, payload.reason || '');
    case 'SellerAcceptReturn':
      return contract.submitTransaction('SellerAcceptReturn', payload.acceptId, payload.requestId, payload.seller);
    default:
      throw new Error(`Function ${fn} is not mapped`);
  }
}

async function main() {
  const fn = args.fn;
  const payload = JSON.parse(args.payload || '{}');
  const opName = operationMap[fn];
  if (!opName) throw new Error(`Unknown function ${fn}`);

  const { gateway, contract } = await getGateway();
  try {
    let shaclMs = 0;
    if (args['use-shacl']) {
      const facts = await gatherStateFacts(contract, fn, payload);
      const result = await shaclValidate(opName, facts);
      shaclMs = result.duration_ms;
      if (!result.conforms) {
        console.error('SHACL validation failed:', result.results);
        process.exit(2);
      }
    }
    const t1 = nowMs();
    const response = await submit(contract, fn, payload);
    const duration = nowMs() - t1;
    logMetric('fabric_submit', { function: fn, duration_ms: duration, shacl_ms: shaclMs, use_shacl: !!args['use-shacl'] });
    console.log('OK:', response && response.toString());
  } finally {
    gateway.disconnect();
  }
}

main()
  .then(() => process.exit(0))
  .catch((e) => {
    console.error(e);
    process.exit(1);
  });
