// Fabric SHACL validator: syntactic + semantic graph constraints over
// a Turtle graph that already includes fetched world-state facts.
import express from 'express';
import fs from 'fs/promises';
import path from 'path';
import { fileURLToPath } from 'url';
import { Parser, Store } from 'n3';
import SHACLValidator from 'rdf-validate-shacl';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const app = express();
const port = process.env.PORT || 3001;
const shapesCache = new Map();

app.use(express.json({ limit: '5mb' }));

function parseTurtle(ttl) {
  const parser = new Parser({ format: 'Turtle' });
  const store = new Store();
  store.addQuads(parser.parse(ttl));
  return store;
}

async function loadShapes() {
  const dir = path.join(__dirname, 'shapes');
  const files = (await fs.readdir(dir)).filter((f) => f.endsWith('.ttl'));
  for (const file of files) {
    const shapeType = path.basename(file, '.ttl');
    const ttl = await fs.readFile(path.join(dir, file), 'utf8');
    shapesCache.set(shapeType, parseTurtle(ttl));
    console.log(`-> Loaded Fabric SHACL shape: ${shapeType}`);
  }
}

app.get('/', (_req, res) => {
  res.json({
    message: 'Fabric SHACL validator',
    loaded_shapes: [...shapesCache.keys()],
  });
});

app.post('/validate', async (req, res) => {
  const { shapeType, data } = req.body || {};
  if (!shapeType || !data) {
    return res.status(400).json({ error: 'body must include shapeType and data' });
  }
  const shapes = shapesCache.get(shapeType);
  if (!shapes) {
    return res.status(404).json({
      error: `Shape type "${shapeType}" not found.`,
      available_shapes: [...shapesCache.keys()],
    });
  }
  try {
    const dataset = parseTurtle(data);
    const validator = new SHACLValidator(shapes);
    const report = await validator.validate(dataset);
    const results = report.results.map((r) => ({
      message: (r.message || []).map((m) => (m.value ? m.value : String(m))),
      path: r.path ? String(r.path.value || r.path) : null,
      focusNode: r.focusNode ? String(r.focusNode.value || r.focusNode) : null,
      severity: r.severity ? String(r.severity.value || r.severity) : null,
    }));
    res.json({ conforms: report.conforms, results });
  } catch (err) {
    res.status(500).json({ error: 'validation failed', details: err.message });
  }
});

await loadShapes();
app.listen(port, () => {
  console.log(`Fabric SHACL validator listening on ${port}`);
});
