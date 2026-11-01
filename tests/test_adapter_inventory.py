import copy
import importlib
import json
from pathlib import Path
import unittest

from jsonschema import Draft202012Validator
from adapters import adapter_inventory
from adapters.adapter_inventory import (INVENTORY_PATH, LANE_PORTS, LANES, PORT_LANES, SCHEMA_PATH, load_inventory,
                                        parse_inventory)
from poodo_core import ContractError, models

ROOT = Path(__file__).resolve().parent.parent
# An optional Foundation's glue may be absent from a checkout (the open-core export leaves Refrigeration, Robotics and Film
# out). Only these rows may then name a missing path; every other row's path must exist.
OPTIONAL_DOMAIN_FILES = {"foundations/refrigeration": ("adapters/refrigeration_stdio.py",
                                                       "extensions/foundation_refrigeration.py"),
                         "foundations/robotics": ("adapters/robotics_stdio.py", "extensions/foundation_robotics.py"),
                         "foundations/film": ("adapters/film_stdio.py", "extensions/foundation_film.py")}


def scanned():
    """ADR 005 decision 3: adapters/*.py, tools/*.py, extensions/*.py and examples/interface/**/lib/*."""
    files = [p for pattern in ("adapters/*.py", "tools/*.py", "extensions/*.py") for p in ROOT.glob(pattern)]
    files += [p for p in ROOT.glob("examples/interface/**/lib/*") if p.is_file() and "node_modules" not in p.parts]
    return sorted(str(p.relative_to(ROOT)) for p in files if p.name != "__init__.py")


def document():
    return json.loads(INVENTORY_PATH.read_text())


class InventoryContractTests(unittest.TestCase):
    def test_schema_is_valid_draft_2020_12(self):
        Draft202012Validator.check_schema(json.loads(SCHEMA_PATH.read_text()))

    def test_inventory_loads(self):
        inventory = load_inventory()
        self.assertGreater(len(inventory.attachments), 0)
        self.assertEqual(set(LANE_PORTS), {"AdmissionPort", "ApprovalPort", "CapabilityPort", "CostPort", "LedgerPort", "MemoryPort"})

    def test_lanes_are_the_cores(self):
        schema = json.loads(SCHEMA_PATH.read_text())
        self.assertEqual(tuple(schema["$defs"]["lane"]["enum"]), models.LANES)
        self.assertIs(adapter_inventory.LANES, models.LANES)
        self.assertIs(adapter_inventory.READ_ONLY_LANES, models.READ_ONLY_LANES)

    def test_each_lane_port_has_its_adr_lane(self):
        self.assertEqual(set(PORT_LANES), set(LANE_PORTS))
        self.assertEqual(PORT_LANES["CostPort"], "SupervisorFace")
        doc = document()
        row = next(r for r in doc["attachments"] if r["port"] == "ApprovalPort")
        doc["attachments"].append({**row, "adapter_id": "host-cost", "port": "CostPort"})  # TruthFace: refused
        with self.assertRaisesRegex(ContractError, "CostPort belongs on SupervisorFace, not TruthFace"):
            parse_inventory(doc)
        doc["attachments"][-1]["lane"] = "SupervisorFace"
        self.assertEqual(parse_inventory(doc).attachment("host-cost", "SupervisorFace").port, "CostPort")

    def test_lane_must_be_one_of_the_eight(self):
        doc = document()
        doc["attachments"][0]["lane"] = "CockpitFace"
        with self.assertRaisesRegex(ContractError, "Invalid adapter inventory"):
            parse_inventory(doc)

    def test_duplicate_adapter_and_lane_is_refused(self):
        doc = document()
        doc["attachments"].append(copy.deepcopy(doc["attachments"][0]))
        with self.assertRaisesRegex(ContractError, "Duplicate adapter attachment"):
            parse_inventory(doc)

    def test_behind_port_needs_a_port(self):
        doc = document()
        row = next(r for r in doc["attachments"] if r["status"] == "behind_port")
        row["port"], row["port_reason"] = "none", "removed"
        with self.assertRaisesRegex(ContractError, "Invalid adapter inventory"):
            parse_inventory(doc)

    def test_port_must_be_a_lane_protocol_and_sit_in_one_lane(self):
        for port, message in (("DomainExtension", "Invalid"), ("EndoforgePort", "not a lane port"),
                              ("WidgetPort", "not a lane port")):
            doc = document()
            next(r for r in doc["attachments"] if r["status"] == "behind_port")["port"] = port
            with self.assertRaisesRegex(ContractError, message):
                parse_inventory(doc)
        doc = document()
        row = next(r for r in doc["attachments"] if r["port"] == "LedgerPort")
        doc["attachments"].append({**row, "adapter_id": "second-ledger", "lane": "ToolFace"})
        with self.assertRaisesRegex(ContractError, "two lanes"):
            parse_inventory(doc)

    def test_missing_reasons_and_mismatched_location_are_refused(self):
        for field, value in (("fake_reason", None), ("port_reason", None), ("command", "x")):
            doc = document()
            row = next(r for r in doc["attachments"] if r["fake"] is None and r["port"] == "none"
                       and r["kind"] != "external_command")
            if value is None:
                del row[field]
            else:
                row[field] = value
            with self.assertRaises(ContractError):
                parse_inventory(doc)



