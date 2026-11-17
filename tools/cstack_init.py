"""cstack init: set up this machine so every bot keeps a durable, signed ledger. Safe to run again.

    python -B tools/cstack_init.py            set up, or finish a setup that stopped part way
    python -B tools/cstack_init.py --check    report health; changes nothing
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from adapters.local_setup import default_state_root, init_command, setup
from bootstrap import DEFAULT_FLEET

LABELS = {"created": "created", "fixed": "fixed  ", "ok": "ok     ", "problem": "PROBLEM"}


def render(report, check):
    root = report.state_root
    out = [f"Cstack {'health check' if check else 'setup'}: {root}", ""]
    out += [f"  {LABELS[status]}  {text}" for status, text in report.lines]
    out.append("")
    if report.problems:
        out.append(f"Not ready: {len(report.problems)} problem(s) above. Fix them, then run "
                   f"`{init_command(root)}{' --check' if check else ''}` again.")
        return "\n".join(out)
    bots = ", ".join(report.bots)
    out.append(f"Ready. Bots: {bots}. Device: {report.device}. Every bot records to a durable, signed ledger "
               "that survives restarts.")
    if report.local_witnesses:
        out.append("The ledger's two witnesses are local keys on this machine, so nothing outside it vouches for "
                   "the record yet. See docs/guides/how-to/set-up.md#witnesses.")
    state = "" if root == default_state_root() else f" --state-root {root}"
    first = report.bots[0] if report.bots else "SLUG"
    out += ["", "Next:",
            f"  Start a bot's server:  python -B tools/cstack_mcp.py --aor {first}{state}",
            f"  Check health later:    {init_command(root)} --check"]
    return "\n".join(out)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="report health without changing anything")
    parser.add_argument("--state-root", type=Path, default=default_state_root(), help="where state and the ledger live")
    parser.add_argument("--fleet", type=Path, default=DEFAULT_FLEET, help="the bot list (aors/fleet.json)")
    parser.add_argument("--device", help="this machine's device name in the bot list; default: recorded, else "
                                         "Tailscale, else the computer's name")
    args = parser.parse_args(argv)
    report = setup(args.state_root, args.fleet, device=args.device, write=not args.check)
    print(render(report, args.check))
    return 1 if report.problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
