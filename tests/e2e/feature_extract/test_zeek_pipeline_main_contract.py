import csv
import json
import shutil
from pathlib import Path

import pytest

from src.util.FeatureExtract.Zeek import log_to_csv_extractor as csv_extractor
from src.util.FeatureExtract.Zeek import pcap_to_csv_pipeline as pipeline
from src.util.FeatureExtract.Zeek import pcap_to_log_extractor as pcap_extractor


ROOT_DIR = Path(__file__).resolve().parents[3]
FIXTURE_DIR = ROOT_DIR / "tests" / "fixtures"
DEFAULT_NETWORK_CONF = {
    "BENIGN": ["192.168.0.0/24"],
    "MALICIOUS": [],
    "EXCEPTION": [],
}


def read_csv_rows(path):
    with path.open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def snapshot_csv_dir(csv_dir):
    snapshot = []
    for csv_path in sorted(csv_dir.glob("*.csv")):
        with csv_path.open("r", encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            fieldnames = tuple(name for name in (reader.fieldnames or []) if name != "uid")
            snapshot.append(
                (
                    csv_path.name,
                    fieldnames,
                    tuple(
                        tuple(sorted((key, value) for key, value in row.items() if key != "uid"))
                        for row in reader
                    ),
                )
            )
    return tuple(snapshot)


def prepare_pipeline_fixture(tmp_path, pcap_names, *, network_conf=None):
    root = Path(tmp_path)
    input_dir = root / "pcap" / "sample_batch"
    input_dir.mkdir(parents=True)
    if isinstance(pcap_names, str):
        pcap_names = [pcap_names]
    for pcap_name in pcap_names:
        target_name = pcap_name.replace("zeek_udp_", "").replace(".pcap", "") + ".pcap"
        pcap_path = input_dir / target_name
        pcap_path.write_bytes((FIXTURE_DIR / "pcap" / pcap_name).read_bytes())
    log_output_root = root / "logs"
    csv_output_root = root / "csv"
    settings_path = root / "zeek_settings.json"
    settings = {
        "PcapToLog": {
            "INPUT_DIR_PATH": str(input_dir),
            "OUTPUT_ROOT_DIR_PATH": str(log_output_root),
        },
        "LogToCsv": {
            "INPUT_DIR_PATH": str(log_output_root / input_dir.name),
            "OUTPUT_ROOT_DIR_PATH": str(csv_output_root),
            "TARGET_LOGS": ["conn.log"],
            "AUTO_VALIDATE_CONN_OUTPUT": True,
            "NETWORK_KEY": "test_network",
        },
        "NetworkAddress": {
            "test_network": network_conf or DEFAULT_NETWORK_CONF
        },
    }
    settings_path.write_text(json.dumps(settings, indent=2), encoding="utf-8")
    return input_dir, log_output_root, csv_output_root, settings_path


def patch_settings(monkeypatch, settings_path):
    monkeypatch.setattr(pcap_extractor, "SETTINGS_PATH", settings_path)
    monkeypatch.setattr(csv_extractor, "SETTINGS_PATH", settings_path)
    monkeypatch.setattr(pcap_extractor, "parse_args", lambda: None)
    monkeypatch.setattr(csv_extractor, "parse_args", lambda: None)


# Input:
# - roundtrip.pcap を 1 件だけ含む sample_batch
# - temp settings 経由で pcap_to_log_extractor.main() を実行
# Expectation:
# - <log_output_root>/<input_dir_name>/<timestamp>/conn.log が作られる
# - timestamp は最小 ts を JST 化した 20220101090000 になる
# - .tmp_* の中間ディレクトリは残らない
# Target script:
# - pcap_to_log_extractor.main()
# Overview:
# - settings 読込、PCAP 収集、zeek 実行、timestamp dir 命名、最終配置までを通す。
# Note:
# - Zeek の解析内容の厳密比較ではなく wrapper の出力レイアウト契約を見る。
@pytest.mark.e2e
@pytest.mark.skipif(shutil.which("zeek") is None, reason="zeek command is required for e2e feature extraction tests")
def test_pcap_to_log_main_creates_timestamped_log_dir(tmp_path, monkeypatch):
    input_dir, log_output_root, _, settings_path = prepare_pipeline_fixture(
        tmp_path,
        "zeek_udp_roundtrip.pcap",
    )
    patch_settings(monkeypatch, settings_path)

    pcap_extractor.main()

    batch_dir = log_output_root / input_dir.name
    final_dir = batch_dir / "20220101090000"
    assert batch_dir.is_dir()
    assert final_dir.is_dir()
    assert (final_dir / "conn.log").is_file()
    assert not any(path.name.startswith(".tmp_") for path in batch_dir.iterdir())


# Input:
# - roundtrip.pcap を 1 件だけ含む sample_batch
# - temp settings 経由で pcap_to_log_extractor.main() と log_to_csv_extractor.main() を順に実行
# Expectation:
# - <csv_output_root>/conn/<batch_name>/00000_<first_daytime>.csv が作られる
# - CSV row の daytime は flow end time 由来で 2022-01-01 09:00:01 になる
# - rows は daytime 昇順で label は数値化可能
# Target script:
# - pcap_to_log_extractor.main()
# - log_to_csv_extractor.main()
# Overview:
# - real zeek を通して pcap -> log -> csv の wrapper 導線を最後まで実行する。
# Note:
# - current repo contract のうち、leaf CSV dir レイアウトと daytime 生成ルールを固定する。
@pytest.mark.e2e
@pytest.mark.skipif(shutil.which("zeek") is None, reason="zeek command is required for e2e feature extraction tests")
def test_full_pipeline_main_creates_leaf_csv_output_with_flow_end_daytime(tmp_path, monkeypatch):
    input_dir, log_output_root, csv_output_root, settings_path = prepare_pipeline_fixture(
        tmp_path,
        "zeek_udp_roundtrip.pcap",
    )
    patch_settings(monkeypatch, settings_path)

    pcap_extractor.main()
    csv_extractor.main()

    batch_dir = log_output_root / input_dir.name
    assert (batch_dir / "20220101090000" / "conn.log").is_file()

    csv_dir = csv_output_root / "conn" / input_dir.name
    csv_path = csv_dir / "00000_20220101090001.csv"
    assert csv_dir.is_dir()
    assert csv_path.is_file()

    rows = read_csv_rows(csv_path)
    assert len(rows) == 1
    assert [row["daytime"] for row in rows] == sorted(row["daytime"] for row in rows)
    assert rows[0]["daytime"] == "2022-01-01 09:00:01"
    assert rows[0]["label"] == "0"


# Input:
# - 同一 batch に roundtrip.pcap と two_roundtrips.pcap を置く
# - temp settings 経由で pcap_to_log_extractor.main() と log_to_csv_extractor.main() を順に実行
# Expectation:
# - log dir は 2 件できる
# - csv dir は batch 全体を daytime で再統合した 1 件以上の chunk として出力される
# - 最終 CSV 群を連結すると row 全体が daytime 昇順になる
# Target script:
# - pcap_to_log_extractor.main()
# - log_to_csv_extractor.main()
# Overview:
# - batch 入力で複数 pcap を処理したときのレイアウト契約を確認する。
@pytest.mark.e2e
@pytest.mark.skipif(shutil.which("zeek") is None, reason="zeek command is required for e2e feature extraction tests")
def test_full_pipeline_main_handles_multiple_pcaps_in_one_batch(tmp_path, monkeypatch):
    input_dir, log_output_root, csv_output_root, settings_path = prepare_pipeline_fixture(
        tmp_path,
        ["zeek_udp_roundtrip.pcap", "zeek_udp_two_roundtrips.pcap"],
    )
    patch_settings(monkeypatch, settings_path)

    pcap_extractor.main()
    csv_extractor.main()

    batch_log_dir = log_output_root / input_dir.name
    assert (batch_log_dir / "20220101090000" / "conn.log").is_file()
    assert (batch_log_dir / "20220101090200" / "conn.log").is_file()

    csv_dir = csv_output_root / "conn" / input_dir.name
    csv_files = sorted(csv_dir.glob("*.csv"))
    assert [path.name for path in csv_files] == ["00000_20220101090001.csv"]

    rows = read_csv_rows(csv_files[0])
    assert len(rows) == 3
    assert [row["daytime"] for row in rows] == [
        "2022-01-01 09:00:01",
        "2022-01-01 09:02:01",
        "2022-01-01 09:02:12",
    ]


# Input:
# - roundtrip.pcap を 1 件だけ含む sample_batch
# - temp settings 経由で pcap_to_csv_pipeline.main() を実行
# Expectation:
# - pcap -> log -> csv を 1 コマンドで最後まで実行できる
# - conn.log 系 CSV 出力後に runtime契約チェックが標準出力へ出る
# Target script:
# - pcap_to_csv_pipeline.main()
# Overview:
# - 新設した wrapper コマンドが、実 Zeek を通した stable workflow をまとめて実行できることを固定する。
@pytest.mark.e2e
@pytest.mark.skipif(shutil.which("zeek") is None, reason="zeek command is required for e2e feature extraction tests")
def test_pcap_to_csv_pipeline_main_runs_both_steps_and_runtime_validation(tmp_path, monkeypatch, capsys):
    input_dir, log_output_root, csv_output_root, settings_path = prepare_pipeline_fixture(
        tmp_path,
        "zeek_udp_roundtrip.pcap",
    )
    patch_settings(monkeypatch, settings_path)
    monkeypatch.setattr(pipeline, "parse_args", lambda: None)

    pipeline.main()

    batch_dir = log_output_root / input_dir.name
    csv_dir = csv_output_root / "conn" / input_dir.name
    csv_path = csv_dir / "00000_20220101090001.csv"

    assert (batch_dir / "20220101090000" / "conn.log").is_file()
    assert csv_path.is_file()

    stdout = capsys.readouterr().out
    assert "[pcap-to-csv] pcap -> log 開始" in stdout
    assert "[pcap-to-csv] log -> csv 開始" in stdout
    assert "[runtime契約チェック]" in stdout
    assert "総合判定: 合格" in stdout


# Input:
# - 同じ pcap fixture を 2 系統の一時環境へ複製する
# - 一方は `pcap-to-log -> log-to-csv` を順に実行
# - もう一方は `pcap-to-csv` を 1 コマンドで実行
# Expectation:
# - 出力される leaf CSV 群が、Zeek 実行ごとに変わりうる `uid` を除いて一致する
# Target script:
# - pcap_to_log_extractor.main()
# - log_to_csv_extractor.main()
# - pcap_to_csv_pipeline.main()
# Overview:
# - wrapper コマンドが手動 2 段実行と同じ CSV を作ることを固定する。
@pytest.mark.e2e
@pytest.mark.skipif(shutil.which("zeek") is None, reason="zeek command is required for e2e feature extraction tests")
def test_pcap_to_csv_pipeline_matches_manual_two_step_pipeline_output(tmp_path, monkeypatch):
    manual_root = Path(tmp_path) / "manual"
    pipeline_root = Path(tmp_path) / "pipeline"

    manual_input_dir, manual_log_output_root, manual_csv_output_root, manual_settings_path = prepare_pipeline_fixture(
        manual_root,
        ["zeek_udp_roundtrip.pcap", "zeek_udp_two_roundtrips.pcap"],
    )
    patch_settings(monkeypatch, manual_settings_path)
    pcap_extractor.main()
    csv_extractor.main()
    manual_csv_dir = manual_csv_output_root / "conn" / manual_input_dir.name

    pipeline_input_dir, pipeline_log_output_root, pipeline_csv_output_root, pipeline_settings_path = prepare_pipeline_fixture(
        pipeline_root,
        ["zeek_udp_roundtrip.pcap", "zeek_udp_two_roundtrips.pcap"],
    )
    patch_settings(monkeypatch, pipeline_settings_path)
    monkeypatch.setattr(pipeline, "parse_args", lambda: None)
    pipeline.main()
    pipeline_csv_dir = pipeline_csv_output_root / "conn" / pipeline_input_dir.name

    assert (manual_log_output_root / manual_input_dir.name / "20220101090000" / "conn.log").is_file()
    assert (pipeline_log_output_root / pipeline_input_dir.name / "20220101090000" / "conn.log").is_file()
    assert snapshot_csv_dir(pipeline_csv_dir) == snapshot_csv_dir(manual_csv_dir)
