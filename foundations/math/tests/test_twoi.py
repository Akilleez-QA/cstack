"""Finite exact regression checks, conditional on the pinned physical catalog."""
from dataclasses import FrozenInstanceError
from fractions import Fraction
import unittest
from unittest.mock import patch
from fm_research import p1, twoi as t, vendor
from character_ring.contract import CATALOG_SHA256
from character_ring.verifier import check_catalog, symmetric, inner as class_inner


class TwoITest(unittest.TestCase):
    def test_catalog_and_orthogonality(self):
        self.assertEqual(vendor.catalog_sha256(), CATALOG_SHA256)
        self.assertEqual(len(check_catalog()), len(t.LABELS))
        with patch.object(vendor, 'CATALOG_SHA256', 'wrong'):
            with self.assertRaises(RuntimeError):
                vendor.catalog_sha256()
        self.assertEqual(sum(d * d for d in t.DIMS.values()), 120)
        for a in t.LABELS:
            for b in t.LABELS:
                self.assertEqual(t.inner(t.irrep(a), t.irrep(b)), int(a == b))

    def test_symmetric_powers(self):
        self.assertEqual(t.sym_W(10).decompose(), {'A': 1, 'V': 1, 'D': 1})
        self.assertEqual(t.sym_W(14).decompose(), {'A': 1, 'V': 1, 'P': 1, 'D': 1})
        self.assertEqual(t.irrep("W'") @ t.sym_W(2), t.irrep('T6'))
        for name in ('W', 'Wp'):
            for n in range(31):
                rep = t.irrep(name).sym(n)
                values = tuple(symmetric(n, x) for x in t.character_values(t.irrep(name)))
                self.assertEqual(t.character_values(rep), values)
                self.assertEqual(rep.dim, n + 1)
                self.assertTrue(rep.is_genuine)
                for i, row in enumerate(check_catalog()):
                    self.assertEqual(class_inner(values, row), (rep.multiplicities[i], 0))
        with self.assertRaises(NotImplementedError):
            t.irrep('A').sym(2)

    def test_invariants_and_molien(self):
        for d in range(32):
            expected = int(d in (0, 12, 20, 24, 30))
            rep = t.sym_W(d)
            self.assertEqual(t.invariant_count(rep), expected, d)
            self.assertEqual(t.inner(rep, t.irrep('1')), expected)
        self.assertEqual(t.invariant_degrees(30), [(d, 1) for d in (0, 12, 20, 24, 30)])
        self.assertTrue(t.molien_check(60))
        self.assertEqual(t.invariant_count(t.sym_W(60)), 2)

    def test_labels_and_virtual_arithmetic(self):
        self.assertEqual(t.irrep("W'"), t.irrep('Wprime'))
        with self.assertRaisesRegex(KeyError, 'valid labels: 1, W, A'):
            t.irrep('unknown')
        self.assertTrue(t.distinguish('P', 'S4'))
        self.assertNotEqual(t.CENTER_SIGN['P'], t.CENTER_SIGN['S4'])
        self.assertEqual(t.sym_W(3).decompose(), {'S4': 1})
        rep = 2 * t.irrep('W') - t.irrep('P')
        self.assertEqual(str(rep), '2*W-P')
        self.assertEqual(str(t.Rep()), '0')
        self.assertEqual(rep.dim, 0)
        self.assertFalse(rep.is_genuine)
        self.assertEqual(rep + t.irrep('P'), t.irrep('W') * 2)
        values = [0] * 9
        frozen = t.Rep(values)
        values[0] = 1
        self.assertEqual(frozen, t.Rep())
        with self.assertRaises(FrozenInstanceError):
            frozen.multiplicities = tuple(values)
        for pair in t.character_values(rep):
            self.assertTrue(all(isinstance(x, Fraction) for x in pair))

    def test_exact_input_boundaries(self):
        calls = [lambda: t.Rep((1.0,) + (0,) * 8), lambda: t.irrep(1.0),
                 lambda: t.sym_W(2.0), lambda: t.irrep('W') * 2.0,
                 lambda: t.invariant_degrees(2.0), lambda: t.molien_check(2.0),
                 lambda: p1.Block('1', 1.0), lambda: p1.Block('1', 0, 1.0),
                 lambda: t.invariant_count(1.0), lambda: t.character_values(1.0),
                 lambda: p1.cohomology([], [1.0]), lambda: t.sym_W(True)]
        for call in calls:
            with self.assertRaises(TypeError):
                call()
        for n in (-1, 257):
            with self.assertRaises(ValueError):
                t.sym_W(n)
        with self.assertRaises(ValueError):
            p1.Block('1', 0, -1)

    def test_p1_cohomology(self):
        zero = p1.cohomology([p1.Block('1', -1)], [0])[0]
        self.assertEqual((zero['h0'], zero['h1']), (t.Rep(), t.Rep()))
        rows = p1.cohomology([p1.Block('1', 0)], range(-15, 16))
        for n, row in rows.items():
            h0 = t.sym_W(n) if n >= 0 else t.Rep()
            h1 = t.sym_W(-n - 2) if n <= -2 else t.Rep()
            self.assertEqual((row['h0'], row['h1']), (h0, h1))
            self.assertEqual(row['h0_dim'], max(n + 1, 0))
        blocks = [p1.Block("W'", -3, 2), p1.Block('A', 2), p1.Block('1', -1)]
        for twist, row in p1.cohomology(blocks, range(-6, 7)).items():
            self.assertEqual((row['rank'], row['degree']), (8, -7))
            self.assertEqual(row['h0_dim'] - row['h1_dim'], row['rank'] * (twist + 1) + row['degree'])
        self.assertEqual(p1.cohomology([], [0])[0]['h0'], t.Rep())

    def test_hom(self):
        source = [p1.Block('W', -3)]
        self.assertEqual(p1.hom(source, source), t.irrep('1') + t.irrep('A'))
        self.assertEqual(p1.hom([p1.Block('1', 1)], [p1.Block('1', 0)]), t.Rep())
        self.assertEqual(p1.hom([p1.Block("W'", 0, 2)], [p1.Block('1', 2)]), 2 * t.irrep('T6'))
