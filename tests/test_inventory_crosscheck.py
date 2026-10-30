"""ADR 005 items 1 and 3 joined: bootstrap checks every grant against the adapter inventory before building a core."""
import json
import unittest

import bootstrap
from adapters.adapter_inventory import INVENTORY_PATH, load_inventory, parse_inventory
from extensions.foundation_math import TOOL_NAMES
from poodo_core import AuthorityGrant, ContractError


def grant(capability_id="foundation_math", lane="ToolFace"):
    return AuthorityGrant("test-grant", capability_id, capability_id, TOOL_NAMES[:1], ("g",), 1, lane=lane)


class InventoryCrossCheckTests(unittest.TestCase):
    def test_every_bootstrap_composition_passes(self):
        self.assertEqual(set(bootstrap.CAPABILITY_ADAPTERS), set(bootstrap.DOMAINS))
        self.assertLessEqual({"foundation_math", "foundation_template"}, set(bootstrap.DOMAINS))
        inventory = load_inventory()
        for domain in bootstrap.DOMAINS.values():
            row = inventory.attachment(bootstrap.CAPABILITY_ADAPTERS[domain.domain_id], "ToolFace")
            self.assertEqual((row.port, row.status, row.path), ("CapabilityPort", "behind_port",
                             f"adapters/{domain.capability.__module__.split('.')[-1]}.py"))
        self.assertEqual(len(bootstrap.COMPOSITIONS), len(bootstrap.DOMAINS))
        for build in bootstrap.COMPOSITIONS:
            core, _ = build("g")
            self.assertEqual(bootstrap.check_grants(core._grants), core._grants)

    def test_wrong_lane_refuses_to_start(self):
        for lane in ("TruthFace", "SupervisorFace", "RuntimeFace"):
            with self.assertRaisesRegex(ContractError, f"is on {lane}; foundation-math-stdio is on ToolFace"):
                bootstrap.check_grants((grant(lane=lane),))

    def test_adapter_missing_from_inventory_refuses_to_start(self):
        doc = json.loads(INVENTORY_PATH.read_text())
        doc["attachments"] = [r for r in doc["attachments"] if r["adapter_id"] != "foundation-math-stdio"]
        doc["not_an_adapter"].append({"path": "adapters/math_stdio.py", "role": "shared_helper", "reason": "test"})
        inventory = parse_inventory(doc)
        with self.assertRaisesRegex(ContractError, "Unknown adapter"):
            bootstrap.build_math("g", inventory=inventory)
        bootstrap.build_template("g", inventory=inventory)  # only the missing adapter's composition refuses

    def test_unmapped_capability_refuses_to_start(self):
        with self.assertRaisesRegex(ContractError, "No inventory adapter is mapped for capability unmapped_tool"):
            bootstrap.check_grants((grant(), grant("unmapped_tool")))


if __name__ == "__main__":
    unittest.main()
