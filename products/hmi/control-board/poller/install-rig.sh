#!/usr/bin/env bash
# Install the poller on host-a. NOT RUN: the owner said don't install the poller yet (2026-10-24). Review, then run on the rig with sudo.
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "run with sudo"; exit 1; }
id -u shields-poller >/dev/null 2>&1 || useradd --system --no-create-home --shell /usr/bin/nologin shields-poller
install -d -m 755 /usr/local/lib/shields
install -m 755 shields-poller.py /usr/local/lib/shields/shields-poller.py
install -m 644 ../../ledger/ledger.py /usr/local/lib/shields/ledger.py  # all-clear proof verifier (needs python3-cryptography)
[ -f /etc/shields-ledger-roster.json ] || echo "Note: no /etc/shields-ledger-roster.json (public keys only); all-clear proofs can't verify until it exists."
install -m 440 sudoers.shields-poller /etc/sudoers.d/shields-poller && visudo -cf /etc/sudoers.d/shields-poller
install -m 644 shields-poller.service /etc/systemd/system/shields-poller.service
install -d -m 700 /etc/credstore.encrypted
[ -f /etc/shields-poller.env ] && grep -q '^SHIELDS_BOARD_URL=https://' /etc/shields-poller.env || { echo "Create /etc/shields-poller.env with SHIELDS_BOARD_URL=https://<deployed board host> first (mode 644)."; exit 2; }
[ -f /etc/credstore.encrypted/shields-hmac ] || { echo "Create the key first (see unit file comment), then copy the SAME hex into Vercel env SHIELDS_HMAC_MAIN_RIG by hand."; exit 2; }
systemctl daemon-reload
sudo -u shields-poller true
echo "Dry check: sudo -u shields-poller SHIELDS_HMAC_FILE=... python3 /usr/local/lib/shields/shields-poller.py --once --dry-run"
echo "Enable when ready: systemctl enable --now shields-poller"
