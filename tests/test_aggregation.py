import unittest

from tests._bootstrap import GoldPriceOracle, make_contract


class TestDomainExtraction(unittest.TestCase):
    def setUp(self):
        self.c = make_contract()

    def test_basic(self):
        self.assertEqual(
            self.c._extract_domain("https://www.kitco.com/gold-price-today"),
            "kitco.com",
        )

    def test_subdomains_collapse_to_same_domain(self):
        variants = [
            "https://www.kitco.com/a",
            "https://charts.kitco.com/a",
        ]
        domains = {self.c._extract_domain(u) for u in variants}
        self.assertEqual(domains, {"kitco.com"})

    def test_invalid_scheme_returns_empty(self):
        self.assertEqual(self.c._extract_domain("ftp://kitco.com"), "")

    def test_different_publishers_stay_distinct(self):
        a = self.c._extract_domain("https://kitco.com/a")
        b = self.c._extract_domain("https://bloomberg.com/a")
        self.assertNotEqual(a, b)

    def test_multi_part_suffix_lbma(self):
        self.assertEqual(
            self.c._extract_domain("https://www.lbma.org.uk/prices"),
            "lbma.org.uk",
        )

    def test_query_string_and_fragment_ignored(self):
        self.assertEqual(
            self.c._extract_domain("https://kitco.com/path?x=1#frag"),
            "kitco.com",
        )

    def test_overlong_url_is_invalid(self):
        long_url = "https://kitco.com/" + "a" * 3000
        self.assertEqual(self.c._extract_domain(long_url), "")

    def test_no_allowlist_entry_is_unreachable(self):
        """Regression guard: every REPUTABLE_PRICE_DOMAINS entry must
        actually round-trip through _extract_domain, or it can never
        be credited as reputable (the exact class of silent bug
        OilPriceOracle's businessinsider.com incident caused)."""
        for domain in GoldPriceOracle.REPUTABLE_PRICE_DOMAINS:
            extracted = self.c._extract_domain(f"https://{domain}/some/path")
            self.assertEqual(
                extracted, domain,
                f"Allowlist entry {domain!r} does not round-trip - it "
                f"could never actually be credited as reputable.",
            )


class TestExtractPath(unittest.TestCase):
    """_extract_path backs the domain+endpoint form of
    required_source_domains, ported from OilPriceOracle v3 for
    feature parity."""

    def setUp(self):
        self.c = make_contract()

    def test_basic_path(self):
        self.assertEqual(
            self.c._extract_path("https://kitco.com/gold/spot"), "/gold/spot"
        )

    def test_root_path_is_empty(self):
        self.assertEqual(self.c._extract_path("https://kitco.com"), "")
        self.assertEqual(self.c._extract_path("https://kitco.com/"), "")

    def test_trailing_slash_stripped(self):
        self.assertEqual(
            self.c._extract_path("https://kitco.com/gold/spot/"), "/gold/spot"
        )

    def test_query_and_fragment_stripped(self):
        self.assertEqual(
            self.c._extract_path("https://kitco.com/gold/spot?x=1#frag"),
            "/gold/spot",
        )

    def test_invalid_scheme_returns_empty(self):
        self.assertEqual(self.c._extract_path("ftp://kitco.com/gold/spot"), "")


class TestParseEndpointRequirement(unittest.TestCase):
    def setUp(self):
        self.c = make_contract()

    def test_bare_domain_has_no_path(self):
        self.assertEqual(
            self.c._parse_endpoint_requirement("kitco.com"), ("kitco.com", "")
        )

    def test_domain_slash_path_form(self):
        self.assertEqual(
            self.c._parse_endpoint_requirement("kitco.com/gold/spot"),
            ("kitco.com", "/gold/spot"),
        )

    def test_full_url_form(self):
        self.assertEqual(
            self.c._parse_endpoint_requirement("https://kitco.com/gold/spot"),
            ("kitco.com", "/gold/spot"),
        )

    def test_trailing_slash_and_case_normalized(self):
        self.assertEqual(
            self.c._parse_endpoint_requirement("Kitco.com/Gold/Spot/"),
            ("kitco.com", "/gold/spot"),
        )

    def test_empty_entry_returns_empty_tuple(self):
        self.assertEqual(self.c._parse_endpoint_requirement(""), ("", ""))
        self.assertEqual(self.c._parse_endpoint_requirement(None), ("", ""))


