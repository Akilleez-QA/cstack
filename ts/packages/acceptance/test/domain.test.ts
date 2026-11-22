import { test } from 'node:test';
import assert from 'node:assert/strict';
import { difference, draw, seeded, ulps } from '@cstack/acceptance';

test('domain terms draw values in range, with edges, and refuse unknown terms', () => {
  const { rand } = seeded('t');
  const seen = new Set<number>();
  for (let i = 0; i < 2000; i++) {
    const v = draw('int[-3..3]', rand) as number;
    assert.ok(Number.isInteger(v) && v >= -3 && v <= 3);
    seen.add(v);
  }
  assert.equal(seen.size, 7);
  const xs = draw('u8[2..4]', rand) as number[];
  assert.ok(xs.length >= 2 && xs.length <= 4 && xs.every((x) => x >= 0 && x <= 255));
  assert.deepEqual(draw({ a: { const: 'x' }, b: [1, null, true] }, rand), { a: 'x', b: [1, null, true] });
  assert.equal(typeof draw('bool', rand), 'boolean');
  assert.throws(() => draw('i33', rand), /unknown domain term/);
  assert.throws(() => draw('int[5..1]', rand), /empty range/);
  const edges = Array.from({ length: 500 }, () => draw('i32', rand));
  assert.ok(edges.includes(2147483647) && edges.includes(-2147483648));
});

test('the same seed text gives the same draws', () => {
  const a = seeded('same'), b = seeded('same');
  assert.equal(a.seed, b.seed);
  assert.deepEqual(draw('i32[5..5]', a.rand), draw('i32[5..5]', b.rand));
});

test('comparison is exact by default and allows tolerance_ulps on numbers', () => {
  assert.equal(ulps(1, 1 + Number.EPSILON), 1);
  assert.equal(ulps(-0, 0), 0);
  assert.equal(difference([1, 2], [1, 2], 0), null);
  assert.match(difference([1, 2.0000000000000004], [1, 2], 0)!, /\/1: expected 2/);
  assert.equal(difference([1, 2.0000000000000004], [1, 2], 1), null);
  assert.match(difference({ a: 1, b: 2 }, { a: 1 }, 0)!, /\/b: unexpected key/);
  assert.match(difference('x', 1, 0)!, /expected a number/);
  assert.match(difference(Number.NaN, 1, 1000)!, /expected 1/);
});
