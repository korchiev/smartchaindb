#!/usr/bin/env node
// Professor-letter Fabric metrics: Direct vs SHACL vs SHACL+Δ, mixes, CDF, load, reject.
import fs from 'fs';
import path from 'path';
import { getGateway, submitMarketplace, deltaCache, shaclValidate, gatherStateFacts } from './index.js';

const N_VAL = Number(process.env.N_VAL || 20);
const N_E2E = Number(process.env.N_E2E || 5);
const N_OFFER = Number(process.env.N_OFFER || 20);
const N_LOAD = Number(process.env.N_LOAD || 16);
const LOAD_CONC = (process.env.LOAD_CONC || '1,2,4,8').split(',').map((x) => Number(x.trim())).filter(Boolean);
const MODES = (process.env.MODES || 'direct,shacl,delta').split(',');
const OUT = process.env.OUT || path.resolve('../../eval/results/fabric.json');
const SKIP_LOAD = process.env.SKIP_LOAD === 'true';
const WAN = process.env.WAN === 'true';

function summarize(samples) {
  if (!samples.length) return { n: 0, samples: [] };
  const ordered = [...samples].sort((a, b) => a - b);
  const at = (p) => ordered[Math.max(0, Math.min(ordered.length - 1, Math.round((p / 100) * (ordered.length - 1))))];
  return {
    n: ordered.length,
    mean: samples.reduce((a, b) => a + b, 0) / samples.length,
    median: at(50),
    p95: at(95),
    min: ordered[0],
    max: ordered[ordered.length - 1],
    samples,
  };
}

function suffix(label) {
  return `${label}_${Date.now()}_${Math.random().toString(16).slice(2, 8)}`;
}

async function lifecycle(contract, mode, tag) {
  const useShacl = mode !== 'direct';
  const useDelta = mode === 'delta';
  const owner = 'org1User';
  const buyer = 'org2User';
  const ids = {
    assetId: `asset_${tag}`,
    advId: `adv_${tag}`,
    offerId: `offer_${tag}`,
    sellId: `sell_${tag}`,
    requestId: `ret_${tag}`,
    acceptId: `acc_${tag}`,
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
    const result = await submitMarketplace(contract, fn, payload, {
      useShacl,
      useDelta,
      mempoolRecheck: useDelta,
    });
    times.push({
      fn,
      ms: Date.now() - started,
      shacl_ms: result.shacl_ms,
      cached: result.cached,
    });
  }
  return { total_ms: Date.now() - t0, times };
}

async function openAd(contract, tag, mode) {
  const useShacl = mode !== 'direct';
  const useDelta = mode === 'delta';
  const owner = 'org1User';
  const ids = { assetId: `asset_${tag}`, advId: `adv_${tag}` };
  await submitMarketplace(contract, 'CreateAsset', { assetId: ids.assetId, owner, description: 'mix' }, { useShacl, useDelta });
  await submitMarketplace(contract, 'CreateAdvertisement', { advId: ids.advId, assetId: ids.assetId, advertiser: owner, price: '100' }, { useShacl, useDelta });
  return ids;
}

async function mixShared(contract, mode, n) {
  const useShacl = mode !== 'direct';
  const useDelta = mode === 'delta';
  deltaCache.clear();
  const ids = await openAd(contract, suffix('shared'), mode);
  const latencies = [];
  let committed = 0;
  let rejected = 0;
  let hits = 0;
  for (let i = 0; i < n; i += 1) {
    const t0 = Date.now();
    try {
      const result = await submitMarketplace(
        contract,
        'SubmitBuyOffer',
        { offerId: `offer_${ids.advId}_${i}`, advId: ids.advId, buyer: 'org2User', amount: '100' },
        { useShacl, useDelta, mempoolRecheck: useDelta },
      );
      latencies.push(Date.now() - t0);
      committed += 1;
      if (result.cached) hits += 1;
    } catch (e) {
      latencies.push(Date.now() - t0);
      rejected += 1;
    }
  }
  return {
    mix: 'shared_ad',
    attempted: n,
    committed,
    rejected,
    hits,
    commit: summarize(latencies),
    stats: deltaCache.stats(),
  };
}

