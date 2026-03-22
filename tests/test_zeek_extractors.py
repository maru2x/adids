import csv
import importlib.util
import json
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]
ZEEK_DIR = REPO_ROOT / "src" / "util" / "FeatureExtract" / "Zeek"


def load_module(module_name: str, file_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class ZeekExtractorTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.base = Path(self.tmpdir.name)
        self.pcap_to_log = load_module("pcap_to_log_test", ZEEK_DIR / "PcapToLogExtractor.py")
        self.log_to_csv = load_module("log_to_csv_test", ZEEK_DIR / "LogToCsvExtractor.py")

    def tearDown(self):
        self.tmpdir.cleanup()

    def write_json_lines(self, path: Path, records):
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as fh:
            for record in records:
                fh.write(json.dumps(record) + "\n")

    def read_csv_rows(self, path: Path):
        with path.open(newline="", encoding="utf-8") as fh:
            return list(csv.DictReader(fh))

    def write_log_to_csv_settings(
        self,
        batch_root: Path,
        output_root: Path,
        *,
        target_logs=None,
        network_key="lab",
        network_address=None,
    ) -> Path:
        if target_logs is None:
            target_logs = ["conn.log"]
        if network_address is None:
            network_address = {
                network_key: {
                    "BENIGN": ["192.168.1.0/24"],
                    "MALICIOUS": ["10.0.0.0/24"],
                    "EXCEPTION": ["8.8.8.8/32"],
                }
            }
        settings_path = self.base / f"{batch_root.name}_log_to_csv_settings.json"
        settings_path.write_text(
            json.dumps(
                {
                    "LogToCsv": {
                        "INPUT_DIR_PATH": str(batch_root),
                        "OUTPUT_ROOT_DIR_PATH": str(output_root),
                        "TARGET_LOGS": target_logs,
                        "NETWORK_KEY": network_key,
                    },
                    "NetworkAddress": network_address,
                }
            ),
            encoding="utf-8",
        )
        return settings_path

    def test_pcap_to_log_creates_batch_layout_from_settings(self):
        input_dir = self.base / "captures"
        nested_dir = input_dir / "nested"
        nested_dir.mkdir(parents=True)
        (input_dir / "alpha.pcap").write_text("", encoding="utf-8")
        (nested_dir / "beta.pcap").write_text("", encoding="utf-8")

        output_root = self.base / "logs"
        settings_path = self.base / "pcap_settings.json"
        settings_path.write_text(
            json.dumps(
                {
                    "PcapToLog": {
                        "INPUT_DIR_PATH": str(input_dir),
                        "OUTPUT_ROOT_DIR_PATH": str(output_root),
                    }
                }
            ),
            encoding="utf-8",
        )

        ts_map = {
            "alpha": 1704067200.0,
            "beta": 1704067260.0,
        }

        def fake_run_zeek(pcap_file: Path, output_dir: Path):
            ts = ts_map[pcap_file.stem]
            self.write_json_lines(
                output_dir / "conn.log",
                [
                    {
                        "ts": ts,
                        "uid": f"{pcap_file.stem}-uid",
                        "id.orig_h": "192.168.1.10",
                        "id.resp_h": "1.1.1.1",
                    }
                ],
            )

        with mock.patch.object(self.pcap_to_log, "SETTINGS_PATH", settings_path), \
             mock.patch.object(self.pcap_to_log, "parse_args", return_value=types.SimpleNamespace()), \
             mock.patch.object(self.pcap_to_log, "run_zeek", side_effect=fake_run_zeek):
            self.pcap_to_log.main()

        batch_dir = output_root / input_dir.name
        self.assertTrue(batch_dir.is_dir())

        expected_dirs = {
            self.pcap_to_log.ts_to_name(ts_map["alpha"], "alpha"),
            self.pcap_to_log.ts_to_name(ts_map["beta"], "beta"),
        }
        actual_dirs = {path.name for path in batch_dir.iterdir() if path.is_dir()}
        self.assertEqual(expected_dirs, actual_dirs)
        for dir_name in expected_dirs:
            self.assertTrue((batch_dir / dir_name / "conn.log").is_file())

    def test_pcap_to_log_cleans_tmp_dir_on_zeek_failure(self):
        input_dir = self.base / "captures"
        input_dir.mkdir(parents=True)
        (input_dir / "alpha.pcap").write_text("", encoding="utf-8")

        output_root = self.base / "logs"
        settings_path = self.base / "pcap_failure_settings.json"
        settings_path.write_text(
            json.dumps(
                {
                    "PcapToLog": {
                        "INPUT_DIR_PATH": str(input_dir),
                        "OUTPUT_ROOT_DIR_PATH": str(output_root),
                    }
                }
            ),
            encoding="utf-8",
        )

        with mock.patch.object(self.pcap_to_log, "SETTINGS_PATH", settings_path), \
             mock.patch.object(self.pcap_to_log, "parse_args", return_value=types.SimpleNamespace()), \
             mock.patch.object(self.pcap_to_log, "run_zeek", side_effect=SystemExit("zeek failed")):
            with self.assertRaisesRegex(SystemExit, "zeek failed"):
                self.pcap_to_log.main()

        batch_dir = output_root / input_dir.name
        self.assertTrue(batch_dir.is_dir())
        self.assertEqual(list(batch_dir.iterdir()), [])

    def test_log_to_csv_creates_per_log_directories_and_excludes_exception(self):
        batch_root = self.base / "log_batches" / "sample_batch"
        log_dir = batch_root / "20240101090000"
        log_dir.mkdir(parents=True)

        self.write_json_lines(
            log_dir / "conn.log",
            [
                {
                    "ts": 1704067200.0,
                    "uid": "good",
                    "id.orig_h": "192.168.1.10",
                    "id.resp_h": "1.1.1.1",
                    "conn_state": "SF",
                    "duration": 1.0,
                },
                {
                    "ts": 1704067201.0,
                    "uid": "drop-exception",
                    "id.orig_h": "192.168.1.10",
                    "id.resp_h": "8.8.8.8",
                    "conn_state": "SF",
                    "duration": 2.0,
                },
                {
                    "ts": 1704067202.0,
                    "uid": "bad",
                    "id.orig_h": "10.0.0.10",
                    "id.resp_h": "192.168.1.20",
                    "conn_state": "S0",
                    "duration": 3.0,
                },
            ],
        )
        self.write_json_lines(
            log_dir / "http.log",
            [
                {
                    "ts": 1704067200.0,
                    "uid": "http-ok",
                    "id.orig_h": "192.168.1.10",
                    "id.resp_h": "1.1.1.1",
                    "method": "GET",
                }
            ],
        )

        output_root = self.base / "csv"
        settings_path = self.write_log_to_csv_settings(
            batch_root,
            output_root,
            target_logs=["conn.log", "http.log"],
        )

        with mock.patch.object(self.log_to_csv, "SETTINGS_PATH", settings_path), \
             mock.patch.object(self.log_to_csv, "parse_args", return_value=types.SimpleNamespace()):
            self.log_to_csv.main()

        conn_csv = output_root / batch_root.name / "conn" / f"{log_dir.name}.csv"
        http_csv = output_root / batch_root.name / "http" / f"{log_dir.name}.csv"
        self.assertTrue(conn_csv.is_file())
        self.assertTrue(http_csv.is_file())

        conn_rows = self.read_csv_rows(conn_csv)
        self.assertEqual([row["uid"] for row in conn_rows], ["good", "bad"])
        self.assertEqual([row["label"] for row in conn_rows], ["0", "1"])

        http_rows = self.read_csv_rows(http_csv)
        self.assertEqual(len(http_rows), 1)
        self.assertEqual(http_rows[0]["uid"], "http-ok")
        self.assertEqual(http_rows[0]["label"], "0")

    def test_log_to_csv_rejects_invalid_json(self):
        batch_root = self.base / "invalid_logs" / "batch_a"
        log_dir = batch_root / "20240101090100"
        log_dir.mkdir(parents=True)
        (log_dir / "conn.log").write_text('{"ts": 1704067260.0}\n{bad json}\n', encoding="utf-8")

        output_root = self.base / "invalid_csv"
        settings_path = self.write_log_to_csv_settings(batch_root, output_root)

        with mock.patch.object(self.log_to_csv, "SETTINGS_PATH", settings_path), \
             mock.patch.object(self.log_to_csv, "parse_args", return_value=types.SimpleNamespace()):
            with self.assertRaisesRegex(SystemExit, "Invalid JSON"):
                self.log_to_csv.main()

    def test_single_target_log_still_creates_named_subdirectory(self):
        batch_root = self.base / "single_target_logs" / "batch_a"
        log_dir = batch_root / "20240101090100"
        log_dir.mkdir(parents=True)
        self.write_json_lines(
            log_dir / "conn.log",
            [
                {
                    "ts": 1704067260.0,
                    "uid": "only-row",
                    "id.orig_h": "192.168.1.10",
                    "id.resp_h": "1.1.1.1",
                    "conn_state": "SF",
                }
            ],
        )

        output_root = self.base / "single_target_csv"
        settings_path = self.write_log_to_csv_settings(batch_root, output_root, target_logs=["conn.log"])

        with mock.patch.object(self.log_to_csv, "SETTINGS_PATH", settings_path), \
             mock.patch.object(self.log_to_csv, "parse_args", return_value=types.SimpleNamespace()):
            self.log_to_csv.main()

        destination = output_root / batch_root.name / "conn" / f"{log_dir.name}.csv"
        self.assertTrue(destination.is_file())
        rows = self.read_csv_rows(destination)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["uid"], "only-row")


if __name__ == "__main__":
    unittest.main()
