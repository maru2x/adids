import csv
from pathlib import Path

from src.util.FeatureExtract.Zeek.log_to_csv_extractor import convert_log_dir


def read_csv_rows(path):
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def network_conf():
    return {
        "BENIGN": ["192.168.0.0/24"],
        "MALICIOUS": [],
        "EXCEPTION": [],
    }


ROOT_DIR = Path(__file__).resolve().parents[3]
FIXTURE_DIR = ROOT_DIR / "tests" / "fixtures" / "zeek_logs"


def test_convert_log_dir_sorts_by_flow_end_time(tmp_path):
    root = Path(tmp_path)
    log_dir = root / "logs" / "20220101000000"
    log_dir.mkdir(parents=True)
    destination = root / "csv" / "20220101000000.csv"

    (log_dir / "conn.log").write_text(
        (FIXTURE_DIR / "unordered_conn.log").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    convert_log_dir(log_dir, destination, network_conf(), ["conn.log"])

    rows = read_csv_rows(destination)
    assert [row["daytime"] for row in rows] == [
        "2022-01-01 09:00:06",
        "2022-01-01 09:10:00",
    ]


def test_convert_log_dir_keeps_zero_duration_as_valid_end_time(tmp_path):
    root = Path(tmp_path)
    log_dir = root / "logs" / "20220101000000"
    log_dir.mkdir(parents=True)
    destination = root / "csv" / "20220101000000.csv"

    (log_dir / "conn.log").write_text(
        (FIXTURE_DIR / "zero_duration_conn.log").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    convert_log_dir(log_dir, destination, network_conf(), ["conn.log"])

    rows = read_csv_rows(destination)
    assert rows[0]["daytime"] == "2022-01-01 09:00:00"

def test_convert_log_dir_falls_back_to_start_time_when_duration_is_missing_or_invalid(tmp_path):
    root = Path(tmp_path)
    log_dir = root / "logs" / "20220101000000"
    log_dir.mkdir(parents=True)
    destination = root / "csv" / "20220101000000.csv"

    (log_dir / "conn.log").write_text(
        (FIXTURE_DIR / "duration_fallback_conn.log").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    convert_log_dir(log_dir, destination, network_conf(), ["conn.log"])

    rows = read_csv_rows(destination)
    assert [row["daytime"] for row in rows] == [
        "2022-01-01 09:00:00",
        "2022-01-01 09:00:10",
    ]
