import csv
import json
import tempfile
import unittest
from pathlib import Path

from src.util.FeatureExtract.Zeek.log_to_csv_extractor import convert_log_dir


class ZeekLogToCsvExtractorTests(unittest.TestCase):
    def write_json_lines(self, path, records):
        with path.open("w", encoding="utf-8") as f:
            for record in records:
                f.write(json.dumps(record, ensure_ascii=True))
                f.write("\n")

    def read_csv_rows(self, path):
        with path.open("r", encoding="utf-8", newline="") as f:
            return list(csv.DictReader(f))

    def network_conf(self):
        return {
            "BENIGN": ["192.168.0.0/24"],
            "MALICIOUS": [],
            "EXCEPTION": [],
        }

    def test_convert_log_dir_sorts_by_flow_end_time(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            log_dir = root / "logs" / "20220101000000"
            log_dir.mkdir(parents=True)
            destination = root / "csv" / "20220101000000.csv"

            self.write_json_lines(
                log_dir / "conn.log",
                [
                    {
                        "ts": 1640995200,
                        "duration": 600,
                        "id.orig_h": "192.168.0.10",
                        "id.resp_h": "8.8.8.8",
                        "conn_state": "SF",
                    },
                    {
                        "ts": 1640995205,
                        "duration": 1,
                        "id.orig_h": "192.168.0.10",
                        "id.resp_h": "8.8.4.4",
                        "conn_state": "SF",
                    },
                ],
            )

            convert_log_dir(log_dir, destination, self.network_conf(), ["conn.log"])

            rows = self.read_csv_rows(destination)
            self.assertEqual(
                [row["daytime"] for row in rows],
                [
                    "2022-01-01 09:00:06",
                    "2022-01-01 09:10:00",
                ],
            )

    def test_convert_log_dir_keeps_zero_duration_as_valid_end_time(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            log_dir = root / "logs" / "20220101000000"
            log_dir.mkdir(parents=True)
            destination = root / "csv" / "20220101000000.csv"

            self.write_json_lines(
                log_dir / "conn.log",
                [
                    {
                        "ts": 1640995200,
                        "duration": 0,
                        "id.orig_h": "192.168.0.10",
                        "id.resp_h": "8.8.8.8",
                        "conn_state": "SF",
                    }
                ],
            )

            convert_log_dir(log_dir, destination, self.network_conf(), ["conn.log"])

            rows = self.read_csv_rows(destination)
            self.assertEqual(rows[0]["daytime"], "2022-01-01 09:00:00")

    def test_convert_log_dir_falls_back_to_start_time_when_duration_is_missing_or_invalid(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            log_dir = root / "logs" / "20220101000000"
            log_dir.mkdir(parents=True)
            destination = root / "csv" / "20220101000000.csv"

            self.write_json_lines(
                log_dir / "conn.log",
                [
                    {
                        "ts": 1640995200,
                        "duration": "",
                        "id.orig_h": "192.168.0.10",
                        "id.resp_h": "8.8.8.8",
                        "conn_state": "SF",
                    },
                    {
                        "ts": 1640995210,
                        "duration": "bad",
                        "id.orig_h": "192.168.0.11",
                        "id.resp_h": "1.1.1.1",
                        "conn_state": "SF",
                    },
                ],
            )

            convert_log_dir(log_dir, destination, self.network_conf(), ["conn.log"])

            rows = self.read_csv_rows(destination)
            self.assertEqual(
                [row["daytime"] for row in rows],
                [
                    "2022-01-01 09:00:00",
                    "2022-01-01 09:00:10",
                ],
            )


if __name__ == "__main__":
    unittest.main()
