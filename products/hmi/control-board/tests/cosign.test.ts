import { test } from "node:test";
import assert from "node:assert/strict";
import { createHash, generateKeyPairSync, sign } from "crypto";
import { challengeFor, cosignGate, CosignDenied, verifyCosign, type Assertion } from "../lib/cosign";

// Synthetic phone authenticator (P-256), producing assertions the way navigator.credentials.get does.
const now = 1_800_000_000, rpId = "shields.example.com", origin = `https://${rpId}`;
const kp = generateKeyPairSync("ec", { namedCurve: "P-256" });
const cfg = { credentialId: "cred-1", spki: kp.publicKey.export({ format: "der", type: "spki" }).toString("base64"), rpId, origins: [origin] };
const want = { intent: "ab".repeat(32), scope: ["host-a", "box"] };
function assertion(o: { flags?: number; rp?: string; origin?: string; type?: string; key?: typeof kp.privateKey; exp?: number; tamper?: boolean } = {}): Assertion {
  const b = { intent: want.intent, scope: ["box", "host-a"], nonce: "0".repeat(32), exp: o.exp ?? now + 300 };
  const cd = Buffer.from(JSON.stringify({ type: o.type ?? "webauthn.get", challenge: challengeFor(b).toString("base64url"), origin: o.origin ?? origin }));
  const ad = Buffer.concat([createHash("sha256").update(o.rp ?? rpId).digest(), Buffer.from([o.flags ?? 0x05]), Buffer.from([0, 0, 0, 7])]);
  const sig = sign("sha256", Buffer.concat([ad, createHash("sha256").update(cd).digest()]), o.key ?? kp.privateKey);
  if (o.tamper) ad[36] = 8;
  return { ...b, credentialId: "cred-1", authenticatorData: ad.toString("base64url"), clientDataJSON: cd.toString("base64url"), signature: sig.toString("base64url") };
}
const denied = (a: Assertion, why: string, w = want) => assert.throws(() => verifyCosign(a, w, cfg, now), (e: Error) => e instanceof CosignDenied && e.message === why);

test("challenge bytes match ledger.py (Python canon + sha256)", () => {
  const b = { intent: "ab".repeat(32), scope: ["host-a", "box"], nonce: "0".repeat(32), exp: 1_800_000_300 };
  assert.equal(challengeFor(b).toString("hex"), "5da0b3197f32128a7251f78335fb8b84f25a49ec14e8936e0a4047797adc8659");
  assert.equal(challengeFor({ ...b, intent: null }).toString("hex"), "7311d5a0dd2b96b94220b235155f0e001aa8af6e1da936ce90c6bc27097fc89d");
});
test("valid phone assertion verifies and returns the sign count", () => assert.equal(verifyCosign(assertion(), want, cfg, now), 7));
test("rejects wrong binding, expiry, origin, rp, flags, type, key, tampering", () => {
  denied(assertion(), "binding-mismatch", { ...want, intent: "cd".repeat(32) });
  denied(assertion(), "binding-mismatch", { ...want, scope: ["box"] });
  denied(assertion({ exp: now - 1 }), "expired");
  denied(assertion({ exp: now + 3600 }), "expired");
  denied(assertion({ origin: "https://evil.example" }), "bad-origin");
  denied(assertion({ rp: "evil.example" }), "bad-rp");
  denied(assertion({ flags: 0x01 }), "needs-user-presence-and-verification");  // UP without UV
  denied(assertion({ type: "webauthn.create" }), "bad-client-data");
  denied(assertion({ key: generateKeyPairSync("ec", { namedCurve: "P-256" }).privateKey }), "bad-signature");
  denied(assertion({ tamper: true }), "bad-signature");
  denied({ ...assertion(), nonce: "1".repeat(32) }, "challenge-mismatch");
  denied({ ...assertion(), credentialId: "other" }, "unknown-credential");
});
test("gate: off by default records only; enforcing denies absent/invalid and single-uses the nonce", async () => {
  const used = new Set<string>();
  const take = async (n: string) => (used.has(n) ? false : (used.add(n), true));
  const base = { required: true, intent: want.intent, scope: want.scope, cosignerJson: JSON.stringify(cfg), nowSec: now, take };
  assert.deepEqual(await cosignGate({ ...base, enforce: false, assertion: undefined }), { ok: true, note: "log-only:absent" });
  assert.deepEqual(await cosignGate({ ...base, enforce: true, assertion: undefined }), { ok: false, status: 403, error: "cosign: absent" });
  assert.deepEqual(await cosignGate({ ...base, enforce: true, assertion: assertion({ flags: 1 }) }),
    { ok: false, status: 403, error: "cosign: invalid:needs-user-presence-and-verification" });
  const a = assertion();
  assert.deepEqual(await cosignGate({ ...base, enforce: true, assertion: a }), { ok: true, note: "ok", signCount: 7 });
  assert.deepEqual(await cosignGate({ ...base, enforce: true, assertion: a }), { ok: false, status: 409, error: "cosign: nonce-unknown-or-used" });
  assert.deepEqual(await cosignGate({ ...base, enforce: true, assertion: undefined, cosignerJson: undefined }), { ok: false, status: 403, error: "cosign: absent" });
  assert.deepEqual(await cosignGate({ ...base, required: false, enforce: true, assertion: undefined }), { ok: true, note: "not-required" });
});
