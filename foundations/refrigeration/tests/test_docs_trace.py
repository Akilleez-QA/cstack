import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


def tool(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DocumentationTraceTests(unittest.TestCase):
    def test_requirements_trace_to_tests_design_and_live_links(self):
        problems, summary = tool("check_trace").check()
        self.assertEqual(problems, [])
        self.assertEqual(summary["requirements"], summary["traced"])

    def test_generated_reference_documents_are_current(self):
        gen = tool("gen_docs")
        for path, text in ((gen.CATALOG, gen.catalog()), (gen.DATA, gen.reference_data())):
            with self.subTest(path=path.name):
                self.assertEqual(path.read_text(), text)


if __name__ == "__main__":
    unittest.main()
