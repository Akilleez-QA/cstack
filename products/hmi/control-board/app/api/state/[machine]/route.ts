// GET /api/state/<machine> : signed desired state, pulled by the machine's poller about every 60s.
// Public route, but contains no secrets; integrity comes from the per-machine HMAC.
// If there's no decision yet, it returns level 0 seq 0 (the poller never lowers on seq 0; see poller).
import { NextResponse } from "next/server";
import { MACHINES, sign } from "@/lib/sign";
import { getJSON, type DesiredState } from "@/lib/store";

export const dynamic = "force-dynamic";

export async function GET(_req: Request, ctx: { params: Promise<{ machine: string }> }) {
  const { machine } = await ctx.params;
  if (!MACHINES.includes(machine)) return NextResponse.json({ error: "unknown machine" }, { status: 404 });
  const now = Math.floor(Date.now() / 1000);
  const st = (await getJSON<DesiredState>(`shields:state:${machine}`)) ?? {
    machine, level: 0, seq: 0, decision_id: "none", authorized_by: "none", issued_at: 0, expires_at: 0, rollback_min: 60,
  };
  // served_at lets the poller reject replays of old responses (freshness window 5 min)
  const payload = { ...st, served_at: now } as unknown as Record<string, unknown>;
  // All-clear proof (DECISION-004 bundle) rides OUTSIDE the HMAC: it is self-authenticating, and the poller verifies it offline.
  const ledger = st.level === 0 && st.decision_id !== "none" ? await getJSON(`shields:proof:${st.decision_id}`) : null;
  const cosign = st.level === 0 && st.decision_id !== "none" ? await getJSON(`shields:cosign:${st.decision_id}`) : null;
  return NextResponse.json({ payload, sig: sign(machine, payload), ...(ledger ? { ledger } : {}), ...(cosign ? { cosign } : {}) }, { headers: { "Cache-Control": "no-store" } });
}
