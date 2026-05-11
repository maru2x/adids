import csv
import json
from pathlib import Path

from src.util.FeatureExtract.Zeek import log_to_csv_extractor as csv_extractor
from src.util.FeatureExtract.Zeek import pcap_to_log_extractor as pcap_extractor


ROOT_DIR = Path(__file__).resolve().parents[3]
FIXTURE_DIR = ROOT_DIR / "tests" / "fixtures"
DEFAULT_NETWORK_CONF = {
    "BENIGN": ["192.168.0.0/24"],
    "MALICIOUS": [],
    "EXCEPTION": [],
}
REQUIRED_RUNTIME_COLUMNS = (
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
)
NUMERIC_OR_EMPTY_COLUMNS = (
    "duration",
    "orig_bytes",
    "resp_bytes",
    "orig_pkts",
    "resp_pkts",
    "orig_ip_bytes",
    "resp_ip_bytes",
    "missed_bytes",
)


def read_csv_content(path):
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)
        return reader.fieldnames or [], rows


def prepare_pipeline_fixture(
    tmp_path,
    relative_pcap_paths,
    *,
    target_logs,
    network_conf=None,
):
    root = Path(tmp_path)
    input_dir = root / "pcap" / "sample_batch"
    input_dir.mkdir(parents=True)
    if isinstance(relative_pcap_paths, str):
        relative_pcap_paths = [relative_pcap_paths]
    for rel_path in relative_pcap_paths:
        fixture_path = FIXTURE_DIR / "pcap" / rel_path
        pcap_name = Path(rel_path).name
        (input_dir / pcap_name).write_bytes(fixture_path.read_bytes())
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
            "TARGET_LOGS": target_logs,
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


def run_full_pipeline_main(
    monkeypatch,
    tmp_path,
    relative_pcap_paths,
    *,
    target_logs,
    network_conf=None,
):
    input_dir, log_output_root, csv_output_root, settings_path = prepare_pipeline_fixture(
        tmp_path,
        relative_pcap_paths,
        target_logs=target_logs,
        network_conf=network_conf,
    )
    patch_settings(monkeypatch, settings_path)
    pcap_extractor.main()
    csv_extractor.main()
    return input_dir, log_output_root, csv_output_root


def assert_runtime_csv_contract(rows):
    assert rows, "Expected at least one CSV row"
    for row in rows:
        for column in REQUIRED_RUNTIME_COLUMNS:
            assert column in row, f"Missing required runtime column: {column}"

        assert row["conn_state"], "conn_state should not be empty"
        int(float(row["label"]))
        for column in NUMERIC_OR_EMPTY_COLUMNS:
            value = row[column]
            if value != "":
                float(value)

        assert row["local_orig"].strip().lower() in {"true", "false", "1", "0", "t", "f", "yes", "no", "y", "n"}
        assert row["local_resp"].strip().lower() in {"true", "false", "1", "0", "t", "f", "yes", "no", "y", "n"}


def assert_csv_matches_expected_subset(
    actual_path,
    expected_path,
    *,
    expect_runtime_contract=False,
):
    actual_header, actual_rows = read_csv_content(actual_path)
    expected_header, expected_rows = read_csv_content(expected_path)

    for column in expected_header:
        assert column in actual_header, f"Missing expected CSV column: {column}"
    assert len(actual_rows) == len(expected_rows)
    if actual_rows:
        assert [row["daytime"] for row in actual_rows] == sorted(row["daytime"] for row in actual_rows)
    if expect_runtime_contract:
        assert_runtime_csv_contract(actual_rows)

    for actual_row, expected_row in zip(actual_rows, expected_rows):
        for key in expected_header:
            assert actual_row[key] == expected_row[key], (
                f"Unexpected value for {key}: {actual_row[key]} != {expected_row[key]}"
            )