class TestContentClassification(unittest.TestCase):
    def setUp(self):
        self.c = make_contract()

    def test_none_is_empty(self):
        self.assertEqual(self.c._classify_content(None), ("empty", False))

    def test_blank_is_empty(self):
        self.assertEqual(self.c._classify_content("   "), ("empty", False))

    def test_too_short_is_malformed(self):
        self.assertEqual(self.c._classify_content("gold up"), ("malformed", False))

    def test_normal_content_is_ok(self):
        content = "Gold is currently trading at $2,000.00 per troy ounce, live data feed. " * 2
        status, usable = self.c._classify_content(content)
        self.assertEqual(status, "ok")
        self.assertTrue(usable)

    def test_low_printable_ratio_is_malformed(self):
        content = "\x01\x02\x03\x04\x05\x06\x07\x08" * 10
        status, usable = self.c._classify_content(content)
        self.assertEqual(status, "malformed")
        self.assertFalse(usable)


class TestParseFixedWord(unittest.TestCase):
    def setUp(self):
        self.c = make_contract()

    def test_labeled_line_matches(self):
        raw = "KARAT: 22K"
        self.assertEqual(
            self.c._parse_fixed_word(raw, GoldPriceOracle.KARAT_WORDS, "Unspecified", label="KARAT"),
            "22K",
        )

    def test_unlabeled_bare_line_matches(self):
        raw = "22K"
        self.assertEqual(
            self.c._parse_fixed_word(raw, GoldPriceOracle.KARAT_WORDS, "Unspecified", label="KARAT"),
            "22K",
        )

    def test_no_match_returns_default(self):
        raw = "not a real karat"
        self.assertEqual(
            self.c._parse_fixed_word(raw, GoldPriceOracle.KARAT_WORDS, "Unspecified", label="KARAT"),
            "Unspecified",
        )

    def test_word_mid_sentence_is_not_a_false_positive(self):
        raw = "I think 22K might be mentioned here somewhere"
        self.assertEqual(
            self.c._parse_fixed_word(raw, GoldPriceOracle.KARAT_WORDS, "Unspecified", label="KARAT"),
            "Unspecified",
        )

    def test_empty_raw_returns_default(self):
        self.assertEqual(
            self.c._parse_fixed_word("", GoldPriceOracle.KARAT_WORDS, "Unspecified", label="KARAT"),
            "Unspecified",
        )

    def test_case_and_punctuation_insensitive(self):
        raw = "unit: gram."
        self.assertEqual(
            self.c._parse_fixed_word(raw, GoldPriceOracle.UNIT_WORDS, "Unspecified", label="UNIT"),
            "Gram",
        )


class TestExtractLabeledValue(unittest.TestCase):
    def setUp(self):
        self.c = make_contract()

    def test_extracts_value_after_colon(self):
        raw = "CURRENCY: USD\nKARAT: 24K\nPRICE: 2000.50"
        self.assertEqual(self.c._extract_labeled_value(raw, "PRICE"), "2000.50")

    def test_missing_label_returns_empty(self):
        raw = "CURRENCY: USD"
        self.assertEqual(self.c._extract_labeled_value(raw, "PRICE"), "")

    def test_extra_prose_around_labeled_lines_still_parses(self):
        raw = "Here is my analysis:\nCURRENCY: USD\nSome commentary.\nPRICE: 1999.99\nThanks!"
        self.assertEqual(self.c._extract_labeled_value(raw, "PRICE"), "1999.99")


