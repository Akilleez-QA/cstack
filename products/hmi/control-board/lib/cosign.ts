// the owner's phone co-sign for all-clear: a WebAuthn (passkey) assertion over a challenge that binds the exact all-clear.
//   challenge = sha256(canon({op:"all-clear-cosign", intent, scope, nonce, exp}))   (same bytes in ledger.py verify_cosign)
// intent = the DECISION-004 intent hash of the attached proof (or null), scope = sorted targets, nonce = board-issued, single use.
// Verified with node crypto only: ES256 (P-256) over authenticatorData || sha256(clientDataJSON); UP and UV flags required.
// COSIGN_PASSKEY_JSON (public only): {"credentialId": b64url, "spki": b64 DER, "rpId": host, "origins": ["https://host"]}
import { createHash, createPublicKey, verify } from "crypto";
import { canon } from "./ledger";

export class CosignDenied extends Error {}
export type Cosigner = { credentialId: string; spki: string; rpId: string; origins: string[] };
export type Binding = { intent: string | null; scope: string[]; nonce: string; exp: number };
export type Assertion = Binding & { credentialId: string; authenticatorData: string; clientDataJSON: string; signature: string };
export const MAX_TTL_SEC = 600;

const b64u = (b: Buffer) => b.toString("base64url");
export const challengeFor = (b: Binding) =>
  createHash("sha256").update(canon({ op: "all-clear-cosign", intent: b.intent, scope: [...b.scope].sort(), nonce: b.nonce, exp: b.exp })).digest();

export function loadCosigner(json: string | undefined): Cosigner {
  if (!json) throw new CosignDenied("COSIGN_PASSKEY_JSON not set");
  const c = JSON.parse(json) as Cosigner;
  if (!c.credentialId || !c.spki || !c.rpId || !Array.isArray(c.origins) || !c.origins.length) throw new CosignDenied("bad cosigner config");
  return c;
}

/** Throws CosignDenied unless `a` is the owner's passkey signing exactly `want` (intent + scope), unexpired. Returns the sign count. */
export function verifyCosign(a: Assertion, want: { intent: string | null; scope: string[] }, c: Cosigner, nowSec: number): number {
  if (!a || typeof a !== "object") throw new CosignDenied("absent");
  if (a.credentialId !== c.credentialId) throw new CosignDenied("unknown-credential");
  if (a.intent !== want.intent || canon([...a.scope].sort()) !== canon([...want.scope].sort())) throw new CosignDenied("binding-mismatch");
  if (!Number.isSafeInteger(a.exp) || a.exp < nowSec || a.exp > nowSec + MAX_TTL_SEC) throw new CosignDenied("expired");
  const cd = Buffer.from(a.clientDataJSON, "base64url"), ad = Buffer.from(a.authenticatorData, "base64url");
  let client: { type?: string; challenge?: string; origin?: string };
  try { client = JSON.parse(cd.toString("utf8")); } catch { throw new CosignDenied("bad-client-data"); }
  if (client.type !== "webauthn.get") throw new CosignDenied("bad-client-data");
  if (client.challenge !== b64u(challengeFor(a))) throw new CosignDenied("challenge-mismatch");
  if (!c.origins.includes(String(client.origin))) throw new CosignDenied("bad-origin");
  if (ad.length < 37 || !ad.subarray(0, 32).equals(createHash("sha256").update(c.rpId).digest())) throw new CosignDenied("bad-rp");
  if ((ad[32] & 0x05) !== 0x05) throw new CosignDenied("needs-user-presence-and-verification");
  const key = createPublicKey({ key: Buffer.from(c.spki, "base64"), format: "der", type: "spki" });
  const msg = Buffer.concat([ad, createHash("sha256").update(cd).digest()]);
  let ok = false;
  try { ok = verify("sha256", msg, key, Buffer.from(a.signature, "base64url")); } catch { ok = false; }
  if (!ok) throw new CosignDenied("bad-signature");
  return ad.readUInt32BE(33);
}

export type CosignResult = { ok: true; note: string; signCount?: number } | { ok: false; status: number; error: string };
/** Route policy. `take(nonce)` must atomically consume a board-issued nonce (Redis GETDEL) and return true only once. */
export async function cosignGate(o: { required: boolean; enforce: boolean; assertion: unknown; intent: string | null; scope: string[];
  cosignerJson?: string; nowSec: number; take: (nonce: string) => Promise<boolean> }): Promise<CosignResult> {
  if (!o.required) return { ok: true, note: "not-required" };
  let n: number;
  try { n = verifyCosign(o.assertion as Assertion, { intent: o.intent, scope: o.scope }, loadCosigner(o.cosignerJson), o.nowSec); }
  catch (e) {
    const why = e instanceof CosignDenied ? e.message : "malformed";
    const note = o.assertion ? `invalid:${why}` : "absent";
    return o.enforce ? { ok: false, status: 403, error: `cosign: ${note}` } : { ok: true, note: `log-only:${note}` };
  }
  if (!(await o.take((o.assertion as Assertion).nonce))) {
    return o.enforce ? { ok: false, status: 409, error: "cosign: nonce-unknown-or-used" } : { ok: true, note: "log-only:nonce-unknown-or-used" };
  }
  return { ok: true, note: o.enforce ? "ok" : "log-only:ok", signCount: n };
}
