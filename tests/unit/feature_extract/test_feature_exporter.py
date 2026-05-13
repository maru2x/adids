import csv
import json
from pathlib import Path

import pytest

from src.util.FeatureExtract.Zeek import feature_exporter as exporter


def read_csv_rows(path):
    with path.open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def make_conn_record(
    *,
    ts,
    orig_h="192.168.0.10",
    resp_h="8.8.8.8",
    conn_state="SF",
    duration=1.0,
    proto="tcp",
    orig_p=40000,
    resp_p=2222,
    local_orig=True,
    local_resp=False,
):
    return {
        "ts": ts,
        "proto": proto,
        "id.orig_h": orig_h,
        "id.orig_p": orig_p,
        "id.resp_h": resp_h,
        "id.resp_p": resp_p,
        "conn_state": conn_state,
        "duration": duration,
        "orig_bytes": 1,
        "resp_bytes": 2,
        "orig_pkts": 3,
        "resp_pkts": 4,
        "orig_ip_bytes": 29,
        "resp_ip_bytes": 41,
        "missed_bytes": 0,
        "local_orig": local_orig,
        "local_resp": local_resp,
    }


def test_build_runtime_compatible_row_with_network_label_and_required_columns():
    record = make_conn_record(ts=1640995200, orig_h="10.0.0.10", resp_h="8.8.8.8")
    network_conf = {
        "BENIGN": ["192.168.0.0/24"],
        "MALICIOUS": ["10.0.0.0/24"],
        "EXCEPTION": [],
    }

    row, reason = exporter.build_runtime_compatible_row_with_reason(
        record,
        network_conf=network_conf,
    )

    assert reason is None
    assert row is not None
    assert row["daytime"] == "2022-01-01 09:00:01"
    assert row["label"] == 1
    assert row["conn_state"] == "SF"
    assert row["local_orig"] is True
    assert row["local_resp"] is False


def test_build_runtime_compatible_row_rejects_unlabeled_network_rows():
    record = make_conn_record(ts=1640995200, orig_h="8.8.8.8", resp_h="1.1.1.1")
    network_conf = {
        "BENIGN": ["192.168.0.0/24"],
        "MALICIOUS": ["10.0.0.0/24"],
        "EXCEPTION": [],
    }

    row, reason = exporter.build_runtime_compatible_row_with_reason(
        record,
        network_conf=network_conf,
    )

    assert row is None
    assert reason == "unlabeled"


def test_live_export_appends_only_new_records_and_rotates_chunks(tmp_path):
    input_dir = Path(tmp_path) / "live_input"
    input_dir.mkdir()
    output_dir = Path(tmp_path) / "csv_leaf"
    state_path = Path(tmp_path) / "state.json"
    conn_log_path = input_dir / "conn.log"

    first_record = make_conn_record(ts=1640995200)
    second_record = make_conn_record(ts=1640995210, orig_p=40001)
    third_record = make_conn_record(ts=1640995220, orig_p=40002)
    conn_log_path.write_text(
        "\n".join(json.dumps(record) for record in [first_record, second_record]) + "\n",
        encoding="utf-8",
    )

    stats = exporter.export_live_conn_log_with_state(
        input_dir,
        output_dir,
        fixed_label=1,
        output_chunk_size=2,
        state_path=state_path,
    )

    assert stats.scanned_record_count == 2
    assert stats.emitted_row_count == 2
    first_chunk = output_dir / "00000_20220101090001.csv"
    assert first_chunk.is_file()
    first_rows = read_csv_rows(first_chunk)
    assert [row["label"] for row in first_rows] == ["1", "1"]

    with conn_log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(third_record) + "\n")

    stats = exporter.export_live_conn_log_with_state(
        input_dir,
        output_dir,
        fixed_label=1,
        output_chunk_size=2,
        state_path=state_path,
    )

    assert stats.scanned_record_count == 1
    assert stats.emitted_row_count == 1
    assert read_csv_rows(first_chunk) == first_rows
    second_chunk = output_dir / "00001_20220101090021.csv"
    assert second_chunk.is_file()
    assert len(read_csv_rows(second_chunk)) == 1


def test_live_export_refuses_existing_leaf_without_state_file(tmp_path):
    input_dir = Path(tmp_path) / "live_input"
    input_dir.mkdir()
    conn_log_path = input_dir / "conn.log"
    conn_log_path.write_text(json.dumps(make_conn_record(ts=1640995200)) + "\n", encoding="utf-8")
    output_dir = Path(tmp_path) / "csv_leaf"
    output_dir.mkdir()
    (output_dir / "00000_20220101090001.csv").write_text("daytime,label\n", encoding="utf-8")

    with pytest.raises(SystemExit, match="without a state file"):
        exporter.export_live_conn_log_with_state(
            input_dir,
            output_dir,
            fixed_label=1,
            output_chunk_size=2,
            state_path=Path(tmp_path) / "missing_state.json",
        )
