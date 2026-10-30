"use client";
// HMI faceplate over the shields ledger: what each machine SHOULD be at (desired), what it last SAID it is (check-in),
// and how stale that report is. Never shows "applied" unless a receipt says so.
import { useEffect, useState, useCallback } from "react";
import { useReverification } from "@clerk/nextjs";

type M = { machine: string; desired: any; checkin: any };
const LBL = ["L0 normal", "L1 external lockdown", "L2 full isolation"];
const u8 = (s: string) => Uint8Array.from(atob(s.replace(/-/g, "+").replace(/_/g, "/")), (c) => c.charCodeAt(0));
const b64u = (b: ArrayBuffer) => btoa(String.fromCharCode(...new Uint8Array(b))).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");

// Phone co-sign for all-clear (lib/cosign.ts): board-issued challenge, signed by this phone's passkey with user verification.
async function phoneCosign(machine: string, intent: string | null) {
  const r = await fetch("/api/cosign", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ machine, intent }) });
  if (r.status === 404) return undefined;  // no passkey configured yet
  const c = await r.json();
  const cred = (await navigator.credentials.get({ publicKey: { challenge: u8(c.challenge), rpId: c.rpId, userVerification: "required",
    allowCredentials: [{ type: "public-key", id: u8(c.credentialId) }], timeout: 60000 } })) as PublicKeyCredential;
  const a = cred.response as AuthenticatorAssertionResponse;
  return { intent: c.intent, scope: c.scope, nonce: c.nonce, exp: c.exp, credentialId: cred.id,
    authenticatorData: b64u(a.authenticatorData), clientDataJSON: b64u(a.clientDataJSON), signature: b64u(a.signature) };
}
// One-time: register this phone's passkey (ES256) and show the PUBLIC config to paste into COSIGN_PASSKEY_JSON and the rig roster.
async function registerPhone() {
  const cred = (await navigator.credentials.create({ publicKey: { challenge: crypto.getRandomValues(new Uint8Array(32)),
    rp: { id: location.hostname, name: "Shields" }, user: { id: crypto.getRandomValues(new Uint8Array(16)), name: "owner", displayName: "the owner" },
    pubKeyCredParams: [{ type: "public-key", alg: -7 }], authenticatorSelection: { userVerification: "required", residentKey: "preferred" } } })) as PublicKeyCredential;
  const spki = (cred.response as AuthenticatorAttestationResponse).getPublicKey();
  prompt("COSIGN_PASSKEY_JSON (public)", JSON.stringify({ credentialId: cred.id, spki: spki && btoa(String.fromCharCode(...new Uint8Array(spki))),
    rpId: location.hostname, origins: [location.origin] }));
}

export default function Board() {
  const [data, setData] = useState<{ machines: M[]; ledger: any[] } | null>(null);
  const [err, setErr] = useState("");
  const load = useCallback(async () => {
    const r = await fetch("/api/audit", { cache: "no-store" });
    r.ok ? setData(await r.json()) : setErr(`audit ${r.status}`);
  }, []);
  useEffect(() => { load(); const t = setInterval(load, 15000); return () => clearInterval(t); }, [load]);

  const post = useReverification(async (body: object) => {
    const r = await fetch("/api/level", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    return r.json();
  });
  const setLevel = async (machine: string, level: number) => {
    const reason = prompt(`Reason for ${LBL[level]} on ${machine}?`);
    if (reason === null) return;
    if (level === 2 && !confirm("L2 cuts tailnet peers. Restore is board, console or the auto-rollback timer only. Continue?")) return;
    let ledger, cosign;
    if (level === 0) {
      const pj = prompt("DECISION-004 proof (`ledger.py bundle` JSON), blank if none");
      if (pj === null) return;
      ledger = pj.trim() ? JSON.parse(pj) : undefined;
      cosign = await phoneCosign(machine, ledger?.intent?.hash ?? null);
    }
    await post({ machine, level, reason, rollback_min: 60, ledger, cosign });
    load();
  };
  const age = (ts?: number) => (ts ? `${Math.round(Date.now() / 1000 - ts)}s ago` : "never");

  return (
    <main>
      <h1>Shields</h1>
      {err && <p className="err">{err}</p>}
      {data?.machines.map((m) => {
        const reported = m.checkin?.level ?? null;
        const stale = !m.checkin?.ts || Date.now() / 1000 - m.checkin.ts > 180;
        return (
          <section key={m.machine} className="machine">
            <h2>{m.machine}</h2>
            <p>Desired: <b className={`l${m.desired?.level ?? 0}`}>{LBL[m.desired?.level ?? 0]}</b> (seq {m.desired?.seq ?? 0})</p>
            <p>Reported: <b className={reported === null ? "unknown" : `l${reported}`}>{reported === null ? "UNKNOWN" : LBL[reported]}</b>
              {" "}· outcome {m.checkin?.outcome ?? "unknown"} · last check-in {age(m.checkin?.ts)} {stale && <b className="stale">STALE</b>}</p>
            <div className="buttons">
              {[0, 1, 2].map((l) => (
                <button key={l} className={`b${l}`} onClick={() => setLevel(m.machine, l)}>
                  {l === 0 ? "All clear" : `L${l}`}
                </button>))}
            </div>
          </section>);
      })}
      <p><button onClick={registerPhone}>Register this phone for all-clear co-sign</button></p>
      <h2>Audit log</h2>
      <ol className="audit">
        {data?.ledger.map((r, i) => (
          <li key={i}>{r.ts} {r.type} {r.id} {r.machine ?? ""} L{r.level ?? "?"} {r.outcome ?? ""} {r.authorized_by ?? ""} {r.reason ?? ""}</li>))}
      </ol>
    </main>
  );
}
