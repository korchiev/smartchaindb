import assert from 'node:assert/strict';
import test from 'node:test';
import fs from 'node:fs/promises';
import { Readable } from 'node:stream';
import ParserN3 from '@rdfjs/parser-n3';
import rdfDataset from '@rdfjs/dataset';
import factory from '@rdfjs/data-model';
import { Validator } from 'shacl-engine';
import { extractTransactionData } from '../transaction_graph.js';
import { validateState } from '../state_validator.js';
import { matchesFilter } from '../state_context.js';

const id = char => char.repeat(64);
const asset = id('a'), ad = id('b'), offer = id('c'), sale = id('d');
const time = '2026-10-17T06:00:00.000Z';
const expiry = '2026-10-17T06:00:01.000Z';
function database(txs = [], metadata = []) {
  const rows = {transactions: txs, metadata, assets: []};
  return {collection(name) {return {
    async findOne(filter) {return rows[name].find(row => matchesFilter(row, filter)) || null;},
    find(filter) {const cursor = {sort() {return cursor;}, async toArray() {return rows[name].filter(row => matchesFilter(row, filter));}};return cursor;},
    async countDocuments(filter) {return rows[name].filter(row => matchesFilter(row, filter)).length;},
  };}};
}
const openDb = () => database([
  {id:asset, operation:'CREATE', outputs:[{public_keys:['seller']}]},
  {id:ad, operation:'ADVERTISEMENT', asset:{id:asset}},
], [{id:ad, metadata:{status:'OPEN', advertiser_public_key:'seller'}}]);
const offerTx = () => ({id:id('f'), operation:'BUY_OFFER', asset:{id:asset,data:{advertisement_id:ad}},
  metadata:{buyer_public_key:'buyer',offer_expiry:expiry}});
async function parse(ttl) {
  const dataset = rdfDataset.dataset();
  for await (const quad of new ParserN3().import(Readable.from([ttl]))) dataset.add(quad);
  return dataset;
}
function graph(extra = '') {return `@prefix bdb:<http://bigchaindb.com/ns#> . @prefix xsd:<http://www.w3.org/2001/XMLSchema#> .
<urn:tx:${id('f')}> a bdb:BUY_OFFERTransaction; bdb:operation "BUY_OFFER"; bdb:version "2.0";
bdb:asset [bdb:id "${asset}";bdb:data [bdb:advertisement_id "${ad}"]];
bdb:inputs [bdb:owners_before "${'H'.repeat(43)}";bdb:fulfillment "x"];
bdb:outputs [bdb:amount "1"];
bdb:metadata [bdb:buyer_public_key "${'H'.repeat(43)}";bdb:escrow_public_key "${'J'.repeat(43)}";bdb:offer_amount "100";
bdb:offer_expiry "2030-01-01T00:00:00Z"^^xsd:dateTime;bdb:requestCreationTimestamp "${time}"^^xsd:dateTime ${extra}] .`;}

