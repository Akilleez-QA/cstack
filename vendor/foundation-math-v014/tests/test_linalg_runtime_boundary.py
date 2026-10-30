"""Static regression gates supplement tests; not a sandbox or formal proof."""
import ast
from pathlib import Path
import unittest


class RuntimeBoundary(unittest.TestCase):
    def test_only_allowlisted_standard_library_imports(self):
        permitted = {'__future__', 'dataclasses', 'fractions', 'json', 'math', 'typing', 'sys'}
        for path in (Path(__file__).parents[1] / 'exact_linalg').glob('*.py'):
            tree = ast.parse(path.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        self.assertIn(alias.name.split('.')[0], permitted, str(path))
                elif isinstance(node, ast.ImportFrom) and node.level == 0:
                    self.assertIn(node.module.split('.')[0], permitted, str(path))

    def test_no_assert_eval_exec_or_dynamic_import(self):
        forbidden = {'eval', 'exec', 'compile', '__import__', 'open', 'input', 'breakpoint'}
        for path in (Path(__file__).parents[1] / 'exact_linalg').glob('*.py'):
            for node in ast.walk(ast.parse(path.read_text())):
                self.assertNotIsInstance(node, ast.Assert, str(path))
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    self.assertNotIn(node.func.id, forbidden, str(path))
                if isinstance(node, ast.Constant):
                    self.assertNotIsInstance(node.value, float, str(path))

    def test_verifier_algorithm_has_no_producer_imports(self):
        path = Path(__file__).parents[1] / 'exact_linalg' / 'verifier.py'
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.ImportFrom):
                self.assertNotIn(node.module, {'producer', 'api'})
            if isinstance(node, ast.Import):
                for alias in node.names:
                    self.assertFalse(alias.name.endswith('.producer'))


if __name__ == '__main__':
    unittest.main()
