import { test } from "node:test";
import assert from "node:assert/strict";
import { CLAIM_LUA, FRESH_SEC, NONCE_TTL_SEC, parseGuard } from "../lib/checkin";

const now = 1_800_000_000;
const ok = { machine: "host-a", ts: now, cseq: now * 1000, nonce: "a".repeat(32) };

test("accepts a fresh payload with cseq + nonce", () => {
  assert.deepEqual(parseGuard(ok, now), { ok: true, cseq: ok.cseq, nonce: ok.nonce });
});
test("rejects stale or future ts", () => {
  assert.equal(parseGuard({ ...ok, ts: now - FRESH_SEC - 1 }, now).ok, false);
  assert.equal(parseGuard({ ...ok, ts: now + FRESH_SEC + 1 }, now).ok, false);
  assert.equal(parseGuard({ ...ok, ts: "x" }, now).ok, false);
});
test("rejects old-format check-ins without cseq/nonce (pre-hardening poller)", () => {
  const { cseq: _c, nonce: _n, ...legacy } = ok;
  assert.deepEqual(parseGuard(legacy, now), { ok: false, error: "missing cseq" });
});
test("rejects bad cseq", () => {
  for (const cseq of [0, -1, 1.5, "5", Number.MAX_SAFE_INTEGER + 2]) assert.equal(parseGuard({ ...ok, cseq }, now).ok, false);
});
test("rejects bad nonce", () => {
  for (const nonce of ["", "abc", "A".repeat(32), "g".repeat(32), 123]) assert.equal(parseGuard({ ...ok, nonce }, now).ok, false);
});
test("nonce memory outlives the ts window; claim script checks cseq before nonce and only then advances", () => {
  assert.ok(NONCE_TTL_SEC > FRESH_SEC);
  const iCseq = CLAIM_LUA.indexOf("<= last"), iNx = CLAIM_LUA.indexOf("'NX'"), iSet = CLAIM_LUA.lastIndexOf("redis.call('SET', KEYS[1]");
  assert.ok(iCseq > 0 && iNx > iCseq && iSet > iNx);
});
