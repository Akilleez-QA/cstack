// POST /api/checkin {payload:{machine, level, seq_applied, decision_id, outcome, before, after, checks, ts, cseq, nonce}, sig}
// The machine signs with its own HMAC key. cseq + nonce + ts are inside the signed payload, so a captured check-in
// can't be replayed (see lib/checkin.ts). An applied level-0 receipt may carry body.ledger, a DECISION-004 proof for
// {op:"checkin", machine, decision_id, level:0}. Reports of reality are never refused: with LEDGER_ENFORCE=1 a missing,
// invalid or reused proof is recorded as an alarm on the receipt instead (rollback timers lower shields without one). Records last check-in and appends an attempt/receipt to the ledger.
import { NextResponse } from "next/server";
import { MACHINES, verify } from "@/lib/sign";
import { appendLedger, claimCheckin, claimLedgerIntent, setJSON } from "@/lib/store";
import { CLAIM_RESULT, parseGuard } from "@/lib/checkin";
import { nowIso } from "@/lib/ids";
import { ledgerGate } from "@/lib/ledger";

const OUTCOMES = ["applied", "failed", "unknown", "held", "noop"];

export async function POST(req: Request) {
  let body: { payload: Record<string, unknown>; sig: string; ledger?: unknown };
  try {
    body = (await req.json()) as typeof body;
  } catch {
    return NextResponse.json({ error: "bad json" }, { status: 400 });
  }
  const { payload, sig } = body ?? {};
  const machine = String(payload?.machine ?? "");
  if (!MACHINES.includes(machine) || typeof sig !== "string" || !verify(machine, payload, sig))
    return NextResponse.json({ error: "bad signature" }, { status: 401 });
  const g = parseGuard(payload, Date.now() / 1000);
  if (!g.ok) return NextResponse.json({ error: g.error }, { status: 401 });
  const claimed = await claimCheckin(machine, g.cseq, g.nonce);
  if (claimed !== 1) return NextResponse.json({ error: CLAIM_RESULT[claimed] ?? "replay" }, { status: 409 });
  const outcome = OUTCOMES.includes(String(payload.outcome)) ? String(payload.outcome) : "unknown";
  const decision_id = String(payload.decision_id ?? "none");
  const lg = await ledgerGate({ required: outcome === "applied" && Number(payload.level) === 0, enforce: process.env.LEDGER_ENFORCE === "1",
    bundle: body.ledger, action: { op: "checkin", machine, decision_id, level: 0 }, rosterJson: process.env.LEDGER_ROSTER_JSON, claim: claimLedgerIntent });
  const ledger = lg.ok ? lg.note : `alarm:${lg.error}`;
  if (!lg.ok) await appendLedger({ type: "alarm", id: decision_id, ts: nowIso(), machine, reason: lg.error, channel: "poller" });
  await setJSON(`shields:checkin:${machine}`, { ...payload, outcome, ledger, received_at: nowIso() });
  if (outcome !== "noop") {
    await appendLedger({ type: "receipt", id: decision_id, ledger, ts: nowIso(), machine, outcome,
      level: payload.level, before: payload.before, after: payload.after, checks: payload.checks, cseq: g.cseq, channel: "poller" });
  }
  return NextResponse.json({ ok: true, ledger });
}