class TestParsePrice(unittest.TestCase):
    def setUp(self):
        self.c = make_contract()

    def test_bare_integer(self):
        self.assertEqual(self.c._parse_price("2000"), 2000.0)

    def test_decimal(self):
        self.assertEqual(self.c._parse_price("2000.50"), 2000.50)

    def test_dollar_prefixed(self):
        self.assertEqual(self.c._parse_price("$2000.50"), 2000.50)

    def test_comma_grouped(self):
        self.assertEqual(self.c._parse_price("2,000.50"), 2000.50)

    def test_negative(self):
        self.assertEqual(self.c._parse_price("-5.00"), -5.00)

    def test_trailing_text_ignored(self):
        self.assertEqual(self.c._parse_price("2000 USD per troy ounce"), 2000.0)

    def test_empty_is_none(self):
        self.assertIsNone(self.c._parse_price(""))

    def test_none_is_none(self):
        self.assertIsNone(self.c._parse_price(None))

    def test_no_leading_number_is_none(self):
        self.assertIsNone(self.c._parse_price("banana"))

    def test_number_not_at_start_is_none(self):
        self.assertIsNone(self.c._parse_price("USD 2000 per ounce"))

    def test_ambiguous_second_number_is_none(self):
        self.assertIsNone(self.c._parse_price("$2000 or $2100"))

    def test_malformed_thousands_grouping_is_none(self):
        self.assertIsNone(self.c._parse_price("1,23.45"))

    def test_leading_dot_is_none(self):
        self.assertIsNone(self.c._parse_price(".73"))

    def test_unclear_literal_is_none(self):
        self.assertIsNone(self.c._parse_price("Unclear"))


class TestKaratUnitInputNormalization(unittest.TestCase):
    def setUp(self):
        self.c = make_contract()

    def test_karat_aliases(self):
        self.assertEqual(self.c._normalize_karat_input("24k"), "24K")
        self.assertEqual(self.c._normalize_karat_input(" 22K "), "22K")
        self.assertEqual(self.c._normalize_karat_input("18k"), "18K")

    def test_unrecognized_karat_returns_empty(self):
        self.assertEqual(self.c._normalize_karat_input("999 fine"), "")
        self.assertEqual(self.c._normalize_karat_input(""), "")

    def test_unit_aliases(self):
        self.assertEqual(self.c._normalize_unit_input("troy_ounce"), "TroyOunce")
        self.assertEqual(self.c._normalize_unit_input("oz"), "TroyOunce")
        self.assertEqual(self.c._normalize_unit_input("g"), "Gram")
        self.assertEqual(self.c._normalize_unit_input("KG"), "Kilogram")
        self.assertEqual(self.c._normalize_unit_input("Tola"), "Tola")

    def test_unrecognized_unit_returns_empty(self):
        self.assertEqual(self.c._normalize_unit_input("pound"), "")


class TestNormalizeTo24kPerGram(unittest.TestCase):
    """The core deterministic conversion this contract's design
    centers on. See _normalize_to_24k_per_gram's docstring."""

    def setUp(self):
        self.c = make_contract()

    def test_24k_gram_is_identity(self):
        self.assertAlmostEqual(
            self.c._normalize_to_24k_per_gram(70.0, "24K", "Gram"), 70.0
        )

    def test_troy_ounce_conversion(self):
        # $2000/troy_ounce, 24K -> 2000 / 31.1034768 grams
        result = self.c._normalize_to_24k_per_gram(2000.0, "24K", "TroyOunce")
        self.assertAlmostEqual(result, 2000.0 / 31.1034768, places=6)

    def test_karat_conversion(self):
        # 22K is 22/24 pure - a source quoting a LOWER price for the
        # same physical purity-adjusted gold should normalize UP
        # toward the 24K-equivalent basis.
        price_24k_basis = self.c._normalize_to_24k_per_gram(70.0, "24K", "Gram")
        price_22k_basis = self.c._normalize_to_24k_per_gram(70.0 * (22.0 / 24.0), "22K", "Gram")
        self.assertAlmostEqual(price_24k_basis, price_22k_basis, places=6)

    def test_combined_karat_and_unit_conversion_example(self):
        # From the docstring's worked example: $2,000/troy_oz, 22K
        # -> ~70.14 USD/gram at 24K basis.
        result = self.c._normalize_to_24k_per_gram(2000.0, "22K", "TroyOunce")
        self.assertAlmostEqual(result, 70.14708342246105, places=5)

    def test_kilogram_and_tola_are_internally_consistent(self):
        # 1 kilogram of 24K gold priced at $70,000 should normalize to
        # the same per-gram-24K basis as $70/gram, 24K.
        per_kg = self.c._normalize_to_24k_per_gram(70000.0, "24K", "Kilogram")
        per_gram = self.c._normalize_to_24k_per_gram(70.0, "24K", "Gram")
        self.assertAlmostEqual(per_kg, per_gram, places=6)

    def test_none_price_returns_none(self):
        self.assertIsNone(self.c._normalize_to_24k_per_gram(None, "24K", "Gram"))

    def test_unspecified_karat_returns_none(self):
        self.assertIsNone(self.c._normalize_to_24k_per_gram(70.0, "Unspecified", "Gram"))

    def test_unspecified_unit_returns_none(self):
        self.assertIsNone(self.c._normalize_to_24k_per_gram(70.0, "24K", "Unspecified"))

    def test_every_karat_word_is_convertible(self):
        # Regression guard: every non-"Unspecified" KARAT_WORDS entry
        # must actually be present in KARAT_PURITY_FRACTION, or a
        # source correctly classified with that karat could never be
        # normalized (silently excluded as price_unparseable forever).
        for word in GoldPriceOracle.KARAT_WORDS:
            if word == "Unspecified":
                continue
            self.assertIn(word, GoldPriceOracle.KARAT_PURITY_FRACTION)

    def test_every_unit_word_is_convertible(self):
        for word in GoldPriceOracle.UNIT_WORDS:
            if word == "Unspecified":
                continue
            self.assertIn(word, GoldPriceOracle.UNIT_TO_GRAMS)


