"""Bootstrap owns one live core per underlying ledger store in this process."""
import gc
from pathlib import Path
import tempfile
import unittest
from dataclasses import replace
from unittest.mock import MagicMock, patch

import bootstrap
from adapters.memory_ledger import MemoryLedger
from bootstrap import build_core
from poodo_core import AuthorityGrant, ContractError, PoodoCore
from tests.test_approval_policy import Capability, Extension


def core_for(ledger):
    return PoodoCore(Extension(), {"synthetic_sensor": Capability()}, (AuthorityGrant(
        "test", "synthetic_sensor", "synthetic_sensor", ("reading",), ("g",), 4, lane="ToolFace"),), ledger)


class LedgerBindingTests(unittest.TestCase):
    def test_same_port_cannot_bind_two_live_cores(self):
        ledger = MemoryLedger()
        core = build_core(ledger, core_for)
        with self.assertRaises(ContractError):
            build_core(ledger, core_for)
        self.assertEqual(core.ledger(), [])

    def test_distinct_ports_over_same_canonical_path_are_refused_before_construction(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "node.log"
            alias = Path(directory) / "alias.log"
            alias.symlink_to(path)
            core = build_core(MemoryLedger(), core_for, store_path=path)
            for duplicate in (path, alias, Path(directory) / "child" / ".." / "node.log"):
                with self.subTest(path=duplicate), self.assertRaises(ContractError):
                    build_core(MemoryLedger(), lambda _: self.fail("duplicate factory ran"), store_path=duplicate)
            other = build_core(MemoryLedger(), core_for, store_path=Path(directory) / "other.log")
            self.assertIsNot(core, other)
            del core
            gc.collect()
            replacement = build_core(MemoryLedger(), core_for, store_path=alias)
            self.assertEqual(replacement.ledger(), [])

    def test_failed_or_recursive_construction_does_not_leave_a_binding(self):
        ledger = MemoryLedger()

        def recursive(bound):
            return build_core(bound, core_for)

        with self.assertRaises(ContractError):
            build_core(ledger, recursive)
        core = build_core(ledger, core_for)
        self.assertEqual(core.ledger(), [])

    def test_production_builders_use_registry_and_fresh_memory_ledgers(self):
        for domain_id, domain in bootstrap.DOMAINS.items():
            fake = replace(domain, capability=MagicMock(),
                           foundation=lambda cap, grants, ledger: core_for(ledger))
            with self.subTest(domain=domain_id), patch.dict(bootstrap.DOMAINS, {domain_id: fake}):
                core, _ = bootstrap.build_domain(domain_id, "g")
                other, _ = bootstrap.build_domain(domain_id, "g")
                self.assertIsNot(core._ledger, other._ledger)
                with self.assertRaises(ContractError):
                    build_core(core._ledger, core_for)

    def test_registry_is_the_one_source_and_unknown_domains_never_fall_back(self):
        self.assertEqual(list(bootstrap.DOMAINS)[:2], ["foundation_math", "foundation_template"])
        self.assertEqual("foundation_refrigeration" in bootstrap.DOMAINS,
                         bootstrap.DEFAULT_REFRIGERATION_ROOT.is_dir())
        for domain_id in ("foundation_engine", "foundation_refrigeration.rules", ""):
            with self.assertRaisesRegex(ContractError, "not registered"):
                bootstrap.build_domain(domain_id, "g")
        with self.assertRaisesRegex(ContractError, "already registered"):
            bootstrap.register(bootstrap.DOMAINS["foundation_template"])


if __name__ == "__main__":
    unittest.main()
