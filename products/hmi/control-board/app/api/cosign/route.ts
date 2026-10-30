// POST /api/cosign {machine|"all", intent?}: issue a single-use challenge for the owner's phone co-sign of an all-clear.
// Same gate as /api/level (Clerk session + single allowed user). The phone signs it with its passkey (navigator.credentials.get)
// and the assertion goes to /api/level in body.cosign. 404 when no passkey is configured (co-sign not set up yet).
import { NextResponse } from "next/server";
import { randomBytes } from "crypto";
import { auth } from "@clerk/nextjs/server";
import { MACHINES } from "@/lib/sign";
import { issueCosignNonce } from "@/lib/store";
import { challengeFor, loadCosigner, MAX_TTL_SEC } from "@/lib/cosign";

export async function POST(req: Request) {
  const { userId } = await auth();
  if (!userId || userId !== process.env.SHIELDS_ALLOWED_USER_ID) return NextResponse.json({ error: "forbidden" }, { status: 403 });
  let c;
  try { c = loadCosigner(process.env.COSIGN_PASSKEY_JSON); } catch { return NextResponse.json({ error: "cosign not configured" }, { status: 404 }); }
  const body = (await req.json()) as { machine: string; intent?: string | null };
  const scope = (body.machine === "all" ? [...MACHINES] : [body.machine]).sort();
  if (!scope.every((m) => MACHINES.includes(m))) return NextResponse.json({ error: "unknown machine" }, { status: 400 });
  const intent = typeof body.intent === "string" && /^[0-9a-f]{64}$/.test(body.intent) ? body.intent : null;
  const nonce = randomBytes(16).toString("hex"), exp = Math.floor(Date.now() / 1000) + MAX_TTL_SEC / 2;
  await issueCosignNonce(nonce, MAX_TTL_SEC);
  return NextResponse.json({ intent, scope, nonce, exp, challenge: challengeFor({ intent, scope, nonce, exp }).toString("base64url"),
    credentialId: c.credentialId, rpId: c.rpId });
}
