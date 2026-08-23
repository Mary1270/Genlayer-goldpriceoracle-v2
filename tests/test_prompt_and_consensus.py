import unittest

from tests._bootstrap import GoldPriceOracle, make_contract


class TestBuildPrompt(unittest.TestCase):
    def setUp(self):
        self.c = make_contract()
        self.prompt = self.c._build_prompt("24K", "TroyOunce", "2000", "some gold price content")

    def test_contains_injection_guardrail(self):
        self.assertIn("untrusted data", self.prompt)
        self.assertIn("ignore previous instructions", self.prompt.lower())

    def test_asks_for_five_labeled_fields(self):
        for label in ("CURRENCY:", "KARAT:", "UNIT:", "FRESHNESS:", "PRICE:"):
            self.assertIn(label, self.prompt)

    def test_does_not_ask_model_to_compare(self):
        # Central design decision: no COMPARISON field is requested,
        # since comparing requires karat/unit conversion arithmetic
        # this contract deliberately keeps out of the LLM's hands.
        self.assertNotIn("COMPARISON:", self.prompt)

    def test_tells_model_not_to_convert(self):
        self.assertIn("do not convert", self.prompt.lower())

    def test_extra_prose_around_labeled_lines_still_parses(self):
        raw = "Sure thing!\nCURRENCY: USD\nKARAT: 22K\nUNIT: Gram\nFRESHNESS: Current\nPRICE: 70.50\nHope that helps."
        self.assertEqual(self.c._extract_labeled_value(raw, "PRICE"), "70.50")

    def test_karat_vocabulary_present(self):
        for word in ("24K", "22K", "21K", "18K", "14K", "10K"):
            self.assertIn(word, self.prompt)

    def test_unit_vocabulary_present(self):
        for word in ("TroyOunce", "Gram", "Kilogram", "Tola"):
            self.assertIn(word, self.prompt)


class TestEquivalencePrinciple(unittest.TestCase):
    def setUp(self):
        self.c = make_contract()
        self.principle = GoldPriceOracle.EQUIVALENCE_PRINCIPLE

    def test_references_actual_schema_fields(self):
        for field in (
            "final_verdict", "winner", "independent_source_count",
            "fetch_status", "quality_flag", "comparison",
        ):
            self.assertIn(field, self.principle)

    def test_explicitly_excludes_price_karat_unit_from_equivalence(self):
        self.assertIn("price", self.principle)
        self.assertIn("karat", self.principle)
        self.assertIn("unit", self.principle)
        self.assertIn("audit metadata only", self.principle)

    def test_not_strict_eq(self):
        # This contract must use prompt_comparative, never strict_eq,
        # for the LLM-derived pipeline - see class docstring.
        import inspect
        source = inspect.getsource(GoldPriceOracle.resolve_agreement)
        self.assertIn("prompt_comparative", source)
        self.assertNotIn("strict_eq", source)


if __name__ == "__main__":
    unittest.main()
