import csv
import json
import sys
from pathlib import Path

import pandas as pd
import pytest


ROOT_DIR = Path(__file__).resolve().parents[3]
SRC_MAIN_DIR = ROOT_DIR / "src" / "main"


# Input:
# - 最小 3 行の zeek-mode CSV fixture
# - runtime 用 settings fixture
# Expectation:
# - 実行後に output dir, settings_log.json, res_eval.csv, m1_weights が生成される
# - output dir 名に dataset 名と retraining mode 情報が入る
@pytest.mark.e2e
def test_runtime_smoke_writes_expected_output_files(tmp_path):
    dataset_dir, settings_path = prepare_runtime_fixture(tmp_path)

    session = run_runtime_session(settings_path)

    output_dir = Path(session.output_path)
    assert output_dir.is_dir()
    assert (output_dir / "settings_log.json").is_file()
    assert (output_dir / "res_eval.csv").is_file()
    assert (output_dir / "m1_weights").is_dir()
    assert output_dir.name.endswith(f"_{dataset_dir.name}_nt_4")


# Input:
# - 同じ最小 runtime fixture
# Expectation:
# - res_eval.csv の基本 schema が成立する
# - 1 セッション分の summary が 1 行で出る
# - TP/FN/FP/TN の合計が flow_num と一致する
@pytest.mark.e2e
def test_runtime_smoke_produces_expected_eval_summary(tmp_path):
    _, settings_path = prepare_runtime_fixture(tmp_path)

    session = run_runtime_session(settings_path)

    eval_path = Path(session.output_path) / "res_eval.csv"
    eval_df = pd.read_csv(eval_path)

    assert list(eval_df.columns[:3]) == ["daytime", "label_key", "TP"]
    assert len(eval_df) == 1
    assert eval_df.loc[0, "label_key"] == "SF"
    flow_num = float(eval_df.loc[0, "flow_num"])
    assert 1.0 <= flow_num <= 3.0
    confusion_sum = (
        float(eval_df.loc[0, "TP"])
        + float(eval_df.loc[0, "FN"])
        + float(eval_df.loc[0, "FP"])
        + float(eval_df.loc[0, "TN"])
    )
    assert confusion_sum == flow_num


# Input:
# - settings.json 相当の fixture path
# Expectation:
# - src/main を import path に載せて SessionController を最後まで実行できる
# Note:
# - e2e テストから runtime を直接呼ぶための helper。
def run_runtime_session(settings_path):
    if str(SRC_MAIN_DIR) not in sys.path:
        sys.path.insert(0, str(SRC_MAIN_DIR))

    from Simulation.model_factory import ModelFactory
    from Simulation.session_controller import SessionController
    from Simulation.settings_loader import SettingsLoader

    loader = SettingsLoader(path=str(settings_path))
    session = SessionController(loader)
    model_factory = ModelFactory(
        model_code=loader.get("MODEL_CODE"),
        user_dir_path=loader.get("USER_DIR"),
        foundation_model_path=loader.get("FOUNDATION_MODEL_PATH"),
        input_dim=loader.resolve_input_dim(),
    )
    session.run(model_factory)
    return session


# Input:
# - tmp_path
# Expectation:
# - runtime が読める leaf CSV dir と対応 settings.json が生成される
# Note:
# - DATASETS_DIR_PATH は nested dir ではなく sample leaf dir を指す。
def prepare_runtime_fixture(tmp_path):
    root = Path(tmp_path)
    dataset_dir = root / "datasets" / "sample"
    dataset_dir.mkdir(parents=True)
    csv_path = dataset_dir / "part_000.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            [
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
        )
        writer.writerow(["2022-01-01 09:00:00", "0", "SF", "1", "10", "20", "1", "1", "38", "38", "0", "true", "false"])
        writer.writerow(["2022-01-01 09:00:01", "1", "SF", "1", "11", "21", "1", "1", "39", "39", "0", "true", "false"])
        writer.writerow(["2022-01-01 09:00:02", "0", "SF", "1", "12", "22", "1", "1", "40", "40", "0", "true", "false"])

    settings = {
        "OS": {
            "TF_CPP_MIN_LOG_LEVEL": "3",
            "TF_FORCE_GPU_ALLOW_GROWTH": "true",
            "CUDA_VISIBLE_DEVICES": "-1",
        },
        "USER_DIR": str(root),
        "MODEL_CODE": 4,
        "FOUNDATION_MODEL_PATH": "",
        "FeatureSchema": {
            "MODE": "zeek",
            "LABEL_COLUMN": "label",
            "LEGACY_FEATURES": [],
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
        "SESSION_START_DATE": "2022-01-01 09:00:00",
        "TargetRange": {"DAYS": 0, "HOURS": 0, "MINUTES": 0, "SECONDS": 5},
        "ONLINE_MODE": 0,
        "RETRAINING_MODE": "nt",
        "RETRAINING_INTERVAL": 3600,
        "EVALUATE_UNIT_INTERVAL": 1,
        "TrainingDefine": {"EPOCHS": 1, "BATCH_SIZE": 1},
        "DriftDetection": {
            "OBS_MODE": 0,
            "DRIFT_DETECTION_UNIT_INTERVAL": 5,
            "ENSEMBLE_METHOD_CODE": 1,
            "WindowConfig": [
                {"CURRENT_WIN_SIZE": 10, "PAST_WIN_SIZE": 10, "METHOD_CODE": 1, "K": 1, "THRESHOLD": 0.1}
            ],
        },
    }
    settings_path = root / "runtime_settings.json"
    settings_path.write_text(json.dumps(settings, indent=2), encoding="utf-8")
    return dataset_dir, settings_path