async function mixMutate(contract, mode, n) {
  const useShacl = mode !== 'direct';
  const useDelta = mode === 'delta';
  deltaCache.clear();
  const ids = await openAd(contract, suffix('mutate'), mode);
  const half = Math.max(1, Math.floor(n / 2));
  const before = [];
  const after = [];
  let committed = 0;
  let rejected = 0;
  for (let i = 0; i < half; i += 1) {
    const t0 = Date.now();
    try {
      await submitMarketplace(
        contract,
        'SubmitBuyOffer',
        { offerId: `om_${ids.advId}_${i}`, advId: ids.advId, buyer: 'org2User', amount: '100' },
        { useShacl, useDelta, mempoolRecheck: useDelta },
      );
      before.push(Date.now() - t0);
      committed += 1;
    } catch (e) {
      before.push(Date.now() - t0);
      rejected += 1;
    }
  }
  await submitMarketplace(
    contract,
    'UpdateAdvertisement',
    { advId: ids.advId, updater: 'org1User', nextStatus: 'CLOSED', price: '100' },
    { useShacl, useDelta },
  );
  for (let i = 0; i < n - half; i += 1) {
    const t0 = Date.now();
    try {
      await submitMarketplace(
        contract,
        'SubmitBuyOffer',
        { offerId: `omc_${ids.advId}_${i}`, advId: ids.advId, buyer: 'org2User', amount: '100' },
        { useShacl, useDelta, mempoolRecheck: useDelta },
      );
      after.push(Date.now() - t0);
      committed += 1;
    } catch (e) {
      after.push(Date.now() - t0);
      rejected += 1;
    }
  }
  return {
    mix: 'mutating_ad',
    attempted: n,
    committed,
    rejected,
    abort_rate: n ? rejected / n : 0,
    before_close: summarize(before),
    after_close: summarize(after),
    stats: deltaCache.stats(),
  };
}

async function mixDisjoint(contract, mode, n) {
  const useShacl = mode !== 'direct';
  const useDelta = mode === 'delta';
  deltaCache.clear();
  const latencies = [];
  let committed = 0;
  let rejected = 0;
  for (let i = 0; i < n; i += 1) {
    const ids = await openAd(contract, suffix(`dj${i}`), mode);
    const t0 = Date.now();
    try {
      await submitMarketplace(
        contract,
        'SubmitBuyOffer',
        { offerId: `od_${ids.advId}`, advId: ids.advId, buyer: 'org2User', amount: '100' },
        { useShacl, useDelta, mempoolRecheck: useDelta },
      );
      latencies.push(Date.now() - t0);
      committed += 1;
    } catch (e) {
      latencies.push(Date.now() - t0);
      rejected += 1;
    }
  }
  return {
    mix: 'disjoint',
    attempted: n,
    committed,
    rejected,
    commit: summarize(latencies),
    stats: deltaCache.stats(),
  };
}

async function failClosed(contract, mode) {
  const useShacl = mode !== 'direct';
  const useDelta = mode === 'delta';
  const ids = await openAd(contract, suffix('rej'), mode);
  const t0 = Date.now();
  try {
    await submitMarketplace(
      contract,
      'CreateAdvertisement',
      { advId: `adv_bad_${ids.assetId}`, assetId: ids.assetId, advertiser: 'org2User', price: '1' },
      { useShacl, useDelta },
    );
    return { rejected: false, ms: Date.now() - t0, status: 'accepted' };
  } catch (e) {
    return {
      rejected: true,
      ms: Date.now() - t0,
      reason: e && e.message ? e.message : String(e),
    };
  }
}

async function runLoad(contract, mode, n, concs) {
  const useShacl = mode !== 'direct';
  const useDelta = mode === 'delta';
  const ids = await openAd(contract, suffix('load'), mode);
  const rows = [];
  for (const c of concs) {
    deltaCache.clear();
    const per = Math.max(1, Math.floor(n / c));
    const attempted = per * c;
    const t0 = Date.now();
    const workers = [];
    for (let w = 0; w < c; w += 1) {
      workers.push((async () => {
        const latencies = [];
        let committed = 0;
        let rejected = 0;
        for (let i = 0; i < per; i += 1) {
          const started = Date.now();
          try {
            await submitMarketplace(
              contract,
              'SubmitBuyOffer',
              { offerId: `ol_${ids.advId}_${w}_${i}_${Date.now()}`, advId: ids.advId, buyer: 'org2User', amount: '100' },
              { useShacl, useDelta },
            );
            committed += 1;
          } catch (e) {
            rejected += 1;
          }
          latencies.push(Date.now() - started);
        }
        return { latencies, committed, rejected };
      })());
    }
    const parts = await Promise.all(workers);
    const wall = (Date.now() - t0) / 1000;
    const latencies = parts.flatMap((p) => p.latencies);
    const committed = parts.reduce((a, p) => a + p.committed, 0);
    const rejected = parts.reduce((a, p) => a + p.rejected, 0);
    rows.push({
      concurrency: c,
      attempted,
      committed,
      rejected,
      wall_s: wall,
      offered_tps: wall ? attempted / wall : 0,
      committed_tps: wall ? committed / wall : 0,
      abort_rate: attempted ? rejected / attempted : 0,
      latency: summarize(latencies),
      stats: deltaCache.stats(),
    });
  }
  return rows;
}

