import csv
import json
import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "-1")

REPO_ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(REPO_ROOT / "src" / "main"))

from ModelFactory import ModelFactory
from SessionController import SessionController
from SettingsLoader import SettingsLoader


SPLIT_HEADERS = [
    "daytime",
    "label",
    "conn_state",
    "duration",
    "orig_bytes",
    "resp_bytes",
    "orig_pkts",
    "resp_pkts",
    "orig_ip_bytes",
    "resp_ip_bytes",
    "missed_bytes",
    "local_orig",
    "local_resp",
]


class MainPipelineTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.base = Path(self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def make_row(self, daytime: str, **overrides):
        row = {
            "daytime": daytime,
            "label": "0",
            "conn_state": "SF",
            "duration": "1.0",
            "orig_bytes": "100",
            "resp_bytes": "200",
            "orig_pkts": "1",
            "resp_pkts": "2",
            "orig_ip_bytes": "120",
            "resp_ip_bytes": "240",
            "missed_bytes": "0",
            "local_orig": "True",
            "local_resp": "False",
        }
        row.update(overrides)
        return row

    def write_split_csv(self, path: Path, rows=None, headers=None):
        path.parent.mkdir(parents=True, exist_ok=True)
        headers = headers or SPLIT_HEADERS
        rows = rows or [self.make_row("2024-01-01 00:00:10")]
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(headers)
            for row in rows:
                writer.writerow([row.get(header, "") for header in headers])

    def build_settings(
        self,
        dataset_dir: Path,
        *,
        retraining_mode: str = "nt",
        retraining_interval: int = 10,
        evaluate_unit_interval: int = 3600,
    ):
        return {
            "OS": {
                "TF_CPP_MIN_LOG_LEVEL": "3",
                "TF_FORCE_GPU_ALLOW_GROWTH": "true",
                "CUDA_VISIBLE_DEVICES": "-1",
            },
            "USER_DIR": str(self.base),
            "MODEL_CODE": 4,
            "FOUNDATION_MODEL_PATH": "",
            "FeatureSchema": {
                "MODE": "split",
                "LABEL_COLUMN": "label",
                "LEGACY_FEATURES": [
                    "rcv_packet_count",
                    "snd_packet_count",
                    "tcp_count",
                    "udp_count",
                    "most_port",
                    "port_count",
                    "rcv_max_interval",
                    "rcv_min_interval",
                    "rcv_max_length",
                    "rcv_min_length",
                    "snd_max_interval",
                    "snd_min_interval",
                    "snd_max_length",
                    "snd_min_length",
                ],
                "LABEL_FEATURES": ["conn_state"],
                "VECTOR_FEATURES": [
                    "duration",
                    "orig_bytes",
                    "resp_bytes",
                    "orig_pkts",
                    "resp_pkts",
                    "orig_ip_bytes",
                    "resp_ip_bytes",
                    "missed_bytes",
                    "local_orig",
                    "local_resp",
                ],
            },
            "DATASETS_DIR_PATH": str(dataset_dir),
            "SESSION_START_DATE": "2024-01-01 00:00:00",
            "TargetRange": {"DAYS": 0, "HOURS": 0, "MINUTES": 1, "SECONDS": 0},
            "ONLINE_MODE": 0,
            "RETRAINING_MODE": retraining_mode,
            "RETRAINING_INTERVAL": retraining_interval,
            "EVALUATE_UNIT_INTERVAL": evaluate_unit_interval,
            "TrainingDefine": {"EPOCHS": 1, "BATCH_SIZE": 1},
            "DriftDetection": {
                "OBS_MODE": 0,
                "DRIFT_DETECTION_UNIT_INTERVAL": 1,
                "ENSEMBLE_METHOD_CODE": 1,
                "WindowConfig": [
                    {
                        "CURRENT_WIN_SIZE": 1,
                        "PAST_WIN_SIZE": 1,
                        "METHOD_CODE": 1,
                        "K": 1,
                        "THRESHOLD": 0.0,
                    }
                ],
            },
        }

    def write_settings_file(self, dataset_dir: Path, **settings_overrides) -> Path:
        settings = self.build_settings(dataset_dir, **settings_overrides)
        settings_path = self.base / "settings.json"
        settings_path.write_text(json.dumps(settings), encoding="utf-8")
        return settings_path

    def build_runtime(self, settings_path: Path):
        loader = SettingsLoader(str(settings_path))
        session = SessionController(loader)
        model_factory = ModelFactory(
            model_code=loader.get("MODEL_CODE"),
            user_dir_path=loader.get("USER_DIR"),
            foundation_model_path=loader.get("FOUNDATION_MODEL_PATH"),
            input_dim=loader.resolve_input_dim(),
        )
        return session, model_factory

    def test_run_completes_with_leaf_dataset_directory(self):
        dataset_dir = self.base / "datasets" / "conn"
        self.write_split_csv(dataset_dir / "20240101000000.csv")
        settings_path = self.write_settings_file(dataset_dir)

        session, model_factory = self.build_runtime(settings_path)
        session.run(model_factory)

        output_path = Path(session.output_path)
        self.assertTrue((output_path / "settings_log.json").is_file())
        self.assertTrue((output_path / "res_eval.csv").is_file())

    def test_static_mode_writes_per_key_training_results(self):
        dataset_dir = self.base / "datasets" / "conn"
        self.write_split_csv(
            dataset_dir / "20240101000000.csv",
            rows=[
                self.make_row("2024-01-01 00:00:00", label="0", conn_state="SF"),
                self.make_row("2024-01-01 00:00:12", label="1", conn_state="S0"),
                self.make_row("2024-01-01 00:00:24", label="0", conn_state="SF"),
                self.make_row("2024-01-01 00:00:36", label="1", conn_state="S0"),
            ],
        )
        settings_path = self.write_settings_file(dataset_dir, retraining_mode="st")

        session, model_factory = self.build_runtime(settings_path)
        session.run(model_factory)

        output_path = Path(session.output_path)
        self.assertTrue((output_path / "res_train_SF_m0.csv").is_file())
        self.assertTrue((output_path / "res_train_S0_m0.csv").is_file())
        self.assertTrue((output_path / "keys" / "SF" / "m1_weights").is_dir())
        self.assertTrue((output_path / "keys" / "S0" / "m1_weights").is_dir())

    def test_dynamic_mode_completes_with_leaf_dataset_directory(self):
        dataset_dir = self.base / "datasets" / "conn"
        self.write_split_csv(
            dataset_dir / "20240101000000.csv",
            rows=[
                self.make_row("2024-01-01 00:00:00", label="0", conn_state="SF"),
                self.make_row("2024-01-01 00:00:01", label="1", conn_state="SF"),
                self.make_row("2024-01-01 00:00:03", label="0", conn_state="SF"),
                self.make_row("2024-01-01 00:00:05", label="1", conn_state="SF"),
            ],
        )
        settings_path = self.write_settings_file(dataset_dir, retraining_mode="dy")

        session, model_factory = self.build_runtime(settings_path)
        session.run(model_factory)

        output_path = Path(session.output_path)
        self.assertTrue((output_path / "settings_log.json").is_file())
        self.assertTrue((output_path / "res_eval.csv").is_file())
        self.assertTrue((output_path / "m0_weights").is_dir())
        self.assertTrue((output_path / "m1_weights").is_dir())

    def test_invalid_dataset_directory_with_nested_folder_raises_error(self):
        dataset_dir = self.base / "datasets" / "mixed"
        self.write_split_csv(dataset_dir / "20240101000000.csv")
        (dataset_dir / "subdir").mkdir(parents=True, exist_ok=True)
        settings_path = self.write_settings_file(dataset_dir)

        session, model_factory = self.build_runtime(settings_path)

        with self.assertRaises(IsADirectoryError):
            session.run(model_factory)

    def test_missing_feature_column_raises_error(self):
        dataset_dir = self.base / "datasets" / "conn"
        headers = [header for header in SPLIT_HEADERS if header != "orig_bytes"]
        self.write_split_csv(
            dataset_dir / "20240101000000.csv",
            rows=[self.make_row("2024-01-01 00:00:10")],
            headers=headers,
        )
        settings_path = self.write_settings_file(dataset_dir)

        session, model_factory = self.build_runtime(settings_path)

        with self.assertRaisesRegex(ValueError, "Missing feature columns"):
            session.run(model_factory)

    def test_invalid_boolean_value_raises_error(self):
        dataset_dir = self.base / "datasets" / "conn"
        self.write_split_csv(
            dataset_dir / "20240101000000.csv",
            rows=[self.make_row("2024-01-01 00:00:10", local_orig="maybe")],
        )
        settings_path = self.write_settings_file(dataset_dir)

        session, model_factory = self.build_runtime(settings_path)

        with self.assertRaisesRegex(ValueError, "Non-numeric feature value"):
            session.run(model_factory)


if __name__ == "__main__":
    unittest.main()
