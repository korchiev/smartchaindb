import { AsyncLocalStorage } from 'async_hooks';
const storage = new AsyncLocalStorage();
const HEX64 = /^[0-9a-f]{64}$/;
const at = (obj, path) => path.split('.').reduce((v, key) => v?.[key], obj);

// This intentionally supports only the query fragment used by these rules.
// An unsupported operator fails validation rather than silently ignoring it.
export function matchesFilter(row, filter) {
  return Object.entries(filter).every(([key, expected]) => {
    if (key === '$or') return expected.some(part => matchesFilter(row, part));
    if (key === '$and') return expected.every(part => matchesFilter(row, part));
    if (key.startsWith('$')) throw new Error('Unsupported state query operator: ' + key);
    const actual = at(row, key);
    if (expected && typeof expected === 'object') {
      if (Object.keys(expected).length === 1 && Array.isArray(expected.$in)) return expected.$in.includes(actual);
      throw new Error('Unsupported state query value');
    }
    return actual === expected;
  });
}

export function ledgerView(db, pendingTransactions = []) {
  const pending = { transactions: [], metadata: [], assets: [] };
  for (const tx of pendingTransactions) {
    if (!tx || typeof tx.id !== 'string' || typeof tx.operation !== 'string') throw new Error('Invalid block-prefix transaction');
    pending.transactions.push(tx);
    pending.metadata.push({ id: tx.id, metadata: tx.metadata });
    if (tx.operation === 'CREATE') pending.assets.push({ id: tx.id, ...tx.asset });
  }
  return collection => {
    if (!Object.hasOwn(pending, collection)) throw new Error('Unsupported state collection');
    const base = db.collection(collection);
    const extra = filter => pending[collection].filter(row => matchesFilter(row, filter));
    return {
      async findOne(filter) {
        const committed = await base.findOne(filter);
        return committed || extra(filter)[0] || null;
      },
      find(filter) {
        let cursor = base.find(filter);
        const query = {
          sort(order) { cursor = cursor.sort(order); return query; },
          async toArray() { return [...await cursor.toArray(), ...extra(filter)]; },
        };
        return query;
      },
      async countDocuments(filter) { return await base.countDocuments(filter) + extra(filter).length; },
    };
  };
}

export function tracked(collection) {
  const ctx = storage.getStore();
  if (!ctx?.db) throw new Error('Ledger state is unavailable');
  const col = ctx.view(collection);
  const record = filter => {
    ctx.queries += 1;
    ctx.collections.add(collection);
    const walk = value => {
      if (Array.isArray(value)) value.forEach(walk);
      else if (value && typeof value === 'object') Object.values(value).forEach(walk);
      else if (typeof value === 'string' && HEX64.test(value)) ctx.ids.add(value);
    };
    walk(filter);
  };
  return {
    findOne(filter) { record(filter); return col.findOne(filter); },
    find(filter) { record(filter); return col.find(filter); },
    countDocuments(filter) { record(filter); return col.countDocuments(filter); },
  };
}

export function expired(value) {
  const ctx = storage.getStore();
  if (!ctx) throw new Error('Validation context is required');
  const deadline = Date.parse(value);
  if (!Number.isFinite(deadline)) throw new Error('Invalid expiry time');
  ctx.validUntil = Math.min(ctx.validUntil, deadline);
  return deadline <= ctx.time;
}

export async function withStateContext(options, callback) {
  if (!options.db) throw new Error('Ledger state is unavailable');
  const time = options.validationTime === undefined ? Date.now() : Date.parse(options.validationTime);
  if (!Number.isFinite(time)) throw new Error('Invalid validation time');
  if (!Array.isArray(options.pendingTransactions || [])) throw new Error('Invalid block prefix');
  const ctx = { db: options.db, view: ledgerView(options.db, options.pendingTransactions),
    time, validUntil: Infinity, ids: new Set(), queries: 0, collections: new Set() };
  const errors = await storage.run(ctx, callback);
  return { errors, read_set: { tx_ids: [...ctx.ids], queries: ctx.queries, collections: [...ctx.collections] },
    valid_until: Number.isFinite(ctx.validUntil) ? new Date(ctx.validUntil).toISOString() : null };
}
