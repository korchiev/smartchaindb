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

async function timed(fn, payload, expectCode = 0) {
  const t0 = Date.now();
  await run(fn, payload, expectCode);
  const ms = Date.now() - t0;
  console.log(`TIME ${fn} ${ms} ms`);
  return ms;
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
  const times = [];
  times.push(['CreateAsset', await timed('CreateAsset', { assetId, owner, description: 'smoke asset' })]);
  times.push(['CreateAdvertisement', await timed('CreateAdvertisement', { advId, assetId, advertiser: owner, price: '100' })]);
  times.push(['UpdateAdvertisement', await timed('UpdateAdvertisement', { advId, updater: owner, nextStatus: 'OPEN', price: '99' })]);
  times.push(['SubmitBuyOffer', await timed('SubmitBuyOffer', { offerId, advId, buyer, amount: '100' })]);
  times.push(['Sell', await timed('Sell', { sellId, offerId, seller: owner })]);
  times.push(['RequestReturn', await timed('RequestReturn', { requestId, sellId, requester: buyer, reason: 'smoke return' })]);
  times.push(['SellerAcceptReturn', await timed('SellerAcceptReturn', { acceptId, requestId, seller: owner })]);

  if (USE_SHACL) {
    console.log('Expect SHACL reject: advertise an asset the caller does not own');
    times.push([
      'CreateAdvertisement(reject)',
      await timed(
        'CreateAdvertisement',
        { advId: `adv_bad_${suffix}`, assetId, advertiser: buyer, price: '1' },
        2,
      ),
    ]);
  }
  console.log('TIMES');
  let total = 0;
  for (const [label, ms] of times) {
    console.log(`  ${label} ${ms} ms`);
    total += ms;
  }
  console.log(`  TOTAL ${total} ms`);
  console.log('SMOKE OK');
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
