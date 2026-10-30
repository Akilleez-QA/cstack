import copy
from pathlib import Path
import unittest

from adapters.aor_registry import GATED, load_fleet, parse_fleet
from poodo_core import LANES, READ_ONLY_LANES, ContractError

EFFECTS = {"read": "allow", "write_slice": "allow", "execute": "ask", "config": "ask",
           "send": "ask", "payment": "ask", "post": "ask", "filing": "ask", "delete": "ask"}
GUEST = {**EFFECTS, "write_slice": "deny", "execute": "deny", "config": "deny"}


def bot(slug, ident, slices=(), reports_to=None, **effects):
    return {"id": ident, "name": slug.title(), "slug": slug, "reports_to": reports_to, "owns": ["x"], "not": [],
            "slices": list(slices), "effects": {**EFFECTS, **effects}, "status": "CHECK"}


def fleet():
    return {"schema": "cstack.fleet/0.1", "source": {"generated_by": "test", "inputs": ["fixture"]},
            "approver": "owner-via-approver",
            "bots": [bot("coordinator", "00000001", ["/", ".github/"]),
                     bot("example-agent", "00000002", ["examples/interface/"]),
                     bot("reference-agent", "00000003", ["examples/reference/"], reports_to="coordinator")],
            "devices": [{"hostname": "agent-box-1", "owner": "example-agent", "guest_effects": dict(GUEST), "status": "CHECK"}]}


class FleetRegistryTests(unittest.TestCase):
    def test_valid_fleet_loads_and_resolves(self):
        f = parse_fleet(fleet())
        self.assertEqual(f.approver, "owner-via-approver")
        self.assertEqual(f.bot("example-agent").slices, ("examples/interface/",))
        self.assertEqual(f.device("agent-box-1").owner, "example-agent")
        self.assertEqual(f.bot("reference-agent").effects.of("send"), "ask")

    def test_gated_effects_can_never_be_allow(self):
        for name in GATED:
            doc = fleet()
            doc["bots"][1]["effects"][name] = "allow"
            with self.assertRaisesRegex(ContractError, "explicit yes"):
                parse_fleet(doc)
            doc = fleet()
            doc["devices"][0]["guest_effects"][name] = "allow"
            with self.assertRaisesRegex(ContractError, "explicit yes"):
                parse_fleet(doc)

    def test_approver_is_fixed_to_owner_via_scheduled(self):
        doc = fleet()
        doc["approver"] = "coordinator"
        with self.assertRaises(ContractError):
            parse_fleet(doc)

    def test_one_owner_per_path(self):
        doc = fleet()
        doc["bots"][2]["slices"] = ["examples/interface/sentinel/"]
        with self.assertRaisesRegex(ContractError, "one owner per path"):
            parse_fleet(doc)

    def test_references_and_duplicates_fail_closed(self):
        cases = [("bots", 2, "reports_to", "nobody"), ("bots", 2, "reports_to", "reference-agent"),
                 ("bots", 1, "slug", "coordinator"), ("bots", 1, "id", "00000001"),
                 ("devices", 0, "owner", "nobody")]
        for section, index, field, value in cases:
            doc = fleet()
            doc[section][index][field] = value
            with self.assertRaises(ContractError, msg=f"{section}.{field}={value}"):
                parse_fleet(doc)

    def test_unknown_fields_and_missing_effects_are_refused(self):
        doc = fleet()
        doc["bots"][0]["grants"] = ["everything"]
        with self.assertRaises(ContractError):
            parse_fleet(doc)
        doc = fleet()
        del doc["bots"][0]["effects"]["delete"]
        with self.assertRaises(ContractError):
            parse_fleet(doc)

    def test_slice_owner_must_be_able_to_write_it(self):
        doc = fleet()
        doc["bots"][1]["effects"]["write_slice"] = "deny"
        with self.assertRaisesRegex(ContractError, "cannot write"):
            parse_fleet(doc)

    def test_records_are_immutable(self):
        f = parse_fleet(copy.deepcopy(fleet()))
        with self.assertRaises(Exception):
            f.bot("example-agent").slug = "coordinator"



if __name__ == "__main__":
    unittest.main()
