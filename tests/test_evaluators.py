import unittest
from muse_mem.benchmarks import personamem_exact_match

class EvaluatorTests(unittest.TestCase):
    def test_option_label_exact_match(self):
        self.assertEqual(personamem_exact_match("The answer is (B).", "b"), 1)
        self.assertEqual(personamem_exact_match("A", "c"), 0)
        self.assertEqual(personamem_exact_match("unknown", "a"), 0)

if __name__ == "__main__":
    unittest.main()
