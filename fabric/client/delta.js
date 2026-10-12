import crypto from 'crypto';

export function dependencyIds(fn, payload) {
  const ids = [];
  const add = (v) => {
    if (typeof v === 'string' && v && !ids.includes(v)) ids.push(v);
  };
  switch (fn) {
    case 'CreateAdvertisement':
    case 'Transfer':
      add(payload.assetId);
      break;
    case 'UpdateAdvertisement':
    case 'SubmitBuyOffer':
      add(payload.advId);
      break;
    case 'Sell':
      add(payload.offerId);
      add(payload.sellId);
      break;
    case 'RequestReturn':
      add(payload.sellId);
      break;
    case 'SellerAcceptReturn':
      add(payload.requestId);
      break;
    default:
      break;
  }
  add(payload.assetId);
  add(payload.advId);
  add(payload.offerId);
  add(payload.sellId);
  add(payload.requestId);
  return ids;
}

export function hashFacts(facts) {
  const canonical = JSON.stringify(facts, Object.keys(facts).sort());
  return crypto.createHash('sha256').update(canonical).digest('hex');
}

export class SHACLDeltaCache {
  constructor(maxSize = 2048) {
    this.maxSize = maxSize;
    this.store = new Map();
    this.index = new Map();
    this.hits = 0;
    this.misses = 0;
    this.invalidations = 0;
  }

  _key(txId, depHash) {
    return `${txId}::${depHash}`;
  }

  get(txId, depHash) {
    const key = this._key(txId, depHash);
    const entry = this.store.get(key);
    if (!entry) {
      this.misses += 1;
      return null;
    }
    this.hits += 1;
    return entry;
  }

  put(txId, depHash, result, depIds) {
    const key = this._key(txId, depHash);
    if (this.store.size >= this.maxSize && !this.store.has(key)) {
      const oldest = this.store.keys().next().value;
      this.store.delete(oldest);
    }
    this.store.set(key, { conforms: result.conforms, results: result.results || [] });
    for (const entity of new Set([txId, ...depIds].filter(Boolean))) {
      if (!this.index.has(entity)) this.index.set(entity, new Set());
      this.index.get(entity).add(key);
    }
  }

  invalidateIds(entityIds) {
    let removed = 0;
    for (const entity of new Set(entityIds.filter(Boolean))) {
      const keys = this.index.get(entity);
      if (!keys) continue;
      for (const key of keys) {
        if (this.store.delete(key)) removed += 1;
      }
      this.index.delete(entity);
    }
    this.invalidations += removed;
    return removed;
  }

  onCommitted(fn, payload) {
    return this.invalidateIds(dependencyIds(fn, payload));
  }

  stats() {
    return {
      size: this.store.size,
      hits: this.hits,
      misses: this.misses,
      invalidations: this.invalidations,
    };
  }

  clear() {
    this.store.clear();
    this.index.clear();
    this.hits = 0;
    this.misses = 0;
    this.invalidations = 0;
  }
}
