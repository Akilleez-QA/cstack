import { readFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

const [modulePath, root, vectorPath, guard] = process.argv.slice(2);
const { createKernel } = await import(pathToFileURL(modulePath).href);
const kernel = createKernel({ root, ...(guard === 'unguarded' ? { numericGuard: false } : {}) });
const canonical = value => {
  if (Array.isArray(value)) return `[${value.map(canonical).join(',')}]`;
  if (value !== null && typeof value === 'object') return `{${Object.keys(value).sort().map(key => `${JSON.stringify(key)}:${canonical(value[key])}`).join(',')}}`;
  return JSON.stringify(value === 0 ? 0 : value);
};
const firstDifference = (a, b, path = '') => {
  if (a !== null && b !== null && typeof a === 'object' && typeof b === 'object') {
    for (const key of new Set([...Object.keys(a), ...Object.keys(b)])) {
      const found = firstDifference(a[key], b[key], `${path}/${key}`);
      if (found) return found;
    }
    return null;
  }
  return canonical(a ?? null) === canonical(b ?? null) && (a === undefined) === (b === undefined) ? null : { path, python: a, kernel: b };
};
const report = { compared: 0, agreed_success: 0, agreed_tool_error: 0, refused_both: 0, refused_port_only: 0, disagreed: 0, refusal_codes: {}, per_tool: {}, first: [] };
const bump = (table, key) => { table[key] = (table[key] ?? 0) + 1; };
const disagree = row => {
  report.disagreed += 1;
  if (report.first.length < 10) report.first.push(row);
};
for (const row of JSON.parse(readFileSync(vectorPath, 'utf8'))) {
  report.compared += 1;
  report.per_tool[row.tool] ??= { compared: 0, success: 0, tool_error: 0, refused: 0, disagreed: 0 };
  const line = report.per_tool[row.tool];
  line.compared += 1;
  const before = report.disagreed;
  let result = null, refusal = null;
  try { result = kernel.run(row.tool, row.arguments); }
  catch (error) {
    if (error.code === undefined) throw error;
    refusal = error.code;
  }
  if (refusal !== null) {
    line.refused += 1;
    bump(report.refusal_codes, refusal);
    if (row.python.wire !== undefined) report.refused_both += 1;
    else report.refused_port_only += 1;
    continue;
  }
  if (row.python.wire !== undefined) {
    disagree({ tool: row.tool, arguments: row.arguments.slice(0, 400), path: '/wire', python: row.python.wire, kernel: result.status });
  } else {
    const { assessment, ...receipt } = result;
    if (assessment !== row.python.assessment) disagree({ tool: row.tool, arguments: row.arguments.slice(0, 400), path: '/assessment', python: row.python.assessment, kernel: assessment });
    else {
      const difference = firstDifference(row.python.receipt, receipt);
      if (difference) disagree({ tool: row.tool, arguments: row.arguments.slice(0, 400), ...difference });
      else if (result.status === 'ok') { report.agreed_success += 1; line.success += 1; }
      else { report.agreed_tool_error += 1; line.tool_error += 1; }
    }
  }
  if (report.disagreed > before) line.disagreed += 1;
}
process.stdout.write(JSON.stringify(report));
