#!/usr/bin/env node
// End-to-end marketplace + SHACL smoke: CREATE → ADVERTISE → OFFER → SELL → RETURN.
import { spawn } from 'child_process';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const suffix = process.env.SMOKE_ID || `s${Date.now()}`;
const USE_SHACL = process.env.USE_SHACL !== 'false';

function run(fn, payload, expectCode = 0) {
  return new Promise((resolve, reject) => {
    const args = ['index.js', 'submit', fn, '--payload', JSON.stringify(payload), `--use-shacl=${USE_SHACL}`];
    const child = spawn(process.execPath, args, { cwd: __dirname, stdio: 'inherit', env: process.env });
    child.on('exit', (code) => {
      if (code === expectCode) return resolve(code);
      reject(new Error(`${fn} exited ${code}, expected ${expectCode}`));
    });
  });
}

async function main() {
  const owner = 'org1User';
  const buyer = 'org2User';
  const assetId = `asset_${suffix}`;
  const advId = `adv_${suffix}`;
  const offerId = `offer_${suffix}`;
  const sellId = `sell_${suffix}`;
  const requestId = `ret_${suffix}`;
  const acceptId = `acc_${suffix}`;

  console.log(`Smoke lifecycle id=${suffix} SHACL=${USE_SHACL}`);
  await run('CreateAsset', { assetId, owner, description: 'smoke asset' });
  await run('CreateAdvertisement', { advId, assetId, advertiser: owner, price: '100' });
  await run('UpdateAdvertisement', { advId, updater: owner, nextStatus: 'OPEN', price: '99' });
  await run('SubmitBuyOffer', { offerId, advId, buyer, amount: '100' });
  await run('Sell', { sellId, offerId, seller: owner });
  await run('RequestReturn', { requestId, sellId, requester: buyer, reason: 'smoke return' });
  await run('SellerAcceptReturn', { acceptId, requestId, seller: owner });

  if (USE_SHACL) {
    console.log('Expect SHACL reject: advertise an asset the caller does not own');
    await run(
      'CreateAdvertisement',
      { advId: `adv_bad_${suffix}`, assetId, advertiser: buyer, price: '1' },
      2,
    );
  }
  console.log('SMOKE OK');
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
