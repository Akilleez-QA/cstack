// Replay guard for POST /api/checkin. The poller signs {cseq, nonce, ts} inside the HMAC'd payload:
//   cseq  : strictly increasing per machine (poller uses max(last+1, unix ms), so a lost state file still moves forward)
//   nonce : 128-bit random hex, single use within the freshness window
//   ts    : unix seconds, must be within FRESH_SEC of server time
// The board accepts a check-in only if cseq > last accepted cseq AND the nonce is unseen (atomic, see store.claimCheckin).
export const FRESH_SEC = 300;
export const NONCE_TTL_SEC = 2 * FRESH_SEC; // nonce memory outlives the ts window, so a replay can't wait it out

export type Guard = { ok: true; cseq: number; nonce: string } | { ok: false; error: string };

export function parseGuard(payload: Record<string, unknown>, nowSec: number): Guard {
  const ts = Number(payload.ts);
  if (!Number.isFinite(ts) || Math.abs(nowSec - ts) > FRESH_SEC) return { ok: false, error: "stale" };
  const cseq = payload.cseq;
  if (typeof cseq !== "number" || !Number.isSafeInteger(cseq) || cseq <= 0) return { ok: false, error: "missing cseq" };
  const nonce = payload.nonce;
  if (typeof nonce !== "string" || !/^[0-9a-f]{32}$/.test(nonce)) return { ok: false, error: "missing nonce" };
  return { ok: true, cseq, nonce };
}

// Atomic compare-and-set run inside Redis (Upstash EVAL). KEYS[1]=last cseq, KEYS[2]=nonce key. ARGV[1]=cseq, ARGV[2]=nonce ttl.
// Returns 1 accepted, 0 cseq not newer (replay/reorder), -1 nonce reused.
export const CLAIM_LUA = `
local last = tonumber(redis.call('GET', KEYS[1]) or '0')
if tonumber(ARGV[1]) <= last then return 0 end
if not redis.call('SET', KEYS[2], '1', 'NX', 'EX', ARGV[2]) then return -1 end
redis.call('SET', KEYS[1], ARGV[1])
return 1`;

export const CLAIM_RESULT: Record<number, string> = { 1: "ok", 0: "replay: cseq not newer", [-1]: "replay: nonce reused" };
