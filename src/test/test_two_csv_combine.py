import csv
import tempfile
import unittest
from pathlib import Path

from src.util.DataModified.two_csv_combine import combine_csv_directories


class TwoCsvCombineTests(unittest.TestCase):
    def write_csv(self, path, rows, fieldnames=("daytime", "label", "conn_state")):
        with path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    def read_rows(self, path):
        with path.open("r", encoding="utf-8", newline="") as f:
            return list(csv.DictReader(f))

    def flatten_output(self, output_dir):
        rows = []
        for csv_path in sorted(output_dir.glob("*.csv")):
            rows.extend(self.read_rows(csv_path))
        return rows

    def test_combine_keeps_buffer_when_one_side_ends(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            input_a = root / "a"
            input_b = root / "b"
            output_dir = root / "out"
            input_a.mkdir()
            input_b.mkdir()

            self.write_csv(
                input_a / "000.csv",
                [
                    {"daytime": "2022-01-01 00:00:00", "label": "0", "conn_state": "SF"},
                    {"daytime": "2022-01-01 00:00:02", "label": "0", "conn_state": "SF"},
                ],
            )
            self.write_csv(
                input_b / "000.csv",
                [
                    {"daytime": "2022-01-01 00:00:01", "label": "1", "conn_state": "S0"},
                    {"daytime": "2022-01-01 00:00:03", "label": "1", "conn_state": "S0"},
                    {"daytime": "2022-01-01 00:00:04", "label": "1", "conn_state": "S0"},
                ],
            )

            combine_csv_directories(str(input_a), str(input_b), str(output_dir), chunk_size=10)

            rows = self.flatten_output(output_dir)
            self.assertEqual(
                [row["daytime"] for row in rows],
                [
                    "2022-01-01 00:00:00",
                    "2022-01-01 00:00:01",
                    "2022-01-01 00:00:02",
                    "2022-01-01 00:00:03",
                    "2022-01-01 00:00:04",
                ],
            )

    def test_combine_splits_exactly_at_chunk_size(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            input_a = root / "a"
            input_b = root / "b"
            output_dir = root / "out"
            input_a.mkdir()
            input_b.mkdir()

            self.write_csv(
                input_a / "000.csv",
                [
                    {"daytime": "2022-01-01 00:00:00", "label": "0", "conn_state": "SF"},
                    {"daytime": "2022-01-01 00:00:02", "label": "0", "conn_state": "SF"},
                ],
            )
            self.write_csv(
                input_b / "000.csv",
                [
                    {"daytime": "2022-01-01 00:00:01", "label": "1", "conn_state": "S0"},
                    {"daytime": "2022-01-01 00:00:03", "label": "1", "conn_state": "S0"},
                ],
            )

            combine_csv_directories(str(input_a), str(input_b), str(output_dir), chunk_size=2)

            output_files = sorted(output_dir.glob("*.csv"))
            self.assertEqual(len(output_files), 2)
            self.assertEqual(len(self.read_rows(output_files[0])), 2)
            self.assertEqual(len(self.read_rows(output_files[1])), 2)

    def test_combine_rejects_header_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            input_a = root / "a"
            input_b = root / "b"
            output_dir = root / "out"
            input_a.mkdir()
            input_b.mkdir()

            self.write_csv(
                input_a / "000.csv",
                [{"daytime": "2022-01-01 00:00:00", "label": "0", "conn_state": "SF"}],
            )
            self.write_csv(
                input_b / "000.csv",
                [{"daytime": "2022-01-01 00:00:01", "label": "1", "label2": "x"}],
                fieldnames=("daytime", "label", "label2"),
            )

            with self.assertRaisesRegex(ValueError, "CSV header mismatch"):
                combine_csv_directories(str(input_a), str(input_b), str(output_dir), chunk_size=10)

    def test_combine_handles_multiple_files_per_side(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            input_a = root / "a"
            input_b = root / "b"
            output_dir = root / "out"
            input_a.mkdir()
            input_b.mkdir()

            self.write_csv(
                input_a / "000.csv",
                [{"daytime": "2022-01-01 00:00:00", "label": "0", "conn_state": "SF"}],
            )
            self.write_csv(
                input_a / "001.csv",
                [{"daytime": "2022-01-01 00:00:03", "label": "0", "conn_state": "SF"}],
            )
            self.write_csv(
                input_b / "000.csv",
                [{"daytime": "2022-01-01 00:00:01", "label": "1", "conn_state": "S0"}],
            )
            self.write_csv(
                input_b / "001.csv",
                [{"daytime": "2022-01-01 00:00:02", "label": "1", "conn_state": "S0"}],
            )

            combine_csv_directories(str(input_a), str(input_b), str(output_dir), chunk_size=10)

            rows = self.flatten_output(output_dir)
            self.assertEqual(
                [row["daytime"] for row in rows],
                [
                    "2022-01-01 00:00:00",
                    "2022-01-01 00:00:01",
                    "2022-01-01 00:00:02",
                    "2022-01-01 00:00:03",
                ],
            )

    def test_combine_skips_header_only_csv_before_data(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            input_a = root / "a"
            input_b = root / "b"
            output_dir = root / "out"
            input_a.mkdir()
            input_b.mkdir()

            self.write_csv(input_a / "000.csv", [])
            self.write_csv(
                input_a / "001.csv",
                [{"daytime": "2022-01-01 00:00:00", "label": "0", "conn_state": "SF"}],
            )
            self.write_csv(
                input_b / "000.csv",
                [{"daytime": "2022-01-01 00:00:01", "label": "1", "conn_state": "S0"}],
            )

            combine_csv_directories(str(input_a), str(input_b), str(output_dir), chunk_size=10)

            rows = self.flatten_output(output_dir)
            self.assertEqual(
                [row["daytime"] for row in rows],
                ["2022-01-01 00:00:00", "2022-01-01 00:00:01"],
            )

    def test_combine_rejects_non_positive_chunk_size(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            input_a = root / "a"
            input_b = root / "b"
            output_dir = root / "out"
            input_a.mkdir()
            input_b.mkdir()

            self.write_csv(
                input_a / "000.csv",
                [{"daytime": "2022-01-01 00:00:00", "label": "0", "conn_state": "SF"}],
            )
            self.write_csv(
                input_b / "000.csv",
                [{"daytime": "2022-01-01 00:00:01", "label": "1", "conn_state": "S0"}],
            )

            with self.assertRaisesRegex(ValueError, "CHUNK_SIZE must be a positive integer"):
                combine_csv_directories(str(input_a), str(input_b), str(output_dir), chunk_size=0)

    def test_combine_rejects_non_empty_output_dir(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            input_a = root / "a"
            input_b = root / "b"
            output_dir = root / "out"
            input_a.mkdir()
            input_b.mkdir()
            output_dir.mkdir()
            (output_dir / "stale.csv").write_text("stale", encoding="utf-8")

            self.write_csv(
                input_a / "000.csv",
                [{"daytime": "2022-01-01 00:00:00", "label": "0", "conn_state": "SF"}],
            )
            self.write_csv(
                input_b / "000.csv",
                [{"daytime": "2022-01-01 00:00:01", "label": "1", "conn_state": "S0"}],
            )

            with self.assertRaisesRegex(ValueError, "OUTPUT_DIR must be empty"):
                combine_csv_directories(str(input_a), str(input_b), str(output_dir), chunk_size=10)

    def test_combine_rejects_invalid_daytime_value(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            input_a = root / "a"
            input_b = root / "b"
            output_dir = root / "out"
            input_a.mkdir()
            input_b.mkdir()

            self.write_csv(
                input_a / "000.csv",
                [{"daytime": "bad-time", "label": "0", "conn_state": "SF"}],
            )
            self.write_csv(
                input_b / "000.csv",
                [{"daytime": "2022-01-01 00:00:01", "label": "1", "conn_state": "S0"}],
            )

            with self.assertRaisesRegex(ValueError, "Invalid daytime value"):
                combine_csv_directories(str(input_a), str(input_b), str(output_dir), chunk_size=10)

    def test_combine_rejects_when_input_has_no_data_rows(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            input_a = root / "a"
            input_b = root / "b"
            output_dir = root / "out"
            input_a.mkdir()
            input_b.mkdir()

            self.write_csv(input_a / "000.csv", [])
            self.write_csv(input_b / "000.csv", [])

            with self.assertRaisesRegex(ValueError, "at least one data row"):
                combine_csv_directories(str(input_a), str(input_b), str(output_dir), chunk_size=10)


if __name__ == "__main__":
    unittest.main()
