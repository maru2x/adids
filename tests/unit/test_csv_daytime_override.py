import csv
import tempfile
import unittest
from pathlib import Path

from src.util.DataModified.csv_daytime_override import override_daytime


class CsvDaytimeOverrideTests(unittest.TestCase):
    def write_csv(self, path, rows, fieldnames=("daytime", "label", "conn_state")):
        with path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    def read_csv(self, path):
        with path.open("r", encoding="utf-8", newline="") as f:
            return list(csv.DictReader(f))

    def test_override_daytime_shifts_all_rows_and_keeps_input_untouched(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            input_dir = root / "input"
            output_dir = root / "output"
            input_dir.mkdir()

            self.write_csv(
                input_dir / "b.csv",
                [
                    {"daytime": "2022-01-02 00:00:05", "label": "1", "conn_state": "S0"},
                    {"daytime": "2022-01-02 00:00:10", "label": "1", "conn_state": "S0"},
                ],
            )
            self.write_csv(
                input_dir / "a.csv",
                [
                    {"daytime": "2022-01-01 23:59:55", "label": "0", "conn_state": "SF"},
                    {"daytime": "2022-01-02 00:00:00", "label": "0", "conn_state": "SF"},
                ],
            )

            override_daytime(
                input_dir=str(input_dir),
                output_dir=str(output_dir),
                baseline="2022-02-01 09:03:59",
            )

            output_files = sorted(path.name for path in output_dir.glob("*.csv"))
            self.assertEqual(
                output_files,
                [
                    "00000_20220201090359.csv",
                    "00001_20220201090409.csv",
                ],
            )

            first_rows = self.read_csv(output_dir / output_files[0])
            second_rows = self.read_csv(output_dir / output_files[1])
            self.assertEqual(first_rows[0]["daytime"], "2022-02-01 09:03:59")
            self.assertEqual(first_rows[1]["daytime"], "2022-02-01 09:04:04")
            self.assertEqual(second_rows[0]["daytime"], "2022-02-01 09:04:09")
            self.assertEqual(second_rows[1]["daytime"], "2022-02-01 09:04:14")

            original_rows = self.read_csv(input_dir / "a.csv")
            self.assertEqual(original_rows[0]["daytime"], "2022-01-01 23:59:55")

    def test_override_daytime_fails_without_daytime_column(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            input_dir = root / "input"
            output_dir = root / "output"
            input_dir.mkdir()

            self.write_csv(
                input_dir / "broken.csv",
                [{"timestamp": "2022-01-01 00:00:00", "label": "0", "conn_state": "SF"}],
                fieldnames=("timestamp", "label", "conn_state"),
            )

            with self.assertRaisesRegex(ValueError, "Missing 'daytime' column"):
                override_daytime(
                    input_dir=str(input_dir),
                    output_dir=str(output_dir),
                    baseline="2022-02-01 09:03:59",
                )


if __name__ == "__main__":
    unittest.main()
