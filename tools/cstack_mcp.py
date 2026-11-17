"""Launch the MCP stdio driving adapter for ONE bot's AOR on this device (ADR 003).

A host starts one of these per bot, from its own MCP configuration:
    python -B tools/cstack_mcp.py --aor example --device example-host
The AOR is fixed here, at launch; nothing a bot sends can change it. --fleet-mail adds the mail_* tools
(adapters/fleet_mail.py), sent as this AOR; without it the server is unchanged. The device is --device, else the name
`cstack init` recorded, else this machine's tailnet name. State lives in ~/.local/state/cstack/ unless --state-root is
given, and the server refuses to start there without the durable ledger `cstack init` sets up, unless
--allow-memory-ledger is given for a throwaway development session.
"""
import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from adapters.mcp_stdio_server import McpServer  # noqa: E402
from adapters.fleet_mail import DEFAULT_BUDGET, FleetMailConfig  # noqa: E402
from adapters.local_setup import SetupError, default_state_root, require_durable, resolve_device  # noqa: E402
from bootstrap import DEFAULT_FLEET, build_aor_session  # noqa: E402


MCP_MARKER = "CSTACK_MCP_SERVER"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--aor", required=True, help="bot slug from aors/fleet.json")
    parser.add_argument("--state-root", type=Path, default=default_state_root())
    parser.add_argument("--device", help="override the recorded or tailnet device name")
    parser.add_argument("--allow-memory-ledger", action="store_true",
                        help="development only: start without a durable ledger; the record is lost when it stops")
    parser.add_argument("--fleet", type=Path, default=DEFAULT_FLEET, help="host-owned AOR registry")
    parser.add_argument("--fleet-mail", action="store_true", help="enable the mail_* tools (off by default)")
    parser.add_argument("--fleet-mail-repo", default=FleetMailConfig.repo, help="private repo holding fleet mail")
    parser.add_argument("--fleet-mail-extra", action="append", metavar="SLUG",
                        help="non-fleet recipient; repeatable (default: worker)")
    parser.add_argument("--fleet-mail-budget", type=int, default=DEFAULT_BUDGET, help="sends+replies per hour")
    args = parser.parse_args(argv)
    mail = FleetMailConfig(repo=args.fleet_mail_repo, budget_per_hour=args.fleet_mail_budget,
                           extras=tuple(args.fleet_mail_extra or FleetMailConfig.extras)) if args.fleet_mail else None
    # Marks this process (and its children) as a bot's MCP server: host-only tools such as
    # tools/scheduled_approvals.py refuse to run under it.
    os.environ[MCP_MARKER] = "1"
    try:
        if not args.allow_memory_ledger:
            require_durable(args.state_root)
        hostname = args.device or resolve_device(args.state_root)
    except SetupError as error:
        sys.stderr.write(f"cstack: {error}\n")
        raise SystemExit(2) from None
    session = build_aor_session(args.aor, state_root=args.state_root, hostname=hostname,
                                fleet_path=args.fleet, fleet_mail=mail)
    try:
        McpServer(session, name=f"cstack-{args.aor}").serve()
    finally:
        session.close()


if __name__ == "__main__":
    main()
