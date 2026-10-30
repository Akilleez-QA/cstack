"""Field identities, exact ranks, independent witnesses and hostile inputs."""
from dataclasses import replace
from fractions import Fraction as F
from itertools import product
import unittest
from fm_research.field import QuadraticElement as E, Q5, GOLDEN as g
from fm_research.rank import (rank_exact, rank_mod_p, rank_over_Q_and_mod_p,
                              verify_rank_certificate)


class FieldTests(unittest.TestCase):
    def test_axioms(self):
        samples = [Q5(0), Q5(1), g, Q5(F(-2, 3), F(1, 4))]
        for x, y, z in product(samples, repeat=3):
            self.assertEqual((x+y)+z, x+(y+z))
            self.assertEqual((x*y)*z, x*(y*z))
            self.assertEqual(x*(y+z), x*y+x*z)
            self.assertEqual(x+y, y+x)
            self.assertEqual(x*y, y*x)
            self.assertEqual((x*y).norm(), x.norm()*y.norm())
        for x in samples:
            self.assertEqual(x-x, 0)
            self.assertEqual(x.conjugate().conjugate(), x)
            self.assertEqual(x*x.conjugate(), x.norm())
            if not x.is_zero():
                self.assertEqual(x*x.inverse(), 1)
                self.assertEqual(1/x, x**-1)
        self.assertEqual(g**2, g+1)
        self.assertEqual(2-g, -(g-2))
        self.assertEqual(hash(Q5(2)), hash(F(2)))
        self.assertEqual(len({g, Q5(F(1, 2), F(1, 2))}), 1)
        self.assertEqual(repr(g), '1/2+1/2*sqrt5')
        self.assertEqual(E(1, 1, -1)**2, E(0, 2, -1))

    def test_rejections(self):
        for action in [lambda: Q5(0.5), lambda: Q5(1, 0.5),
                       lambda: g+0.5, lambda: 0.5*g, lambda: g/0.5,
                       lambda: g == 0.5, lambda: E(1, 0, 5.0)]:
            with self.assertRaises(TypeError):
                action()
        for d in (0, 1, 4, 12, -4):
            with self.assertRaises(ValueError):
                E(1, 1, d)
        with self.assertRaises(ValueError):
            g + E(1, 1, 2)
        with self.assertRaises(ZeroDivisionError):
            Q5(0).inverse()


class RankTests(unittest.TestCase):
    def test_ranks_and_certificates(self):
        cases = [([[1, 0], [0, 1]], 2), ([[0, 0], [0, 0]], 0),
                 ([[1, 2, 3], [2, 4, 6], [0, 1, 1]], 2),
                 ([], 0), ([[], []], 0), ([[0, 1], [1, 0]], 2)]
        for a, expected in cases:
            for field, p in [('Q', None), ('F_p', 5), ('Q(sqrt5)', None)]:
                cert = rank_exact(a, field, p)
                self.assertEqual(cert.rank, expected)
                self.assertTrue(verify_rank_certificate(a, cert))
                self.assertEqual(cert.to_dict()['rank'], expected)
        a = [[1, 1], [1, -1]]
        self.assertEqual(rank_exact(a).rank, 2)
        self.assertEqual(rank_mod_p(a, 2), 1)
        self.assertEqual(rank_over_Q_and_mod_p(a, [2, 3]), {2: 1, 3: 2})
        for a, field in [([[1, g], [g, g+1]], 'Q(sqrt5)'),
                         ([[F(1, 2), 1], [1, 2]], 'Q'),
                         ([[E(1, 1, -1)]], 'Q(sqrt -1)')]:
            cert = rank_exact(a, field)
            self.assertEqual(cert.rank, 1)
            self.assertTrue(verify_rank_certificate(a, cert))

    def test_exhaustive_small_matrices(self):
        for entries in product((-1, 0, 1), repeat=4):
            a, b, c, d = entries
            matrix = [[a, b], [c, d]]
            for field, p in [('Q', None), ('F_p', 2), ('F_p', 3),
                             ('Q(sqrt5)', None)]:
                det = a*d-b*c
                nonzero = any(x % p if p else x for x in entries)
                expected = 2 if (det % p if p else det) else int(nonzero)
                cert = rank_exact(matrix, field, p)
                self.assertEqual(cert.rank, expected)
                self.assertTrue(verify_rank_certificate(matrix, cert))

    def test_tampering(self):
        a = [[0, 1], [0, 2]]
        cert = rank_exact(a)
        for changes in [dict(rank=0, pivot_rows=(), pivot_cols=()),
                        dict(rank=2), dict(pivot_rows=(2,)), dict(pivot_cols=(0,)),
                        dict(matrix_sha256='bad'), dict(rows=3)]:
            self.assertFalse(verify_rank_certificate(a, replace(cert, **changes)))
        self.assertFalse(verify_rank_certificate([[0, 1], [0, 3]], cert))

    def test_invalid_inputs(self):
        for a in ([[1], []], [[], [1]]):
            with self.assertRaises(ValueError):
                rank_exact(a)
        for p in (0, 1, 4, 15, 10**12+1):
            with self.assertRaises(ValueError):
                rank_mod_p([[1]], p)
        for field, p in [('Q', None), ('Q(sqrt5)', None), ('F_p', 2)]:
            with self.assertRaises(TypeError):
                rank_exact([[0.5]], field, p)
        with self.assertRaises(TypeError):
            rank_mod_p([[F(1, 2)]], 3)
