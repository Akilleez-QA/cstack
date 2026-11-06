import { readFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

const [modulePath, root, vectorPath] = process.argv.slice(2);
const { createKernel } = await import(pathToFileURL(modulePath).href);
const kernel = createKernel({ root });
const same = (a, b) => {
  if (typeof a === 'number' && typeof b === 'number') return a === b;
  if (Array.isArray(a)) return Array.isArray(b) && a.length === b.length && a.every((v, i) => same(v, b[i]));
  if (a !== null && typeof a === 'object') {
    if (b === null || typeof b !== 'object') return false;
    const keys = Object.keys(a);
    return keys.length === Object.keys(b).length && keys.every(k => Object.hasOwn(b, k) && same(a[k], b[k]));
  }
  return a === b;
};
const firstDifference = (a, b, path = '') => {
  if (a !== null && b !== null && typeof a === 'object' && typeof b === 'object') {
    for (const key of new Set([...Object.keys(a), ...Object.keys(b)])) {
      const found = firstDifference(a[key], b[key], `${path}/${key}`);
      if (found) return found;
    }
    return null;
  }
  return same(a, b) ? null : { path, python: a, kernel: b };
};
let compared = 0, refused = 0, rounding = 0, worst = 0;
const lastPlace = text => { const dot = String(text).indexOf('.'); return dot < 0 ? 1 : 10 ** -(String(text).length - dot - 1); };
const differences = [];
for (const row of JSON.parse(readFileSync(vectorPath, 'utf8'))) {
  compared += 1;
  let result;
  try { result = kernel.run(row.tool, row.arguments); }
  catch (error) {
    if (error.code === undefined) throw error;
    if (!row.python_exception) differences.push({ tool: row.tool, arguments: row.arguments.slice(0, 200), path: '/refused', python: row.assessment, kernel: error.code });
    else refused += 1;
    continue;
  }
  if (row.python_exception) { differences.push({ tool: row.tool, arguments: row.arguments.slice(0, 200), path: '/receipt', python: row.python_exception, kernel: result.status }); continue; }
  const { assessment, ...receipt } = result;
  if (assessment !== undefined && assessment !== row.assessment) differences.push({ tool: row.tool, arguments: row.arguments, path: '/assessment', python: row.assessment, kernel: assessment });
  const difference = firstDifference(row.receipt, receipt);
  if (!difference) continue;
  const { python, kernel: ours } = difference;
  if (typeof python === 'number' && typeof ours === 'number' && Math.abs(python - ours) <= 1.5 * Math.max(lastPlace(python), lastPlace(ours))) {
    rounding += 1;
    worst = Math.max(worst, Math.abs(python - ours));
  } else differences.push({ tool: row.tool, arguments: row.arguments.slice(0, 200), ...difference });
}
process.stdout.write(JSON.stringify({ compared, refused, rounding, worst, different: differences.length, first: differences.slice(0, 10) }));
