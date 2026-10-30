"""Unit tests for the rule-based checks and context loading (no API access needed)."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.context import build_system_prompt, load_context
from modules.evaluation import validate_insight

GOOD = """📍 Sales ahead of forecast, driven by higher traffic.

📊 Key observations:
▲ CR +1pt vs LY on stronger promotion
▼ AOV -3% vs LY as mix shifted lower
▲ Traffic +6% vs PW

⚠️ Watch: stock cover on top SKUs
🎯 Action: rebalance stock to South region"""


class ValidateInsightTests(unittest.TestCase):
    def test_well_formed_insight_passes(self):
        self.assertEqual(validate_insight(GOOD), [])

    def test_no_data_slide_is_always_valid(self):
        self.assertEqual(validate_insight("No business data on this slide."), [])

    def test_missing_sections_are_flagged(self):
        flags = validate_insight("📍 Short story with LY comparison.")
        self.assertIn("missing section: Watch:", flags)
        self.assertIn("missing section: Action:", flags)

    def test_long_bullet_is_flagged(self):
        long_bullet = "▲ " + " ".join(["word"] * 13) + " LY"
        flags = validate_insight(GOOD + "\n" + long_bullet)
        self.assertTrue(any(f.startswith("bullet too long") for f in flags))

    def test_hedge_word_is_flagged(self):
        flags = validate_insight(GOOD.replace("Sales ahead", "Sales probably ahead"))
        self.assertIn("hallucination signal: 'probably'", flags)

    def test_missing_abbreviation_is_flagged(self):
        text = "📍 Sales up.\n▲ Good week\nWatch: none\nAction: none"
        self.assertTrue(any("no known abbreviations" in f for f in validate_insight(text)))


class ContextTests(unittest.TestCase):
    def test_context_files_load_in_filename_order(self):
        with tempfile.TemporaryDirectory() as d:
            for name, body in (("02_b.md", "second"), ("01_a.md", "first"), ("ignore.txt", "x")):
                with open(os.path.join(d, name), "w", encoding="utf-8") as f:
                    f.write(body)
            self.assertEqual(load_context(d), "first\nsecond")

    def test_missing_context_dir_is_empty(self):
        self.assertEqual(load_context("does-not-exist"), "")

    def test_system_prompt_embeds_context(self):
        self.assertIn("my reference text", build_system_prompt("my reference text"))


if __name__ == "__main__":
    unittest.main()
