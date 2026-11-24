"""Small regression suite using only synthetic values and identifiers."""

from pathlib import Path
import tempfile
import unittest

from score_bvtv import evaluate, read_scores


class ScoreTests(unittest.TestCase):
    def read_csv(self, content):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "synthetic.csv"
            path.write_text(content, encoding="utf-8")
            return read_scores(path)

    def test_identifier_join_and_units(self):
        result = evaluate({"a": 20, "b": 40}, {"b": 37, "a": 21})
        self.assertEqual(result, {
            "specimen_count": 2,
            "mae_percentage_points": 2.0,
            "bias_percentage_points": -1.0,
        })
        self.assertEqual(result, evaluate({"b": 40, "a": 20}, {"a": 21, "b": 37}))

    def test_boundary_values(self):
        self.assertEqual(self.read_csv("specimen_id,bvtv_percent\na,0\nb,100\n"), {"a": 0, "b": 100})

    def test_invalid_files(self):
        header = "specimen_id,bvtv_percent\n"
        cases = {
            "empty file": "",
            "empty data": header,
            "wrong header": "specimen_id,bvtv\na,20\n",
            "duplicate": header + "a,20\na,30\n",
            "whitespace duplicate": header + "a,20\n a ,30\n",
            "blank id": header + " ,20\n",
            "missing column": header + "a\n",
            "extra column": header + "a,20,30\n",
        }
        for value in ["", "word", "nan", "inf", "-inf", "-1", "101"]:
            cases[f"invalid value {value}"] = header + f"a,{value}\n"
        for name, content in cases.items():
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.read_csv(content)

    def test_mismatched_specimens(self):
        for predictions in [{}, {"a": 20, "b": 30}, {"b": 30}]:
            with self.subTest(predictions=predictions), self.assertRaisesRegex(ValueError, "specimen mismatch"):
                evaluate({"a": 20}, predictions)


if __name__ == "__main__":
    unittest.main()
