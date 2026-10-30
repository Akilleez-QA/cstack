import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { canon, digest, ledgerGate, loadRoster, verifyIntent, type Bundle, type Json } from "../lib/ledger";

// Made by the Python prototype (tests/fixtures/make-ledger-fixture.py): public keys and signatures only.
const F = JSON.parse(readFileSync(join(__dirname, "../../tests/fixtures/ledger-python.json"), "utf8"));
const R = loadRoster(JSON.stringify(F.roster));
const clone = <T>(x: T): T => JSON.parse(JSON.stringify(x));
const denied = (b: unknown, a: Json, why: string) => assert.throws(() => verifyIntent(b as Bundle, a, R), { message: why });

test("canonical JSON and digest are byte-identical to Python (unicode, astral, control, DEL, nesting)", () => {
  assert.equal(canon(F.canon.value), F.canon.text);
  assert.equal(digest(F.canon.value), F.canon.digest);
  assert.throws(() => canon({ x: 1.5 }), /non-integer/);
});
test("Python-made all-clear and check-in proofs verify", () => {
  assert.equal(verifyIntent(F.allClear.bundle, F.allClear.action, R), F.allClear.bundle.intent.hash);
  assert.equal(verifyIntent(F.checkin.bundle, F.checkin.action, R), F.checkin.bundle.intent.hash);
});
test("denies a different action, an under-quorum checkpoint, and an intent already claimed", () => {
  denied(F.allClear.bundle, { op: "all-clear", scope: ["host-a", "box"] }, "intent-digest-mismatch");
  denied(F.checkin.bundle, { ...F.checkin.action, level: 1 }, "intent-digest-mismatch");
  denied(F.unwitnessed.bundle, F.unwitnessed.action, "intent-not-witnessed-by-quorum");
  denied(F.used.bundle, F.used.action, "intent-already-used");
});
test("denies tampering: body, signature, chain, checkpoint, duplicate cosigner, writer binding", () => {
  const a = F.allClear.action;
  let b = clone(F.allClear.bundle); b.intent.ts += 1; b.chain[0] = b.intent; denied(b, a, "bad-signature");
  b = clone(F.allClear.bundle); b.chain[1].prev = "0".repeat(64); denied(b, a, "bad-signature");
  b = clone(F.allClear.bundle); b.chain.pop(); denied(b, a, "checkpoint-does-not-cover-intent");
  b = clone(F.allClear.bundle); b.chain = [b.chain[1]]; denied(b, a, "chain-must-start-at-intent");
  b = clone(F.allClear.bundle); b.checkpoint.cosigs = [b.checkpoint.cosigs[0], b.checkpoint.cosigs[0]]; denied(b, a, "intent-not-witnessed-by-quorum");
  b = clone(F.allClear.bundle); b.checkpoint.cosigs[1].ts += 1; denied(b, a, "intent-not-witnessed-by-quorum");
  const r2 = clone(F.roster); r2.writers["box-bot"].node = "host-a";
  assert.throws(() => verifyIntent(F.allClear.bundle, a, loadRoster(JSON.stringify(r2))), { message: "unknown-writer-or-origin" });
  denied(null, a, "no-intent");
  denied({ intent: F.allClear.bundle.intent }, a, "no-intent");
});
test("roster must carry a quorum of at least 2 witnesses", () => {
  assert.throws(() => loadRoster(undefined), /not set/);
  assert.throws(() => loadRoster(JSON.stringify({ ...F.roster, quorum: 1 })), /quorum/);
  assert.throws(() => loadRoster(JSON.stringify({ ...F.roster, witnesses: { a: "00" } })), /quorum/);
});

const roster = JSON.stringify(F.roster);
const atomicClaim = () => { const used = new Set<string>(); return async (h: string) => { await new Promise((r) => setImmediate(r)); if (used.has(h)) return false; used.add(h); return true; }; };
const gate = (o: Partial<Parameters<typeof ledgerGate>[0]>) =>
  ledgerGate({ required: true, enforce: true, bundle: F.allClear.bundle, action: F.allClear.action, rosterJson: roster, claim: atomicClaim(), ...o });

test("raising shields never needs the ledger", async () => {
  assert.deepEqual(await gate({ required: false, bundle: undefined, rosterJson: undefined }), { ok: true, note: "not-required" });
});
test("log-only (default) records the result, never blocks and never consumes", async () => {
  let calls = 0; const claim = async () => (calls++, true);
  assert.deepEqual(await gate({ enforce: false, bundle: undefined, claim }), { ok: true, note: "log-only:absent" });
  assert.deepEqual(await gate({ enforce: false, bundle: F.unwitnessed.bundle, claim }), { ok: true, note: "log-only:invalid:intent-digest-mismatch" });
  assert.equal((await gate({ enforce: false, claim })).ok, true);
  assert.equal(calls, 0);
});
test("enforcing: absent, invalid, or missing roster is 403; valid is accepted once, then 409", async () => {
  assert.deepEqual(await gate({ bundle: undefined }), { ok: false, status: 403, error: "ledger: absent" });
  assert.deepEqual(await gate({ bundle: F.unwitnessed.bundle, action: F.unwitnessed.action }), { ok: false, status: 403, error: "ledger: invalid:intent-not-witnessed-by-quorum" });
  assert.equal((await gate({ rosterJson: undefined })).ok, false);
  const claim = atomicClaim();
  assert.deepEqual(await gate({ claim }), { ok: true, note: "ok", intent: F.allClear.bundle.intent.hash });
  assert.deepEqual(await gate({ claim }), { ok: false, status: 409, error: "ledger: intent-already-used" });
});
test("enforcing: 10 concurrent requests on one intent, exactly one wins", async () => {
  const claim = atomicClaim();
  const out = await Promise.all(Array.from({ length: 10 }, () => gate({ claim })));
  assert.equal(out.filter((r) => r.ok).length, 1);
  assert.equal(out.filter((r) => !r.ok && r.status === 409).length, 9);
});
