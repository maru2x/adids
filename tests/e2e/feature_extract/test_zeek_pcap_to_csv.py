import csv
import shutil
from pathlib import Path

import pytest

from src.util.FeatureExtract.Zeek.log_to_csv_extractor import convert_log_dir
from src.util.FeatureExtract.Zeek.pcap_to_log_extractor import run_zeek


ROOT_DIR = Path(__file__).resolve().parents[3]
FIXTURE_DIR = ROOT_DIR / "tests" / "fixtures"
CASES = (
    ("zeek_udp_roundtrip.pcap", "zeek_udp_roundtrip.csv"),
    ("zeek_udp_interleaved.pcap", "zeek_udp_interleaved.csv"),
    ("zeek_udp_one_way.pcap", "zeek_udp_one_way.csv"),
)
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


def read_csv_rows(path):
    with path.open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def network_conf():
    return {
        "BENIGN": ["192.168.0.0/24"],
        "MALICIOUS": [],
        "EXCEPTION": [],
    }


@pytest.mark.e2e
@pytest.mark.skipif(shutil.which("zeek") is None, reason="zeek command is required for e2e feature extraction tests")
@pytest.mark.parametrize(("pcap_name", "expected_name"), CASES)
def test_pcap_fixture_produces_expected_csv_subset(tmp_path, pcap_name, expected_name):
    pcap_fixture = FIXTURE_DIR / "pcap" / pcap_name
    expected_csv = FIXTURE_DIR / "expected_csv" / expected_name
    assert pcap_fixture.is_file(), f"Missing fixture: {pcap_fixture}"
    assert expected_csv.is_file(), f"Missing expected CSV: {expected_csv}"

    root = Path(tmp_path)
    log_dir = root / "logs" / "20220101000000"
    log_dir.mkdir(parents=True)

    run_zeek(pcap_fixture, log_dir)

    conn_log = log_dir / "conn.log"
    assert conn_log.is_file(), "Zeek did not produce conn.log"

    destination = root / "csv" / "20220101000000.csv"
    convert_log_dir(log_dir, destination, network_conf(), ["conn.log"])

    actual_rows = read_csv_rows(destination)
    expected_rows = read_csv_rows(expected_csv)

    assert len(actual_rows) == len(expected_rows)
    assert [row["daytime"] for row in actual_rows] == sorted(row["daytime"] for row in actual_rows)
    assert_runtime_csv_contract(actual_rows)

    for actual_row, expected_row in zip(actual_rows, expected_rows):
        for key, expected_value in expected_row.items():
            assert actual_row[key] == expected_value, (
                f"Unexpected value for {key}: {actual_row[key]} != {expected_value}"
            )


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