def lane_suites():
    """Item 2's LANE_SUITES (tests/replaceability/compose.py, #82), or None before that PR lands on this branch."""
    if not (ROOT / "tests" / "replaceability" / "compose.py").is_file():
        return None
    return importlib.import_module("tests.replaceability.compose").LANE_SUITES


def problems(inventory):
    """Repository checks: the inventory must describe this checkout."""
    files, found = scanned(), []
    absent = {path for root, paths in OPTIONAL_DOMAIN_FILES.items() if not (ROOT / root).is_dir() for path in paths}
    covered = {a.path for a in inventory.attachments} | {p for p, _ in inventory.not_an_adapter}
    found += [f"no row: {f}" for f in files if f not in covered]
    found += [f"excluded but not scanned: {p}" for p, _ in inventory.not_an_adapter if p not in files and p not in absent]
    for a in inventory.attachments:
        if a.path is not None and not (ROOT / a.path).exists() and a.path not in absent:
            found.append(f"missing path: {a.path}")
        suites = lane_suites()
        if a.fake is not None and suites is not None and a.fake not in suites.get(a.lane, {}).get("fakes", ()):
            found.append(f"missing fake: {a.fake}")
        if a.strategic_dependency_adr is not None and not (ROOT / "contracts" / a.strategic_dependency_adr).is_file():
            found.append(f"missing strategic dependency ADR: {a.strategic_dependency_adr}")
    return found


class InventoryRepositoryTests(unittest.TestCase):
    """A new adapter file without a row, or a row naming a missing path, fails here."""

    def setUp(self):
        self.inventory = load_inventory()

    def test_inventory_matches_the_checkout(self):
        self.assertEqual(problems(self.inventory), [])

    def mutated(self, change):
        doc = document()
        change(doc)
        return problems(parse_inventory(doc))

    def test_unlisted_file_fails(self):
        def drop(doc):
            doc["attachments"] = [r for r in doc["attachments"] if r.get("path") != "adapters/math_stdio.py"]
        self.assertEqual(self.mutated(drop), ["no row: adapters/math_stdio.py"])
        self.assertEqual(self.mutated(lambda d: d["not_an_adapter"].pop(0)), ["no row: adapters/adapter_inventory.py"])

    def test_missing_path_and_fake_fail(self):
        def move(doc):
            row = next(r for r in doc["attachments"] if r.get("path") == "adapters/memory")
            row["path"] = "adapters/gone"
        self.assertEqual(self.mutated(move), ["missing path: adapters/gone"])
        if lane_suites() is not None:
            def fake(doc):
                next(r for r in doc["attachments"] if r["fake"])["fake"] = "fake.no-such"
            self.assertEqual(self.mutated(fake), ["missing fake: fake.no-such"])

    def test_strategic_dependency_needs_a_decision_record(self):
        def accept(name):
            return lambda doc: doc["attachments"][0].update(strategic_dependency_adr=name)
        self.assertEqual(self.mutated(accept("DECISION-999-nothing.md")),
                         ["missing strategic dependency ADR: DECISION-999-nothing.md"])
        self.assertEqual(self.mutated(accept("DECISION-004-private-witnessed-ledger.md")), [])


    def test_no_strategic_dependency_is_accepted_today(self):
        self.assertEqual([a.adapter_id for a in self.inventory.attachments if a.strategic_dependency_adr], [])
        self.assertTrue(all(a.lane in LANES for a in self.inventory.attachments))


if __name__ == "__main__":
    unittest.main()
