import { createHmac, timingSafeEqual } from "node:crypto";

export const MACHINES = (process.env.SHIELDS_MACHINES ?? "host-a,box").split(",").map((s) => s.trim());

function keyFor(machine: string): Buffer {
  const name = "SHIELDS_HMAC_" + machine.toUpperCase().replace(/[^A-Z0-9]/g, "_");
  const hex = process.env[name];
  if (!hex || hex.length < 64) throw new Error(`missing ${name}`); // fail closed: no key, no signed state
  return Buffer.from(hex, "hex");
}

/** Canonical form: sorted keys, no whitespace. Poller re-serialises identically (python json.dumps sort_keys, separators). */
export function canonical(obj: Record<string, unknown>): string {
  return JSON.stringify(Object.keys(obj).sort().reduce((a, k) => ((a[k] = obj[k]), a), {} as Record<string, unknown>));
}

export function sign(machine: string, payload: Record<string, unknown>): string {
  return createHmac("sha256", keyFor(machine)).update(canonical(payload)).digest("hex");
}

export function verify(machine: string, payload: Record<string, unknown>, sig: string): boolean {
  try {
    const want = Buffer.from(sign(machine, payload), "hex");
    const got = Buffer.from(sig, "hex");
    return want.length === got.length && timingSafeEqual(want, got);
  } catch {
    return false;
  }
}