test('metadata operation cannot bypass state validation even when the real shape accepts it', async () => {
  const dataset = await parse(graph(';bdb:operation "CREATE"'));
  const shapes = await parse(await fs.readFile(new URL('../shapes/BUY_OFFER.ttl', import.meta.url), 'utf8'));
  const report = await new Validator(shapes,{factory}).validate({dataset});
  assert.equal(report.conforms,true);
  const tx = extractTransactionData(dataset,'BUY_OFFER');
  assert.equal(tx.operation,'BUY_OFFER');
  assert.equal(tx.metadata.operation,'CREATE');
  const result = await validateState(tx,{db:database(),validationTime:time});
  assert.ok(result.errors.some(e => e.message[0].includes('does not exist')));
});
test('requested shape must match the root operation', async () => {
  assert.throws(() => extractTransactionData(null,'SELL'));
  const data=await parse(graph());
  assert.throws(() => extractTransactionData(data,'SELL'), /does not match/);
});
test('multiple root operations are rejected', async () => {
  const data=await parse(graph()+`\n<urn:tx:${id('e')}> bdb:operation "CREATE" .`);
  assert.throws(() => extractTransactionData(data,'BUY_OFFER'),/Exactly one/);
});
test('nested metadata structure is preserved', async () => {
  const data=await parse(graph(';bdb:return_policy_details [bdb:return_window_days 7]'));
  assert.equal(extractTransactionData(data,'BUY_OFFER').metadata.return_policy_details.return_window_days,7);
});
test('repeated capability values remain a collection', async () => {
  const data=await parse(graph(';bdb:capability "sell";bdb:capability "lease"'));
  assert.deepEqual(extractTransactionData(data,'BUY_OFFER').metadata.capability,['sell','lease']);
});
test('missing database is not structural-only acceptance', async () => {
  await assert.rejects(validateState(offerTx(),{db:null,validationTime:time}),/unavailable/);
});
test('query errors are failures, not cacheable semantic rejections', async () => {
  const db={collection(){return {findOne(){throw Error('database disconnected');}};}};
  await assert.rejects(validateState(offerTx(),{db,validationTime:time}),/disconnected/);
});
test('expiry is evaluated at explicit ledger time and returns a cache deadline', async () => {
  const result=await validateState(offerTx(),{db:openDb(),validationTime:time});
  assert.deepEqual(result.errors,[]);
  assert.equal(result.valid_until,expiry);
  const expired=await validateState(offerTx(),{db:openDb(),validationTime:expiry});
  assert.ok(expired.errors.some(e=>e.message[0].includes('expired')));
});
test('invalid expiry time cannot pass as NaN', async () => {
  const tx=offerTx();tx.metadata.offer_expiry='invalid';
  await assert.rejects(validateState(tx,{db:openDb(),validationTime:time}),/expiry/);
});
test('an earlier close in the same block rejects a later offer', async () => {
  const close={id:id('e'),operation:'UPDATE_ADV',asset:{id:ad,data:{id:ad}},metadata:{status:'CLOSED'}};
  const result=await validateState(offerTx(),{db:openDb(),validationTime:time,pendingTransactions:[close]});
  assert.ok(result.errors.some(e=>e.message[0].includes('not open')));
});
test('a closed advertisement cannot reopen', async () => {
  const db=database([{id:ad,operation:'ADVERTISEMENT',asset:{id:asset}},
    {id:id('e'),operation:'UPDATE_ADV',asset:{id:ad}}],
    [{id:ad,metadata:{status:'OPEN',advertiser_public_key:'seller'}},{id:id('e'),metadata:{status:'CLOSED'}}]);
  const tx={id:id('f'),operation:'UPDATE_ADV',asset:{data:{id:ad}},inputs:[{owners_before:['seller']}],metadata:{status:'OPEN'}};
  const result=await validateState(tx,{db,validationTime:time});
  assert.ok(result.errors.some(e=>e.message[0].includes('Invalid status transition')));
});
test('active advertisement uniqueness reads normalized metadata', async () => {
  const tx={id:id('f'),operation:'ADVERTISEMENT',asset:{id:asset},metadata:{advertiser_public_key:'seller'}};
  const result=await validateState(tx,{db:openDb(),validationTime:time});
  assert.ok(result.errors.some(e=>e.message[0].includes('active advertisement')));
});
test('a return earlier in the block prevents a second return', async () => {
  const db=database([{id:sale,operation:'SELL'}],[{id:sale,metadata:{buyer_public_key:'buyer'}}]);
  const tx={id:id('f'),operation:'REQUEST_RETURN',asset:{data:{sell_transaction_id:sale}},metadata:{requester_public_key:'buyer'}};
  const earlier={...tx,id:id('e')};
  const result=await validateState(tx,{db,validationTime:time,pendingTransactions:[earlier]});
  assert.ok(result.errors.some(e=>e.message[0].includes('already exists')));
});
test('block prefix can introduce a dependency used later in that block', async () => {
  const pending=[{id:ad,operation:'ADVERTISEMENT',asset:{id:asset},metadata:{status:'OPEN',advertiser_public_key:'seller'}}];
  const result=await validateState(offerTx(),{db:database(),validationTime:time,pendingTransactions:pending});
  assert.deepEqual(result.errors,[]);
});
