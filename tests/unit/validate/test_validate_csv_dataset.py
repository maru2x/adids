import csv
from pathlib import Path

from src.util.Validate.validate_csv_dataset import build_report_text, validate_csv_dataset


def write_csv(path, rows, fieldnames):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_validate_csv_dataset_accepts_valid_zeek_leaf_dir(tmp_path):
    dataset_dir = Path(tmp_path) / "sample"
    fieldnames = [
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
    write_csv(
        dataset_dir / "00000.csv",
        [
            {
                "daytime": "2022-01-01 09:00:00",
                "label": "0",
                "conn_state": "SF",
                "duration": "1",
                "orig_bytes": "10",
                "resp_bytes": "20",
                "orig_pkts": "1",
                "resp_pkts": "1",
                "orig_ip_bytes": "38",
                "resp_ip_bytes": "38",
                "missed_bytes": "0",
                "local_orig": "true",
                "local_resp": "false",
            }
        ],
        fieldnames,
    )

    report = validate_csv_dataset(dataset_dir, schema="zeek")

    assert report.ok
    assert report.file_count == 1
    assert report.row_count == 1


def test_validate_csv_dataset_rejects_daytime_regression_across_files(tmp_path):
    dataset_dir = Path(tmp_path) / "sample"
    fieldnames = [
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
    write_csv(
        dataset_dir / "00000.csv",
        [
            {
                "daytime": "2022-01-01 09:00:05",
                "label": "0",
                "conn_state": "SF",
                "duration": "1",
                "orig_bytes": "10",
                "resp_bytes": "20",
                "orig_pkts": "1",
                "resp_pkts": "1",
                "orig_ip_bytes": "38",
                "resp_ip_bytes": "38",
                "missed_bytes": "0",
                "local_orig": "true",
                "local_resp": "false",
            }
        ],
        fieldnames,
    )
    write_csv(
        dataset_dir / "00001.csv",
        [
            {
                "daytime": "2022-01-01 09:00:04",
                "label": "1",
                "conn_state": "S0",
                "duration": "1",
                "orig_bytes": "11",
                "resp_bytes": "21",
                "orig_pkts": "1",
                "resp_pkts": "1",
                "orig_ip_bytes": "39",
                "resp_ip_bytes": "39",
                "missed_bytes": "0",
                "local_orig": "true",
                "local_resp": "false",
            }
        ],
        fieldnames,
    )

    report = validate_csv_dataset(dataset_dir, schema="zeek")

    assert not report.ok
    assert any("CSV ファイル間で daytime が逆行しています" in problem.message for problem in report.problems)


def test_validate_csv_dataset_rejects_non_csv_entries(tmp_path):
    dataset_dir = Path(tmp_path) / "sample"
    dataset_dir.mkdir()
    (dataset_dir / "note.txt").write_text("x", encoding="utf-8")

    report = validate_csv_dataset(dataset_dir, schema="zeek")

    assert not report.ok
    assert any("CSV 以外のファイルは置けません" in problem.message for problem in report.problems)


def test_build_report_text_includes_japanese_runtime_checks_and_summary_tables(tmp_path):
    dataset_dir = Path(tmp_path) / "sample"
    fieldnames = [
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
        "id.orig_h",
        "id.resp_h",
    ]
    write_csv(
        dataset_dir / "00000.csv",
        [
            {
                "daytime": "2022-01-01 09:00:00",
                "label": "0",
                "conn_state": "SF",
                "duration": "",
                "orig_bytes": "10",
                "resp_bytes": "20",
                "orig_pkts": "1",
                "resp_pkts": "1",
                "orig_ip_bytes": "38",
                "resp_ip_bytes": "38",
                "missed_bytes": "0",
                "local_orig": "true",
                "local_resp": "false",
                "id.orig_h": "192.168.0.10",
                "id.resp_h": "8.8.8.8",
            }
        ],
        fieldnames,
    )

    report = validate_csv_dataset(
        dataset_dir,
        schema="zeek",
        network_conf={
            "BENIGN": ["192.168.0.0/24"],
            "MALICIOUS": [],
            "EXCEPTION": [],
        },
    )
    output = build_report_text(report)

    assert report.ok
    assert "[runtime契約チェック]" in output
    assert "総合判定: 合格" in output
    assert "conn_state=SF" in output
    assert "外向き" in output
    assert "duration 欠損" in output
