import { NextResponse } from "next/server";
import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";
import { buildCsp, clerkHost } from "@/lib/csp";
// Machine endpoints are NOT behind Clerk: they're authenticated by per-machine HMAC instead.
const isMachineRoute = createRouteMatcher(["/api/state/(.*)", "/api/checkin", "/manifest.webmanifest", "/sw.js", "/sw-register.js", "/icon.svg"]);
export default clerkMiddleware(async (auth, req) => {
  if (!isMachineRoute(req)) await auth.protect();
  const nonce = btoa(String.fromCharCode(...crypto.getRandomValues(new Uint8Array(16)))); // edge-safe (no Buffer)
  const csp = buildCsp(nonce, clerkHost(process.env));
  const headers = new Headers(req.headers);
  headers.set("x-nonce", nonce);
  headers.set("Content-Security-Policy", csp); // Next.js picks the nonce up from here for its inline bootstrap scripts
  const res = NextResponse.next({ request: { headers } });
  res.headers.set("Content-Security-Policy", csp);
  return res;
});
export const config = { matcher: ["/((?!_next|.*\\.(?:css|js|svg|png|ico|webmanifest)$).*)", "/(api)(.*)"] };