async function validationLayer(contract, n) {
  const ids = await openAd(contract, suffix('val'), 'delta');
  const payload = { offerId: `offer_val_${ids.advId}`, advId: ids.advId, buyer: 'org2User', amount: '100' };
  const facts = await gatherStateFacts(contract, 'SubmitBuyOffer', payload);
  const { hashFacts } = await import('./delta.js');
  const cacheMeta = { txId: payload.offerId, depHash: hashFacts(facts), depIds: [ids.advId] };
  const miss = [];
  const hits = [];
  for (let i = 0; i < n; i += 1) {
    deltaCache.clear();
    const first = await shaclValidate('BUY_OFFER', facts, cacheMeta);
    miss.push(first.duration_ms);
    const second = await shaclValidate('BUY_OFFER', facts, cacheMeta);
    hits.push(second.duration_ms);
  }
  const closedFacts = { ...facts, advertisementOpen: false };
  const closedMeta = { txId: payload.offerId, depHash: hashFacts(closedFacts), depIds: [ids.advId] };
  const changed = await shaclValidate('BUY_OFFER', closedFacts, closedMeta);
  return {
    shacl_http_miss: summarize(miss),
    shacl_delta_hit: summarize(hits),
    value_change_miss: { n: 1, median: changed.duration_ms, samples: [changed.duration_ms] },
    stats: deltaCache.stats(),
  };
}

async function runMode(contract, mode) {
  deltaCache.clear();
  const block = { mode, cache_start: deltaCache.stats() };
  console.log(`=== Fabric ${mode} e2e n=${N_E2E} ===`);
  const trials = [];
  for (let i = 0; i < N_E2E; i += 1) {
    const run = await lifecycle(contract, mode, suffix(`${mode}${i}`));
    trials.push(run);
    console.log(`  ${mode} trial ${i + 1}: ${run.total_ms} ms`);
  }
  const byOp = {};
  for (const trial of trials) {
    for (const t of trial.times) {
      if (!byOp[t.fn]) byOp[t.fn] = [];
      byOp[t.fn].push(t.ms);
    }
  }
  block.e2e = {
    trials,
    total: summarize(trials.map((t) => t.total_ms)),
    by_op: Object.fromEntries(Object.entries(byOp).map(([k, v]) => [k, summarize(v)])),
  };
  console.log(`=== Fabric ${mode} mixes ===`);
  block.mix_shared = await mixShared(contract, mode, N_OFFER);
  block.mix_mutate = await mixMutate(contract, mode, N_OFFER);
  if (!WAN) block.mix_disjoint = await mixDisjoint(contract, mode, N_OFFER);
  block.fail_closed = await failClosed(contract, mode);
  if (!SKIP_LOAD && !WAN) {
    console.log(`=== Fabric ${mode} load ===`);
    block.load = await runLoad(contract, mode, N_LOAD, LOAD_CONC);
  }
  block.cache_end = deltaCache.stats();
  return block;
}

async function main() {
  const { gateway, contract } = await getGateway();
  const payload = {
    platform: 'fabric',
    wan: WAN,
    n_e2e: N_E2E,
    n_offer: N_OFFER,
    n_load: N_LOAD,
    started: new Date().toISOString(),
    modes: {},
  };
  try {
    if (!WAN) {
      console.log(`=== Fabric validation layer n=${N_VAL} ===`);
      payload.validation_layer = await validationLayer(contract, N_VAL);
    }
    for (const mode of MODES) {
      payload.modes[mode] = await runMode(contract, mode);
    }
    payload.finished = new Date().toISOString();
    fs.mkdirSync(path.dirname(OUT), { recursive: true });
    fs.writeFileSync(OUT, JSON.stringify(payload, null, 2));
    console.log('WROTE', OUT);
    console.log('FABRIC PROFESSOR EVAL OK');
  } finally {
    gateway.disconnect();
  }
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
