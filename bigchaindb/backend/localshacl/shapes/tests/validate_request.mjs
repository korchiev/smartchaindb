// Offline integration harness: real parser, shapes, engine and state rules;
// only MongoDB transport is replaced by the supplied normalized records.
import fs from 'node:fs/promises';
import { Readable } from 'node:stream';
import ParserN3 from '@rdfjs/parser-n3';
import rdfDataset from '@rdfjs/dataset';
import factory from '@rdfjs/data-model';
import { Validator } from 'shacl-engine';
import { extractTransactionData } from '../transaction_graph.js';
import { validateState } from '../state_validator.js';
import { matchesFilter } from '../state_context.js';
let input='';for await (const chunk of process.stdin) input+=chunk;
const {request,records}=JSON.parse(input);
async function parse(ttl){const d=rdfDataset.dataset();for await(const q of new ParserN3().import(Readable.from([ttl])))d.add(q);return d;}
const db={collection(name){const rows=records[name]||[];return {
 async findOne(q){return rows.find(r=>matchesFilter(r,q))||null;},
 find(q){const c={sort(){return c;},async toArray(){return rows.filter(r=>matchesFilter(r,q));}};return c;},
 async countDocuments(q){return rows.filter(r=>matchesFilter(r,q)).length;},
};}};
const dataset=await parse(request.data);
const shapes=await parse(await fs.readFile(new URL('../shapes/'+request.shapeType+'.ttl',import.meta.url),'utf8'));
const report=await new Validator(shapes,{factory}).validate({dataset});
let results=report.results.map(r=>({message:r.message.map(m=>m.value)}));
let state={errors:[],read_set:{tx_ids:[],queries:0,collections:[]},valid_until:null};
if(report.conforms){state=await validateState(extractTransactionData(dataset,request.shapeType),{db,validationTime:request.validationTime,pendingTransactions:request.pendingTransactions});results=results.concat(state.errors);}
process.stdout.write(JSON.stringify({validation_protocol:2,conforms:report.conforms&&results.length===0,results,
 validation_phases:{state:report.conforms?'completed':'not_required'},read_set:state.read_set,valid_until:state.valid_until}));