class TestAggregate(unittest.TestCase):
    def setUp(self):
        self.c = make_contract()

    def _record(self, comparison="Above", fetch_status="ok", duplicate=False,
                reputable=True, quality_flag="ok"):
        return {
            "fetch_status": fetch_status,
            "is_duplicate_domain": duplicate,
            "is_reputable": reputable,
            "quality_flag": quality_flag,
            "comparison": comparison,
        }

    def test_too_few_eligible_is_indeterminate(self):
        records = [self._record(comparison="Above")]
        self.assertEqual(self.c._aggregate(records), "Indeterminate")

    def test_two_agreeing_above_is_above(self):
        records = [self._record(comparison="Above"), self._record(comparison="Above")]
        self.assertEqual(self.c._aggregate(records), "Above")

    def test_two_agreeing_below_is_below(self):
        records = [self._record(comparison="Below"), self._record(comparison="Below")]
        self.assertEqual(self.c._aggregate(records), "Below")

    def test_two_agreeing_equal_is_equal(self):
        records = [self._record(comparison="Equal"), self._record(comparison="Equal")]
        self.assertEqual(self.c._aggregate(records), "Equal")

    def test_tied_split_is_indeterminate(self):
        records = [self._record(comparison="Above"), self._record(comparison="Below")]
        self.assertEqual(self.c._aggregate(records), "Indeterminate")

    def test_majority_with_dissent_still_resolves(self):
        records = [
            self._record(comparison="Above"),
            self._record(comparison="Above"),
            self._record(comparison="Below"),
        ]
        self.assertEqual(self.c._aggregate(records), "Above")

    def test_non_ok_fetch_status_excluded(self):
        records = [
            self._record(comparison="Above", fetch_status="timeout"),
            self._record(comparison="Above"),
        ]
        self.assertEqual(self.c._aggregate(records), "Indeterminate")

    def test_duplicate_domain_does_not_double_count(self):
        records = [
            self._record(comparison="Above"),
            self._record(comparison="Above", duplicate=True),
        ]
        self.assertEqual(self.c._aggregate(records), "Indeterminate")

    def test_non_reputable_excluded(self):
        records = [
            self._record(comparison="Above"),
            self._record(comparison="Above", reputable=False),
        ]
        self.assertEqual(self.c._aggregate(records), "Indeterminate")

    def test_bad_quality_flag_excluded(self):
        records = [
            self._record(comparison="Above"),
            self._record(comparison="Above", quality_flag="karat_unrecognized"),
        ]
        self.assertEqual(self.c._aggregate(records), "Indeterminate")


if __name__ == "__main__":
    unittest.main()
