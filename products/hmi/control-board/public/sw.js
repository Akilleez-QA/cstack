// Network-only for /api (state must never come from cache); cache the shell for offline open.
const SHELL = "shields-shell-v1";
self.addEventListener("install", (e) => e.waitUntil(caches.open(SHELL).then((c) => c.addAll(["/manifest.webmanifest", "/icon.svg"]))));
self.addEventListener("fetch", (e) => {
  const u = new URL(e.request.url);
  if (u.pathname.startsWith("/api/")) return; // default network fetch, no caching
  e.respondWith(fetch(e.request).catch(() => caches.match(e.request)));
});
