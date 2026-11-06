import { realpathSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

const [pyodidePath, repository, foundationsJson, callsText] = process.argv.slice(2);
const { loadPyodide } = await import(pathToFileURL(pyodidePath).href);
const started = performance.now();
const py = await loadPyodide();
const loadMs = performance.now() - started;
const rssAfterLoad = process.memoryUsage().rss;
py.FS.mkdirTree('/repo');
py.FS.mount(py.FS.filesystems.NODEFS, { root: realpathSync(repository) }, '/repo');
const rows = [];
for (const row of JSON.parse(foundationsJson)) {
  const importStart = performance.now();
  const call = py.runPython(`
import json, sys
sys.path.insert(0, ${JSON.stringify(`/repo/${row.path}`)})
${row.prelude}
def call(text):
    return json.dumps(${row.expression})
call
`);
  const importMs = performance.now() - importStart;
  const text = JSON.stringify(row.arguments);
  const windowStart = process.hrtime.bigint();
  const callStart = performance.now();
  let output;
  for (let i = 0; i < Number(callsText); i++) output = call(text);
  const callMs = performance.now() - callStart;
  rows.push({ foundation: row.foundation, import_ms: importMs, per_call_us: callMs * 1000 / Number(callsText), calls: Number(callsText),
    window_ns: [String(windowStart), String(process.hrtime.bigint())], output_bytes: output.length, rss_mib: process.memoryUsage().rss / 1048576 });
}
process.stdout.write(JSON.stringify({ load_ms: loadMs, rss_after_load_mib: rssAfterLoad / 1048576, rows }));
process.exit(0);
