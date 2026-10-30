// POST /api/level {machine|"all", level, reason, rollback_min}: the ONLY write path for desired state.
// Clerk session + single allowed user + fresh MFA (reverification strict_mfa) required.
// Level 0 (all-clear) also needs a DECISION-004 proof in body.ledger (`ledger.py bundle`) when LEDGER_ENFORCE=1;
// otherwise the proof is only checked and recorded. Raising shields (1|2) never needs it. A verified proof is stored as
// shields:proof:<decision id> and served beside the signed state, so pollers can verify it themselves.
// Level 0 also takes the owner's phone co-sign in body.cosign (WebAuthn assertion, see lib/cosign.ts, challenge from /api/cosign),
// bound to the proof's intent hash + scope. COSIGN_ENFORCE=1 requires it; default only verifies and records it.
// Writes a POODO decision record first, then the new desired state. Machines report attempts and receipts via /api/checkin.
import { NextResponse } from "next/server";
import { auth, reverificationError } from "@clerk/nextjs/server";
import { MACHINES } from "@/lib/sign";
import { appendLedger, claimLedgerIntent, takeCosignNonce, nextSeq, setJSON, type DesiredState, type Level } from "@/lib/store";
import { decisionId, nowIso } from "@/lib/ids";
import { ledgerGate } from "@/lib/ledger";
import { cosignGate } from "@/lib/cosign";

export async function POST(req: Request) {
  const { userId, has } = await auth();
  if (!userId || userId !== process.env.SHIELDS_ALLOWED_USER_ID) return NextResponse.json({ error: "forbidden" }, { status: 403 });
  if (!has({ reverification: "strict_mfa" })) return NextResponse.json(reverificationError("strict_mfa"), { status: 403 });

  const body = (await req.json()) as { machine: string; level: number; reason?: string; rollback_min?: number; ledger?: unknown; cosign?: unknown };
  const level = body.level as Level;
  if (![0, 1, 2].includes(level)) return NextResponse.json({ error: "level must be 0|1|2" }, { status: 400 });
  const targets = body.machine === "all" ? MACHINES : [body.machine];
  if (!targets.every((m) => MACHINES.includes(m))) return NextResponse.json({ error: "unknown machine" }, { status: 400 });
  const rollback_min = Math.min(Math.max(body.rollback_min ?? 60, 5), 24 * 60);

  // Phone co-sign first (cheap to redo), bound to the attached proof's intent hash; then the ledger gate consumes the intent.
  const scope = [...targets].sort();
  const intentOf = (body.ledger as { intent?: { hash?: unknown } } | undefined)?.intent?.hash;
  const cs = await cosignGate({ required: level === 0, enforce: process.env.COSIGN_ENFORCE === "1", assertion: body.cosign,
    intent: typeof intentOf === "string" ? intentOf : null, scope, cosignerJson: process.env.COSIGN_PASSKEY_JSON,
    nowSec: Math.floor(Date.now() / 1000), take: takeCosignNonce });
  if (!cs.ok) {
    await appendLedger({ type: "denied", id: "none", ts: nowIso(), authorized_by: `board:${userId}`, level, scope: targets, reason: cs.error, channel: "control-board" });
    return NextResponse.json({ error: cs.error }, { status: cs.status });
  }
  const lg = await ledgerGate({ required: level === 0, enforce: process.env.LEDGER_ENFORCE === "1", bundle: body.ledger,
    action: { op: "all-clear", scope: [...targets].sort() }, rosterJson: process.env.LEDGER_ROSTER_JSON, claim: claimLedgerIntent });
  if (!lg.ok) {
    await appendLedger({ type: "denied", id: "none", ts: nowIso(), authorized_by: `board:${userId}`, level, scope: targets, reason: lg.error, channel: "control-board" });
    return NextResponse.json({ error: lg.error }, { status: lg.status });  // before any decision or state write
  }
  const id = decisionId();
  const issued_at = Math.floor(Date.now() / 1000);
  await appendLedger({ type: "decision", id, ts: nowIso(), authorized_by: `board:${userId}`, level, scope: targets,
    reason: body.reason ?? "", rollback_min, channel: "control-board", ledger: lg.note, ledger_intent: lg.intent, cosign: cs.note });
  if (cs.signCount !== undefined) {  // the co-sign itself, as its own append-only ledger record, and kept for pollers to re-verify
    await appendLedger({ type: "cosign", id, ts: nowIso(), authorized_by: `phone:${(body.cosign as { credentialId: string }).credentialId}`,
      level, scope: targets, ledger_intent: intentOf ?? null, sign_count: cs.signCount, note: cs.note, channel: "control-board" });
    await setJSON(`shields:cosign:${id}`, body.cosign);
  }
  // Keep the verified proof with the decision: the state route serves it so each poller re-verifies it offline (rig roster).
  if (lg.intent) await setJSON(`shields:proof:${id}`, { action: { op: "all-clear", scope: [...targets].sort() }, bundle: body.ledger });
  for (const machine of targets) {
    const st: DesiredState = { machine, level, seq: await nextSeq(machine), decision_id: id, authorized_by: `board:${userId}`,
      issued_at, expires_at: issued_at + 24 * 3600, rollback_min };
    await setJSON(`shields:state:${machine}`, st);
  }
  // Outcome is not known here. It stays "pending" until each machine's receipt arrives.
  return NextResponse.json({ id, targets, level, outcome: "pending" });
}
