// Generates the TS types from the JSON Schemas. The schemas are the source of truth.
// `--check` fails when a generated file is stale, so CI catches a hand edit or a forgotten regen.
import { readFileSync, writeFileSync } from 'node:fs';
import { compile } from 'json-schema-to-typescript';

const here = new URL('..', import.meta.url);
const targets = [{ schema: 'schema/intent.schema.json', out: 'src/intent.generated.ts' }];
const check = process.argv.includes('--check');
let stale = 0;

for (const { schema, out } of targets) {
  const source = JSON.parse(readFileSync(new URL(schema, here), 'utf8'));
  const text = await compile(source, source.title, {
    bannerComment: `// GENERATED from ${schema} by scripts/gen.ts. Do not edit; run \`npm run gen\`.`,
    unreachableDefinitions: true,
    additionalProperties: false,
    ignoreMinAndMaxItems: true,
    style: { singleQuote: true },
  });
  const path = new URL(out, here);
  if (check) {
    let current = '';
    try { current = readFileSync(path, 'utf8'); } catch {}
    if (current !== text) { console.error(`stale: ${out} (run npm run gen)`); stale++; }
  } else {
    writeFileSync(path, text);
    console.log(`wrote ${out}`);
  }
}
process.exit(stale ? 1 : 0);
