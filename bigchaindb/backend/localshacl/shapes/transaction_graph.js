// Read only the transaction's declared RDF paths. Identically named predicates
// on nested metadata must never alter operation dispatch or dependency fields.
const BDB = 'http://bigchaindb.com/ns#';
const RDF_TYPE = 'http://www.w3.org/1999/02/22-rdf-syntax-ns#type';
const XSD = 'http://www.w3.org/2001/XMLSchema#';
const same = (a, b) => a.termType === b.termType && a.value === b.value;

export function extractTransactionData(dataset, expectedOperation) {
  const quads = [...dataset];
  const roots = quads.filter(q => q.predicate.value === BDB + 'operation'
    && q.subject.termType === 'NamedNode' && q.subject.value.startsWith('urn:tx:'));
  if (roots.length !== 1 || roots[0].object.termType !== 'Literal') {
    throw new Error('Exactly one transaction root operation is required');
  }
  const root = roots[0].subject;
  const operation = roots[0].object.value;
  if (!expectedOperation || operation !== expectedOperation) {
    throw new Error('Transaction operation does not match the requested shape');
  }
  if (!quads.some(q => same(q.subject, root) && q.predicate.value === RDF_TYPE
      && q.object.value === BDB + operation + 'Transaction')) {
    throw new Error('Transaction root type does not match its operation');
  }
  const fields = node => quads.filter(q => same(q.subject, node)
    && q.predicate.value.startsWith(BDB));
  const literal = term => {
    if (term.termType !== 'Literal') throw new Error('Expected a literal value');
    // Preserve numeric strings (amounts/keys); decode typed nested values.
    if (term.datatype?.value === XSD + 'boolean') return term.value === 'true' || term.value === '1';
    if ([XSD + 'integer', XSD + 'decimal', XSD + 'double'].includes(term.datatype?.value)) {
      const n = Number(term.value);
      if (!Number.isFinite(n)) throw new Error('Invalid numeric literal');
      return n;
    }
    return term.value;
  };
  const decode = (node, seen = new Set()) => {
    if (node.termType === 'Literal') return literal(node);
    if (node.termType !== 'BlankNode' || seen.has(node.value)) {
      throw new Error('Expected an acyclic nested blank node');
    }
    const next = new Set(seen).add(node.value);
    const obj = Object.create(null);
    for (const q of fields(node)) {
      const key = q.predicate.value.slice(BDB.length);
      const value = decode(q.object, next);
      if (['owners_before', 'public_keys', 'capability', 'capabilityParameters'].includes(key)) {
        (obj[key] ||= []).push(value);
      } else {
        if (Object.hasOwn(obj, key)) throw new Error('Ambiguous nested field: ' + key);
        obj[key] = value;
      }
    }
    return obj;
  };
  const single = name => {
    const matches = fields(root).filter(q => q.predicate.value === BDB + name);
    if (matches.length > 1) throw new Error('Ambiguous transaction field: ' + name);
    return matches.length ? decode(matches[0].object) : Object.create(null);
  };
  const asset = single('asset');
  asset.data ||= Object.create(null);
  if (asset.id && asset.data.id && asset.id !== asset.data.id) {
    throw new Error('Conflicting asset identifiers');
  }
  return {
    id: root.value.slice('urn:tx:'.length), operation, asset,
    metadata: single('metadata'),
    inputs: fields(root).filter(q => q.predicate.value === BDB + 'inputs').map(q => decode(q.object)),
    outputs: fields(root).filter(q => q.predicate.value === BDB + 'outputs').map(q => decode(q.object)),
  };
}
