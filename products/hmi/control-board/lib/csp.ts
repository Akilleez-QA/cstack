// Per-request nonce CSP (no 'unsafe-inline'). Built in middleware.ts; Next.js reads the nonce from the request's
// Content-Security-Policy header and stamps it on its own scripts; ClerkProvider (dynamic) passes it to clerk-js.
// 'strict-dynamic' lets the nonce'd clerk-js load its own chunks. No hostnames are hard-coded: the Clerk Frontend API
// host comes from SHIELDS_CLERK_FAPI_HOST or is decoded from the publishable key.

/** pk_(test|live)_<base64("<fapi-host>$")> -> fapi host, or "" if it can't be decoded. */
export function fapiFromPublishableKey(pk: string | undefined): string {
  const m = /^pk_(?:test|live)_([A-Za-z0-9+/=_-]+)$/.exec(pk ?? "");
  if (!m) return "";
  try {
    const host = atob(m[1].replace(/-/g, "+").replace(/_/g, "/")).replace(/\$$/, "");
    return /^[a-z0-9.-]+\.[a-z]{2,}$/i.test(host) ? host.toLowerCase() : "";
  } catch {
    return "";
  }
}

export function clerkHost(env: Record<string, string | undefined>): string {
  const h = (env.SHIELDS_CLERK_FAPI_HOST ?? "").trim().toLowerCase();
  return /^[a-z0-9.-]+\.[a-z]{2,}$/.test(h) ? h : fapiFromPublishableKey(env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY);
}

export function buildCsp(nonce: string, fapiHost: string): string {
  const clerk = fapiHost ? ` https://${fapiHost}` : "";
  return [
    "default-src 'self'",
    `script-src 'self' 'nonce-${nonce}' 'strict-dynamic'${clerk}`,
    `style-src 'self' 'nonce-${nonce}'`,
    `connect-src 'self'${clerk}`,
    "img-src 'self' data: https://img.clerk.com",
    "worker-src 'self' blob:",
    "object-src 'none'",
    "base-uri 'none'",
    "form-action 'self'",
    "frame-ancestors 'none'",
  ].join("; ");
}
