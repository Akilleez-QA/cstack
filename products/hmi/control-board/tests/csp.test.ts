import { test } from "node:test";
import assert from "node:assert/strict";
import { buildCsp, clerkHost, fapiFromPublishableKey } from "../lib/csp";

const pk = (host: string, kind = "test") => `pk_${kind}_${Buffer.from(host + "$").toString("base64")}`;

test("no 'unsafe-inline' anywhere, nonce on script + style", () => {
  const c = buildCsp("Tk9OQ0U=", "example.clerk.accounts.dev");
  assert.ok(!c.includes("unsafe-inline"));
  assert.match(c, /script-src 'self' 'nonce-Tk9OQ0U=' 'strict-dynamic' https:\/\/example\.clerk\.accounts\.dev/);
  assert.match(c, /style-src 'self' 'nonce-Tk9OQ0U='/);
  assert.match(c, /frame-ancestors 'none'/);
  assert.match(c, /object-src 'none'/);
});
test("Clerk host comes from env, never a hard-coded domain", () => {
  assert.equal(fapiFromPublishableKey(pk("example.clerk.accounts.dev")), "example.clerk.accounts.dev");
  assert.equal(fapiFromPublishableKey(pk("clerk.example.com", "live")), "clerk.example.com");
  assert.equal(fapiFromPublishableKey("garbage"), "");
  assert.equal(fapiFromPublishableKey(undefined), "");
  assert.equal(clerkHost({ SHIELDS_CLERK_FAPI_HOST: "Clerk.Example.org" }), "clerk.example.org");
  assert.equal(clerkHost({ NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY: pk("a.clerk.accounts.dev") }), "a.clerk.accounts.dev");
  assert.equal(clerkHost({ SHIELDS_CLERK_FAPI_HOST: "bad host; script-src *" }), "");
  assert.doesNotMatch(buildCsp("n", ""), /(script|connect)-src [^;]*https:/);
});
