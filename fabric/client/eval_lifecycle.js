#!/usr/bin/env node
// Reused-gateway Fabric lifecycle: Direct vs SHACL vs SHACL+Δ.
import { getGateway, submitMarketplace, deltaCache } from './index.js';

const N = Number(process.env.N || 3);
const MODES = (process.env.MODES || 'direct,shacl,delta').split(',');

function median(values) {
  const ordered = [...values].sort((a, b) => a - b);
  const mid = Math.floor(ordered.length / 2);
  if (ordered.length % 2) return ordered[mid];
  return (ordered[mid - 1] + ordered[mid]) / 2;
}

async function oneLifecycle(contract, mode, suffix) {
  const useShacl = mode !== 'direct';
  const useDelta = mode === 'delta';
  const owner = 'org1User';
  const buyer = 'org2User';
  const ids = {
    assetId: `asset_${suffix}`,
    advId: `adv_${suffix}`,
    offerId: `offer_${suffix}`,
    sellId: `sell_${suffix}`,
    requestId: `ret_${suffix}`,
    acceptId: `acc_${suffix}`,
  };
  const steps = [
    ['CreateAsset', { assetId: ids.assetId, owner, description: 'eval asset' }],
    ['CreateAdvertisement', { advId: ids.advId, assetId: ids.assetId, advertiser: owner, price: '100' }],
    ['UpdateAdvertisement', { advId: ids.advId, updater: owner, nextStatus: 'OPEN', price: '99' }],
    ['SubmitBuyOffer', { offerId: ids.offerId, advId: ids.advId, buyer, amount: '100' }],
    ['Sell', { sellId: ids.sellId, offerId: ids.offerId, seller: owner }],
    ['RequestReturn', { requestId: ids.requestId, sellId: ids.sellId, requester: buyer, reason: 'eval return' }],
    ['SellerAcceptReturn', { acceptId: ids.acceptId, requestId: ids.requestId, seller: owner }],
  ];
  const times = [];
  const t0 = Date.now();
  for (const [fn, payload] of steps) {
    const started = Date.now();
    const result = await submitMarketplace(contract, fn, payload, { useShacl, useDelta });
    times.push({ fn, ms: Date.now() - started, shacl_ms: result.shacl_ms, cached: result.cached });
  }
  return { total_ms: Date.now() - t0, times };
}

async function main() {
  const { gateway, contract } = await getGateway();
  try {
    console.log(`Fabric reused-gateway eval N=${N} modes=${MODES.join(',')}`);
    for (const mode of MODES) {
      deltaCache.clear();
      const totals = [];
      for (let i = 0; i < N; i += 1) {
        const suffix = `${mode}_${Date.now()}_${i}`;
        const run = await oneLifecycle(contract, mode, suffix);
        totals.push(run.total_ms);
        console.log(`  ${mode} trial ${i + 1}: ${run.total_ms} ms`, run.times.map((t) => `${t.fn}=${t.ms}${t.cached ? '*' : ''}`).join(' '));
      }
      console.log(
        `MODE ${mode} median ${median(totals).toFixed(1)} ms  min ${Math.min(...totals)}  max ${Math.max(...totals)}  cache`,
        deltaCache.stats(),
      );
    }
    console.log('FABRIC THREE-WAY OK');
  } finally {
    gateway.disconnect();
  }
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
