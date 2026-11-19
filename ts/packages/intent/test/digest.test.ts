import { test } from 'node:test';
import assert from 'node:assert/strict';
import { canonical, digest, parseStrict, schemaProblems } from '@cstack/contracts';
import { vectors, sample } from './helpers.ts';

test('every Python golden vector has the same canonical bytes and digest in TS', () => {
  assert.ok(vectors.vectors.length >= 9);
  for (const v of vectors.vectors) {
    assert.equal(canonical(v.value), v.canonical, v.name);
    assert.equal(digest(v.value), v.sha256, v.name);
  }
});

test('floats and unsafe integers are refused, because the intent contract is float-free', () => {
  // Plain JSON.parse would turn Python's `1.0` into 1 and digest it as `1`: a silent mismatch.
  for (const v of vectors.ts_refuses) assert.throws(() => parseStrict(v.canonical), /safe integers/, v.name);
  assert.throws(() => canonical({ x: 1.5 }), /safe integers/);
  assert.throws(() => canonical({ x: 2 ** 53 + 2 }), /safe integers/);
  for (const v of vectors.vectors) assert.equal(canonical(parseStrict(v.canonical)), v.canonical, v.name);
  assert.throws(() => canonical({ x: Number.NaN }));
  assert.throws(() => canonical({ x: undefined }));
  assert.throws(() => canonical(new Map()));
});

test('key order and digest do not depend on insertion order', () => {
  assert.equal(digest({ a: 1, b: [1, 2] }), digest({ b: [1, 2], a: 1 }));
});

test('the sample contract is schema-valid, and the schema refuses unknown fields and floats', () => {
  assert.deepEqual(schemaProblems(sample()), []);
  assert.notDeepEqual(schemaProblems({ ...sample(), extra: 1 }), []);
  const floaty = sample();
  floaty.limits.budget_cents = 1.5;
  assert.notDeepEqual(schemaProblems(floaty), []);
  const kinds = sample();
  (kinds.acceptance[0]!.check as { kind: string }).kind = 'vibes';
  assert.notDeepEqual(schemaProblems(kinds), []);
});
