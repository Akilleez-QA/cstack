// DECISION-004 verifier for the board (Vercel cannot run ledger.py or reach the tailnet). Same format, same rules:
// an all-clear (level 0) is accepted only with a signed intent for exactly this action, linked by hash chain to a
// checkpoint co-signed by a quorum of roster witnesses, and not used before. Raising shields (1|2) never needs it.
// LEDGER_ENFORCE=1 turns verification into a hard gate; otherwise the result is only recorded ("log-only").
// LEDGER_ROSTER_JSON holds public keys only: {"quorum":2,"witnesses":{name:hex},"writers":{name:{"pub":hex,"node":origin}}}
import { createHash, createPublicKey, verify as edVerify } from "node:crypto";

export type Json = null | boolean | number | string | Json[] | { [k: string]: Json };
export interface Entry { [k: string]: Json }
export interface Cosig { name: string; ts: number; sig: string }
export interface Bundle { intent: Entry; chain: Entry[]; checkpoint: { size: number; head: string; cosigs: Cosig[] } }
export interface Roster { quorum: number; witnesses: Record<string, string>; writers: Record<string, { pub: string; node: string }> }
export class LedgerDenied extends Error {}

/** Byte-identical to Python json.dumps(o, sort_keys=True, separators=(",",":")) with ensure_ascii. */
export function canon(o: Json): string {
  if (o === null || typeof o === "boolean") return String(o);
  if (typeof o === "number") { if (!Number.isSafeInteger(o)) throw new LedgerDenied("non-integer number"); return String(o); }
  if (typeof o === "string") {
    let s = '"';
    for (const ch of o) for (let i = 0; i < ch.length; i++) {
      const c = ch.charCodeAt(i), m: Record<number, string> = { 34: '\\"', 92: "\\\\", 10: "\\n", 13: "\\r", 9: "\\t", 8: "\\b", 12: "\\f" };
      s += m[c] ?? (c < 0x20 || c > 0x7e ? "\\u" + c.toString(16).padStart(4, "0") : ch[i]);
    }
    return s + '"';
  }
  if (Array.isArray(o)) return "[" + o.map(canon).join(",") + "]";
  return "{" + Object.keys(o).sort((a, b) => (a < b ? -1 : a > b ? 1 : 0)).map((k) => canon(k) + ":" + canon(o[k])).join(",") + "}";
}
export const sha = (s: string | Buffer) => createHash("sha256").update(s).digest("hex");
export const digest = (action: Json) => sha(canon(action));

const SPKI = Buffer.from("302a300506032b6570032100", "hex");
export function okSig(pubHex: string, sigB64: string, msg: Buffer | string): boolean {
  try {
    const raw = Buffer.from(pubHex, "hex"); if (raw.length !== 32) return false;
    const key = createPublicKey({ key: Buffer.concat([SPKI, raw]), format: "der", type: "spki" });
    return edVerify(null, Buffer.isBuffer(msg) ? msg : Buffer.from(msg), key, Buffer.from(sigB64, "base64"));
  } catch { return false; }
}
export const cpText = (origin: string, size: number, head: string) => `${origin}\n${size}\n${head}\n`;
function cosigMsg(ts: number, origin: string, size: number, head: string) {
  const b = Buffer.alloc(8); b.writeBigUInt64BE(BigInt(ts)); return Buffer.concat([b, Buffer.from(cpText(origin, size, head))]);
}

export function loadRoster(json: string | undefined): Roster {
  if (!json) throw new LedgerDenied("LEDGER_ROSTER_JSON not set");
  const r = JSON.parse(json) as Roster;
  if (!(r.quorum >= 2) || Object.keys(r.witnesses ?? {}).length < r.quorum || typeof r.writers !== "object") throw new LedgerDenied("roster needs quorum >= 2 witnesses");
  return r;
}

function checkEntry(e: Entry, origin: string, roster: Roster) {
  const { sig, hash, ...body } = e;
  const w = roster.writers[String(e.writer)];
  if (e.origin !== origin || !w || w.node !== origin) throw new LedgerDenied("unknown-writer-or-origin");
  if (typeof sig !== "string" || !okSig(w.pub, sig, canon(body))) throw new LedgerDenied("bad-signature");
  if (hash !== sha(canon({ ...body, sig }))) throw new LedgerDenied("hash-mismatch");
}

/** Throws LedgerDenied unless the bundle proves a quorum-witnessed, unconsumed intent for exactly `action`. Returns the intent hash. */
export function verifyIntent(b: Bundle, action: Json, roster: Roster): string {
  const it = b?.intent, chain = b?.chain, cp = b?.checkpoint;
  if (!it || !Array.isArray(chain) || !cp || !Array.isArray(cp.cosigs)) throw new LedgerDenied("no-intent");
  const origin = String(it.origin);
  if (it.kind !== "intent") throw new LedgerDenied("no-intent");
  checkEntry(it, origin, roster);
  if ((it.body as Entry | null)?.digest !== digest(action)) throw new LedgerDenied("intent-digest-mismatch");
  if (chain[0]?.hash !== it.hash) throw new LedgerDenied("chain-must-start-at-intent");
  for (let i = 1; i < chain.length; i++) {
    const e = chain[i], p = chain[i - 1];
    checkEntry(e, origin, roster);
    if (e.seq !== (p.seq as number) + 1 || e.prev !== p.hash) throw new LedgerDenied("chain-break");
    if ((e.kind === "claim" || e.kind === "result") && e.ref === it.hash) throw new LedgerDenied("intent-already-used");
  }
  const last = chain[chain.length - 1];
  if (last.seq !== cp.size || last.hash !== cp.head) throw new LedgerDenied("checkpoint-does-not-cover-intent");
  const good = new Set<string>();
  for (const c of cp.cosigs) {
    const pk = roster.witnesses[c?.name];
    if (pk && Number.isSafeInteger(c.ts) && okSig(pk, c.sig, cosigMsg(c.ts, origin, cp.size, cp.head))) good.add(c.name);
  }
  if (good.size < roster.quorum) throw new LedgerDenied("intent-not-witnessed-by-quorum");
  return String(it.hash);
}

export type GateResult = { ok: true; note: string; intent?: string } | { ok: false; status: number; error: string };
/** The route-level policy. `claim(hash)` must be atomic (Redis SET NX) and return true only for the first caller. */
export async function ledgerGate(opts: { required: boolean; enforce: boolean; bundle: unknown; action: Json; rosterJson?: string;
  claim: (hash: string) => Promise<boolean> }): Promise<GateResult> {
  if (!opts.required) return { ok: true, note: "not-required" };
  let h: string;
  try { h = verifyIntent(opts.bundle as Bundle, opts.action, loadRoster(opts.rosterJson)); }
  catch (e) {
    const why = e instanceof LedgerDenied ? e.message : "malformed";
    const note = opts.bundle ? `invalid:${why}` : "absent";
    return opts.enforce ? { ok: false, status: 403, error: `ledger: ${note}` } : { ok: true, note: `log-only:${note}` };
  }
  if (!opts.enforce) return { ok: true, note: "log-only:ok", intent: h };  // log-only never consumes
  if (!(await opts.claim(h))) return { ok: false, status: 409, error: "ledger: intent-already-used" };
  return { ok: true, note: "ok", intent: h };
}
