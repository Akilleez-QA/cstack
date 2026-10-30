// GET /api/audit : ledger tail + per-machine desired state + last check-in (Clerk-protected by middleware).
import { NextResponse } from "next/server";
import { auth } from "@clerk/nextjs/server";
import { MACHINES } from "@/lib/sign";
import { getJSON, readLedger } from "@/lib/store";

export const dynamic = "force-dynamic";

export async function GET() {
  const { userId } = await auth();
  if (!userId || userId !== process.env.SHIELDS_ALLOWED_USER_ID) return NextResponse.json({ error: "forbidden" }, { status: 403 });
  const machines = await Promise.all(MACHINES.map(async (m) => ({
    machine: m,
    desired: await getJSON(`shields:state:${m}`),
    checkin: await getJSON<Record<string, unknown>>(`shields:checkin:${m}`),
  })));
  return NextResponse.json({ machines, ledger: (await readLedger(200)).reverse() }, { headers: { "Cache-Control": "no-store" } });
}
