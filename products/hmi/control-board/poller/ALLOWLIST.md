# Firewall allowlist entry for the board (kept open at L0/L1/L2)
Implemented in `shields/lib/shields-local.sh` (sibling piece) `nft_rules()`:
- `meta skuid "shields-poller" tcp dport 443 accept` (rig): only the poller's uid may reach any 443. This is stable across poller restarts. A cgroup-id match is not, because nft resolves the cgroup at load time.
- `ip daddr { <board IPs> } tcp dport 443 accept` (rig + box): resolved from `SHIELDS_BOARD_HOST` at fire time (getent). With a Vercel custom domain this is typically 76.76.21.21 (A record). If the name doesn't resolve, the rule is omitted and the uid rule still covers the rig.
- DNS for the poller goes through systemd-resolved (already allowed: resolved cgroup, 53/853).
Inbound: none. The board never connects to the machines.
Box: no systemd, so run the poller as root via `setsid` with `SHIELDS_ENGINE=/workspace/ops/shields/lib/shields-local.sh`, `SHIELDS_MACHINE=box`, `SHIELDS_LEVEL_FILE=/workspace/ops/shields/local-state/box/level`, key file outside /workspace (`/root/.shields-hmac`, mode 600).
