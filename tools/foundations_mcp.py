import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from adapters.foundations_mcp import FoundationsMcpServer  # noqa: E402
from bootstrap import DEFAULT_FLEET, build_aor_session, foundation_inventories  # noqa: E402
from tools.cstack_mcp import MCP_MARKER, tailnet_hostname  # noqa: E402


def domain_id(name):
    return name if name.startswith("foundation_") else f"foundation_{name}"


def main(argv=None):
    parser = argparse.ArgumentParser(description="Serve the host's pinned Foundations as read-only MCP tools for "
                                                 "one bot's AOR on this device.")
    parser.add_argument("--aor", required=True, help="bot slug from the fleet registry")
    parser.add_argument("--foundation", action="append", required=True, metavar="NAME",
                        help="registered Foundation to expose, such as refrigeration; repeatable")
    parser.add_argument("--state-root", type=Path, default=Path.home() / ".local/state/cstack")
    parser.add_argument("--device", help="override the tailnet device name (tests only)")
    parser.add_argument("--fleet", type=Path, default=DEFAULT_FLEET, help="host-owned AOR registry")
    args = parser.parse_args(argv)
    foundations = [domain_id(name) for name in args.foundation]
    os.environ[MCP_MARKER] = "1"
    inventories = foundation_inventories(foundations)
    session = build_aor_session(args.aor, state_root=args.state_root, hostname=args.device or tailnet_hostname(),
                                fleet_path=args.fleet, foundations=foundations)
    try:
        FoundationsMcpServer(session, inventories, name=f"cstack-foundations-{args.aor}").serve()
    finally:
        session.close()


if __name__ == "__main__":
    main()
