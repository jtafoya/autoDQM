import unittest

from src.kb_schema import (
    KB_KEYS,
    parse_kb_run,
    validate_kb_entries,
    validate_manual_entries,
)


def manual_entry(run=1640):
    return {
        "run": run,
        "category": "broken_PMT_base",
        "cause": "human cause",
        "action": "human action",
        "recovery": "human recovery",
    }


class KnowledgeBaseSchemaTests(unittest.TestCase):
    def test_run_parser_accepts_integer_and_exact_range(self):
        self.assertEqual(parse_kb_run(1640), (1640, 1640))
        self.assertEqual(parse_kb_run("1800-1805"), (1800, 1805))

    def test_run_parser_rejects_ambiguous_values(self):
        invalid_values = (
            True,
            -1,
            "1800 - 1805",
            "run1800",
            "1805-1800",
            [1800, 1805],
        )
        for value in invalid_values:
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_kb_run(value)

    def test_entries_require_exact_ordered_schema(self):
        entry = manual_entry()
        self.assertEqual(tuple(entry), KB_KEYS)
        self.assertEqual(validate_kb_entries([entry]), [entry])
        reordered = {key: entry[key] for key in reversed(KB_KEYS)}
        with self.assertRaises(ValueError):
            validate_kb_entries([reordered])

    def test_duplicate_run_is_rejected(self):
        with self.assertRaises(ValueError):
            validate_kb_entries([manual_entry(), manual_entry()])

    def test_manual_fields_must_be_nonblank(self):
        entry = manual_entry()
        entry["cause"] = ""
        with self.assertRaises(ValueError):
            validate_manual_entries([entry])


if __name__ == "__main__":
    unittest.main()
