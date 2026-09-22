#!/usr/bin/env node
// Sequential marketplace workload: CREATE → ADVERTISE → BUY_OFFER → SELL
// Optional REQUEST_RETURN + SELLER_ACCEPT_RETURN.
import { spawn } from 'child_process';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const N = parseInt(process.env.N || '5', 10);
const RETURNS_P = parseFloat(process.env.RETURNS || '0');
const USE_SHACL = process.env.USE_SHACL === 'true';

function run(fn, payload) {
  return new Promise((resolve, reject) => {
    const args = ['index.js', 'submit', fn, '--payload', JSON.stringify(payload), `--use-shacl=${USE_SHACL}`];
    const child = spawn(process.execPath, args, { cwd: __dirname, stdio: 'inherit', env: process.env });
    child.on('exit', (code) => (code === 0 ? resolve() : reject(new Error(`${fn} failed with ${code}`))));
  });
}

async function main() {
  console.log(`Fabric workload N=${N} RETURNS=${RETURNS_P} SHACL=${USE_SHACL}`);
  for (let i = 0; i < N; i++) {
    const assetId = `asset_${i}`;
    const advId = `adv_${i}`;
    const offerId = `offer_${i}`;
    const sellId = `sell_${i}`;
    const owner = 'org1User';
    const buyer = 'org2User';
    await run('CreateAsset', { assetId, owner, description: `workload asset ${i}` });
    await run('CreateAdvertisement', { advId, assetId, advertiser: owner, price: '100' });
    await run('SubmitBuyOffer', { offerId, advId, buyer, amount: '100' });
    await run('Sell', { sellId, offerId, seller: owner });
    if (RETURNS_P > 0 && (i / N) < RETURNS_P) {
      const requestId = `ret_${i}`;
      const acceptId = `acc_${i}`;
      await run('RequestReturn', { requestId, sellId, requester: buyer, reason: 'workload return' });
      await run('SellerAcceptReturn', { acceptId, requestId, seller: owner });
    }
    console.log(`completed lifecycle ${i + 1}/${N}`);
  }
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
