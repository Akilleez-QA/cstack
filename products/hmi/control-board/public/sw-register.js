// External (not inline) so the CSP needs no 'unsafe-inline'. Loaded with the per-request nonce from app/layout.tsx.
if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js");
