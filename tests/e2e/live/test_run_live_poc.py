import json
import sys
import threading
import time
from pathlib import Path

import pytest


ROOT_DIR = Path(__file__).resolve().parents[3]
SRC_MAIN_DIR = ROOT_DIR / "src" / "main"


@pytest.mark.e2e
def test_run_live_processes_one_matching_row_and_prints_alert(tmp_path, capsys):
    if str(SRC_MAIN_DIR) not in sys.path:
        sys.path.insert(0, str(SRC_MAIN_DIR))

    from Live.runtime import LiveRuntime
    from Live.settings_loader import LiveSettingsLoader

    root = Path(tmp_path)
    input_dir = root / "logs" / "current"
    input_dir.mkdir(parents=True)
    conn_log_path = input_dir / "conn.log"
    conn_log_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "ts": 1710000000.0,
                        "uid": "Cdemo1",
                        "id.orig_h": "192.168.10.50",
                        "id.orig_p": 42310,
                        "id.resp_h": "192.168.10.10",
                        "id.resp_p": 2223,
                        "proto": "tcp",
                        "conn_state": "OTH",
                        "local_orig": True,
                        "local_resp": True,
                        "missed_bytes": 0,
                        "orig_pkts": 1,
                        "orig_ip_bytes": 40,
                        "resp_pkts": 0,
                        "resp_ip_bytes": 0,
                        "duration": 0.02,
                    }
                )
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    settings = {
        "OS": {
            "TF_CPP_MIN_LOG_LEVEL": "3",
            "TF_FORCE_GPU_ALLOW_GROWTH": "true",
            "CUDA_VISIBLE_DEVICES": "-1",
        },
        "USER_DIR": str(root),
        "MODEL_CODE": 4,
        "FOUNDATION_MODEL_PATH": str(root / "models" / "live_demo_model.pickle"),
        "AUTO_CREATE_DEMO_MODEL": True,
        "FeatureSchema": {
            "MODE": "zeek",
            "LABEL_COLUMN": "label",
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
        "SIMULATION_SETTINGS_PATH": str(ROOT_DIR / "src" / "main" / "Simulation" / "settings.json"),
        "FEATURE_EXPORT_INPUT_DIR_PATH": str(input_dir),
        "FEATURE_EXPORT_OUTPUT_DIR_PATH": str(root / "csv"),
        "FEATURE_EXPORT_STATE_PATH": str(root / "state" / "feature_export_state.json"),
        "FEATURE_EXPORT_LABEL": 0,
        "FEATURE_EXPORT_OUTPUT_CHUNK_SIZE": 100,
        "FEATURE_EXPORT_VALIDATE_OUTPUT": False,
        "LIVE_CURSOR_STATE_PATH": str(root / "state" / "cursor_state.json"),
        "INITIAL_POSITION": "start",
        "POLL_INTERVAL_SECONDS": 0.0,
        "MAX_POLLS": 1,
        "IDLE_LOG_EVERY_POLLS": 10,
        "ALERT_THRESHOLD": 0.5,
        "SOURCE_TYPE": "local_iot_demo",
        "TARGET_PORTS": [2223],
        "TARGET_PROTOCOLS": ["tcp"],
        "TARGET_CONN_STATES": [],
    }
    settings_path = root / "live_settings.json"
    settings_path.write_text(json.dumps(settings, indent=2), encoding="utf-8")

    loader = LiveSettingsLoader(path=str(settings_path))
    runtime = LiveRuntime(loader)
    runtime.run()

    captured = capsys.readouterr()
    assert "[ALERT]" in captured.out
    assert "dst_port=2223" in captured.out
    assert runtime.total_alert_count >= 1


@pytest.mark.e2e
def test_run_live_end_mode_ignores_existing_rows_and_alerts_on_appended_row(tmp_path, capsys):
    if str(SRC_MAIN_DIR) not in sys.path:
        sys.path.insert(0, str(SRC_MAIN_DIR))

    from Live.runtime import LiveRuntime
    from Live.settings_loader import LiveSettingsLoader

    root = Path(tmp_path)
    input_dir = root / "logs" / "current"
    input_dir.mkdir(parents=True)
    conn_log_path = input_dir / "conn.log"
    conn_log_path.write_text(
        json.dumps(
            {
                "ts": 1710000000.0,
                "uid": "Cold1",
                "id.orig_h": "192.168.10.51",
                "id.orig_p": 42311,
                "id.resp_h": "192.168.10.10",
                "id.resp_p": 2223,
                "proto": "tcp",
                "conn_state": "OTH",
                "local_orig": True,
                "local_resp": True,
                "missed_bytes": 0,
                "orig_pkts": 1,
                "orig_ip_bytes": 40,
                "resp_pkts": 0,
                "resp_ip_bytes": 0,
                "duration": 0.02,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    settings = {
        "OS": {
            "TF_CPP_MIN_LOG_LEVEL": "3",
            "TF_FORCE_GPU_ALLOW_GROWTH": "true",
            "CUDA_VISIBLE_DEVICES": "-1",
        },
        "USER_DIR": str(root),
        "MODEL_CODE": 4,
        "FOUNDATION_MODEL_PATH": str(root / "models" / "live_demo_model.pickle"),
        "AUTO_CREATE_DEMO_MODEL": True,
        "FeatureSchema": {
            "MODE": "zeek",
            "LABEL_COLUMN": "label",
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
        "SIMULATION_SETTINGS_PATH": str(ROOT_DIR / "src" / "main" / "Simulation" / "settings.json"),
        "FEATURE_EXPORT_INPUT_DIR_PATH": str(input_dir),
        "FEATURE_EXPORT_OUTPUT_DIR_PATH": str(root / "csv"),
        "FEATURE_EXPORT_STATE_PATH": str(root / "state" / "feature_export_state.json"),
        "FEATURE_EXPORT_LABEL": 0,
        "FEATURE_EXPORT_OUTPUT_CHUNK_SIZE": 100,
        "FEATURE_EXPORT_VALIDATE_OUTPUT": False,
        "LIVE_CURSOR_STATE_PATH": str(root / "state" / "cursor_state.json"),
        "INITIAL_POSITION": "end",
        "POLL_INTERVAL_SECONDS": 0.05,
        "MAX_POLLS": 3,
        "IDLE_LOG_EVERY_POLLS": 10,
        "ALERT_THRESHOLD": 0.5,
        "SOURCE_TYPE": "local_iot_demo",
        "TARGET_PORTS": [2223],
        "TARGET_PROTOCOLS": ["tcp"],
        "TARGET_CONN_STATES": [],
    }
    settings_path = root / "live_settings.json"
    settings_path.write_text(json.dumps(settings, indent=2), encoding="utf-8")

    loader = LiveSettingsLoader(path=str(settings_path))
    runtime = LiveRuntime(loader)

    def append_matching_row():
        time.sleep(0.07)
        with conn_log_path.open("a", encoding="utf-8") as fh:
            fh.write(
                json.dumps(
                    {
                        "ts": 1710000001.0,
                        "uid": "Cnew1",
                        "id.orig_h": "192.168.10.52",
                        "id.orig_p": 42312,
                        "id.resp_h": "192.168.10.10",
                        "id.resp_p": 2223,
                        "proto": "tcp",
                        "conn_state": "OTH",
                        "local_orig": True,
                        "local_resp": True,
                        "missed_bytes": 0,
                        "orig_pkts": 1,
                        "orig_ip_bytes": 40,
                        "resp_pkts": 0,
                        "resp_ip_bytes": 0,
                        "duration": 0.02,
                    }
                )
                + "\n"
            )

    writer_thread = threading.Thread(target=append_matching_row)
    writer_thread.start()
    runtime.run()
    writer_thread.join()

    captured = capsys.readouterr()
    assert runtime.total_alert_count == 1
    assert captured.out.count("[ALERT]") == 1
