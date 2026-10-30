// Minimal Upstash Redis REST client (no SDK). Keys:
//   shields:state:<machine>  -> JSON DesiredState (latest decision for that machine)
//   shields:checkin:<machine> -> JSON last check-in (reported level, hashes, ts)
//   shields:ledger            -> Redis list, append-only POODO records (decision/attempt/receipt)
//   shields:cseq:<machine>    -> last accepted check-in sequence number (replay guard)
//   shields:nonce:<machine>:<nonce> -> seen check-in nonce, expires after NONCE_TTL_SEC
//   ledger:used:<intent hash>  -> DECISION-004 intent consumed by the board (SET NX, never expires)
//   cosign:nonce:<nonce>       -> board-issued phone co-sign nonce, consumed once (GETDEL), expires after 10 min
//   shields:proof:<id> / shields:cosign:<id> -> all-clear proof and phone co-sign kept with the decision, served to pollers
import { CLAIM_LUA, NONCE_TTL_SEC } from "./checkin";
const URL_ = process.env.UPSTASH_REDIS_REST_URL!;
const TOKEN = process.env.UPSTASH_REDIS_REST_TOKEN!;

async function cmd<T = unknown>(...args: (string | number)[]): Promise<T> {
  const r = await fetch(URL_, {
    method: "POST",
    headers: { Authorization: `Bearer ${TOKEN}`, "Content-Type": "application/json" },
    body: JSON.stringify(args),
    cache: "no-store",
  });
  if (!r.ok) throw new Error(`store ${r.status}`);
  return ((await r.json()) as { result: T }).result;
}

export type Level = 0 | 1 | 2;
export interface DesiredState {
  machine: string; level: Level; seq: number; decision_id: string;
  authorized_by: string; issued_at: number; expires_at: number; rollback_min: number;
}
export interface LedgerRecord { type: "decision" | "attempt" | "receipt" | "denied" | "alarm" | "cosign"; id: string; ts: string; [k: string]: unknown }

export const getJSON = async <T>(k: string) => { const v = await cmd<string | null>("GET", k); return v ? (JSON.parse(v) as T) : null; };
export const setJSON = (k: string, v: unknown) => cmd("SET", k, JSON.stringify(v));
export const nextSeq = (machine: string) => cmd<number>("INCR", `shields:seq:${machine}`);
export const appendLedger = (rec: LedgerRecord) => cmd("RPUSH", "shields:ledger", JSON.stringify(rec));
export const readLedger = async (n = 200) =>
  ((await cmd<string[]>("LRANGE", "shields:ledger", -n, -1)) ?? []).map((s) => JSON.parse(s) as LedgerRecord);
/** DECISION-004 single use on the board: true only for the first caller for this intent hash. */
export const issueCosignNonce = (nonce: string, ttl: number) => cmd("SET", `cosign:nonce:${nonce}`, "1", "EX", ttl);
export const takeCosignNonce = async (nonce: string) => /^[0-9a-f]{32}$/.test(nonce) && (await cmd<string | null>("GETDEL", `cosign:nonce:${nonce}`)) === "1";
export const claimLedgerIntent = async (hash: string) => (await cmd<string | null>("SET", `ledger:used:${hash}`, "1", "NX")) === "OK";
/** Atomically accept a check-in (cseq newer than last AND nonce unseen). 1 ok, 0 stale cseq, -1 nonce reused. */
export const claimCheckin = (machine: string, cseq: number, nonce: string) =>
  cmd<number>("EVAL", CLAIM_LUA, 2, `shields:cseq:${machine}`, `shields:nonce:${machine}:${nonce}`, cseq, NONCE_TTL_SEC);
