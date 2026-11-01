"""Independent determinant/minor oracles, never producer elimination logic."""
from fractions import Fraction
from itertools import combinations, permutations, product
import random
import unittest
from exact_linalg.contract import Limits, MathError, encode_coefficient
from exact_linalg.producer import produce
from exact_linalg.verifier import verify


def matrix(rows, cols, entries, domain='Z'):
    return {'domain': domain, 'rows': rows, 'cols': cols, 'entries': entries}


def coefficient(value):
    return Fraction(value) if type(value) is int else Fraction(value['num'], value['den'])


def leibniz(entries):
    """Independent signed-permutation determinant, including empty determinant."""
    n = len(entries)
    total = Fraction(0)
    for perm in permutations(range(n)):
        inversions = sum(perm[i] > perm[j] for i in range(n) for j in range(i + 1, n))
        term = Fraction((-1) ** inversions)
        for i in range(n):
            term *= coefficient(entries[i][perm[i]])
        total += term
    return total


def minor_rank(spec):
    m, n, entries = spec['rows'], spec['cols'], spec['entries']
    for k in range(min(m, n), 0, -1):
        for rows in combinations(range(m), k):
            for cols in combinations(range(n), k):
                if leibniz([[entries[i][j] for j in cols] for i in rows]):
                    return k
    return 0


def oracle_check(test, spec):
    certificate = produce(spec)
    checked = verify(spec, certificate)
    test.assertEqual(certificate['rank'], minor_rank(spec))
    test.assertEqual(checked.rank, certificate['rank'])
    n, m = spec['cols'], spec['rows']
    test.assertEqual(certificate['nullspace']['cols'], n - certificate['rank'])
    if m == n:
        test.assertEqual(coefficient(certificate['determinant']), leibniz(spec['entries']))
    else:
        test.assertIsNone(certificate['determinant'])
    # A second direct nullspace evaluation independent of shared arithmetic helpers.
    N = certificate['nullspace']['entries']
    for row in spec['entries']:
        for j in range(n - certificate['rank']):
            test.assertEqual(sum((coefficient(row[k]) * coefficient(N[k][j]) for k in range(n)), Fraction(0)), 0)


class IndependentOracles(unittest.TestCase):
    def test_exhaustive_tiny_integer_matrices(self):
        for m, n in ((0, 0), (0, 3), (3, 0), (1, 1), (1, 3), (3, 1), (2, 2), (2, 3), (3, 2)):
            for entries in product((-1, 0, 1), repeat=m * n):
                rows = [list(entries[i * n:(i + 1) * n]) for i in range(m)]
                oracle_check(self, matrix(m, n, rows))

    def test_deterministic_rational_matrices(self):
        rng = random.Random(81973)
        for _ in range(160):
            m, n = rng.randrange(5), rng.randrange(5)
            entries = [[encode_coefficient(Fraction(rng.randrange(-5, 6), rng.randrange(1, 8))) for _ in range(n)] for _ in range(m)]
            oracle_check(self, matrix(m, n, entries, 'Q'))

    def test_rank_deficient_rational_fixture(self):
        a = matrix(3, 4, [[{'num': 1, 'den': 2}, 1, 0, -1],
                           [1, 2, 0, -2], [0, 0, 3, 6]], 'Q')
        oracle_check(self, a)
        cert = produce(a)
        self.assertEqual(cert['pivots'], [0, 2])
        self.assertEqual(cert['free_columns'], [1, 3])
        self.assertEqual(cert['nullspace']['entries'], [[-2, 2], [1, 0], [0, -2], [0, 1]])

    def test_determinant_swap_sign_and_fraction(self):
        a = matrix(2, 2, [[0, {'num': 2, 'den': 3}], [3, 1]], 'Q')
        cert = produce(a)
        self.assertEqual(cert['determinant'], -2)
        self.assertTrue(any(op['op'] == 'swap' for op in cert['operations']))
        oracle_check(self, a)

    def test_empty_shapes_and_full_nullity(self):
        for m, n in ((0, 0), (0, 4), (4, 0), (4, 4)):
            a = matrix(m, n, [[0] * n for _ in range(m)])
            cert = produce(a)
            self.assertEqual(cert['rank'], 0)
            self.assertEqual(cert['nullspace']['rows'], n)
            self.assertEqual(cert['nullspace']['cols'], n)
            self.assertEqual(cert['nullspace']['entries'], [[int(i == j) for j in range(n)] for i in range(n)])
            verify(a, cert)

    def test_deterministic_no_input_mutation(self):
        a = matrix(2, 3, [[2, 3, 4], [5, 6, 7]])
        import copy
        before = copy.deepcopy(a)
        self.assertEqual(produce(a), produce(a))
        self.assertEqual(a, before)

    def test_z_is_q_linear_algebra_not_integer_kernel_basis(self):
        cert = produce(matrix(1, 2, [[2, 1]]))
        self.assertEqual(cert['nullspace']['entries'], [[{'num': -1, 'den': 2}], [1]])
        self.assertEqual(cert['nullspace']['domain'], 'Q')
        self.assertEqual(verify(matrix(1, 2, [[2, 1]]), cert).to_dict()['computational_field'], 'Q')

    def test_exact_large_integer_regression(self):
        a = matrix(2, 2, [[2**80 + 1, 2**80], [2**80, 2**80 - 1]])
        cert = produce(a)
        self.assertEqual(cert['determinant'], -1)
        verify(a, cert)


if __name__ == '__main__':
    unittest.main()
