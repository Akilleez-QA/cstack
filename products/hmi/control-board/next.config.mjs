/** @type {import('next').NextConfig} */
// Content-Security-Policy is set per request in middleware.ts (nonce-based, no 'unsafe-inline'); see lib/csp.ts.
const securityHeaders = [
  { key: "Strict-Transport-Security", value: "max-age=63072000; includeSubDomains; preload" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "no-referrer" },
];
export default { async headers() { return [{ source: "/(.*)", headers: securityHeaders }]; } };
