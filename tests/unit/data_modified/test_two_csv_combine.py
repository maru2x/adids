import csv
from pathlib import Path

import pytest

from src.util.DataModified.two_csv_combine import combine_csv_directories


def write_csv(path, rows, fieldnames=("daytime", "label", "conn_state")):
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def read_rows(path):
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def flatten_output(output_dir):
    rows = []
    for csv_path in sorted(output_dir.glob("*.csv")):
        rows.extend(read_rows(csv_path))
    return rows


def test_combine_keeps_buffer_when_one_side_ends(tmp_path):
    root = Path(tmp_path)
    input_a = root / "a"
    input_b = root / "b"
    output_dir = root / "out"
    input_a.mkdir()
    input_b.mkdir()

    write_csv(
        input_a / "000.csv",
        [
            {"daytime": "2022-01-01 00:00:00", "label": "0", "conn_state": "SF"},
            {"daytime": "2022-01-01 00:00:02", "label": "0", "conn_state": "SF"},
        ],
    )
    write_csv(
        input_b / "000.csv",
        [
            {"daytime": "2022-01-01 00:00:01", "label": "1", "conn_state": "S0"},
            {"daytime": "2022-01-01 00:00:03", "label": "1", "conn_state": "S0"},
            {"daytime": "2022-01-01 00:00:04", "label": "1", "conn_state": "S0"},
        ],
    )

    combine_csv_directories(str(input_a), str(input_b), str(output_dir), chunk_size=10)

    rows = flatten_output(output_dir)
    assert [row["daytime"] for row in rows] == [
        "2022-01-01 00:00:00",
        "2022-01-01 00:00:01",
        "2022-01-01 00:00:02",
        "2022-01-01 00:00:03",
        "2022-01-01 00:00:04",
    ]


def test_combine_splits_exactly_at_chunk_size(tmp_path):
    root = Path(tmp_path)
    input_a = root / "a"
    input_b = root / "b"
    output_dir = root / "out"
    input_a.mkdir()
    input_b.mkdir()

    write_csv(
        input_a / "000.csv",
        [
            {"daytime": "2022-01-01 00:00:00", "label": "0", "conn_state": "SF"},
            {"daytime": "2022-01-01 00:00:02", "label": "0", "conn_state": "SF"},
        ],
    )
    write_csv(
        input_b / "000.csv",
        [
            {"daytime": "2022-01-01 00:00:01", "label": "1", "conn_state": "S0"},
            {"daytime": "2022-01-01 00:00:03", "label": "1", "conn_state": "S0"},
        ],
    )

    combine_csv_directories(str(input_a), str(input_b), str(output_dir), chunk_size=2)

    output_files = sorted(output_dir.glob("*.csv"))
    assert len(output_files) == 2
    assert len(read_rows(output_files[0])) == 2
    assert len(read_rows(output_files[1])) == 2


def test_combine_rejects_header_mismatch(tmp_path):
    root = Path(tmp_path)
    input_a = root / "a"
    input_b = root / "b"
    output_dir = root / "out"
    input_a.mkdir()
    input_b.mkdir()

    write_csv(
        input_a / "000.csv",
        [{"daytime": "2022-01-01 00:00:00", "label": "0", "conn_state": "SF"}],
    )
    write_csv(
        input_b / "000.csv",
        [{"daytime": "2022-01-01 00:00:01", "label": "1", "label2": "x"}],
        fieldnames=("daytime", "label", "label2"),
    )

    with pytest.raises(ValueError, match="CSV header mismatch"):
        combine_csv_directories(str(input_a), str(input_b), str(output_dir), chunk_size=10)


def test_combine_handles_multiple_files_per_side(tmp_path):
    root = Path(tmp_path)
    input_a = root / "a"
    input_b = root / "b"
    output_dir = root / "out"
    input_a.mkdir()
    input_b.mkdir()

    write_csv(
        input_a / "000.csv",
        [{"daytime": "2022-01-01 00:00:00", "label": "0", "conn_state": "SF"}],
    )
    write_csv(
        input_a / "001.csv",
        [{"daytime": "2022-01-01 00:00:03", "label": "0", "conn_state": "SF"}],
    )
    write_csv(
        input_b / "000.csv",
        [{"daytime": "2022-01-01 00:00:01", "label": "1", "conn_state": "S0"}],
    )
    write_csv(
        input_b / "001.csv",
        [{"daytime": "2022-01-01 00:00:02", "label": "1", "conn_state": "S0"}],
    )

    combine_csv_directories(str(input_a), str(input_b), str(output_dir), chunk_size=10)

    rows = flatten_output(output_dir)
    assert [row["daytime"] for row in rows] == [
        "2022-01-01 00:00:00",
        "2022-01-01 00:00:01",
        "2022-01-01 00:00:02",
        "2022-01-01 00:00:03",
    ]


def test_combine_skips_header_only_csv_before_data(tmp_path):
    root = Path(tmp_path)
    input_a = root / "a"
    input_b = root / "b"
    output_dir = root / "out"
    input_a.mkdir()
    input_b.mkdir()

    write_csv(input_a / "000.csv", [])
    write_csv(
        input_a / "001.csv",
        [{"daytime": "2022-01-01 00:00:00", "label": "0", "conn_state": "SF"}],
    )
    write_csv(
        input_b / "000.csv",
        [{"daytime": "2022-01-01 00:00:01", "label": "1", "conn_state": "S0"}],
    )

    combine_csv_directories(str(input_a), str(input_b), str(output_dir), chunk_size=10)

    rows = flatten_output(output_dir)
    assert [row["daytime"] for row in rows] == ["2022-01-01 00:00:00", "2022-01-01 00:00:01"]


def test_combine_rejects_non_positive_chunk_size(tmp_path):
    root = Path(tmp_path)
    input_a = root / "a"
    input_b = root / "b"
    output_dir = root / "out"
    input_a.mkdir()
    input_b.mkdir()

    write_csv(
        input_a / "000.csv",
        [{"daytime": "2022-01-01 00:00:00", "label": "0", "conn_state": "SF"}],
    )
    write_csv(
        input_b / "000.csv",
        [{"daytime": "2022-01-01 00:00:01", "label": "1", "conn_state": "S0"}],
    )

    with pytest.raises(ValueError, match="CHUNK_SIZE must be a positive integer"):
        combine_csv_directories(str(input_a), str(input_b), str(output_dir), chunk_size=0)


def test_combine_rejects_non_empty_output_dir(tmp_path):
    root = Path(tmp_path)
    input_a = root / "a"
    input_b = root / "b"
    output_dir = root / "out"
    input_a.mkdir()
    input_b.mkdir()
    output_dir.mkdir()
    (output_dir / "stale.csv").write_text("stale", encoding="utf-8")

    write_csv(
        input_a / "000.csv",
        [{"daytime": "2022-01-01 00:00:00", "label": "0", "conn_state": "SF"}],
    )
    write_csv(
        input_b / "000.csv",
        [{"daytime": "2022-01-01 00:00:01", "label": "1", "conn_state": "S0"}],
    )

    with pytest.raises(ValueError, match="OUTPUT_DIR must be empty"):
        combine_csv_directories(str(input_a), str(input_b), str(output_dir), chunk_size=10)


def test_combine_rejects_invalid_daytime_value(tmp_path):
    root = Path(tmp_path)
    input_a = root / "a"
    input_b = root / "b"
    output_dir = root / "out"
    input_a.mkdir()
    input_b.mkdir()

    write_csv(
        input_a / "000.csv",
        [{"daytime": "bad-time", "label": "0", "conn_state": "SF"}],
    )
    write_csv(
        input_b / "000.csv",
        [{"daytime": "2022-01-01 00:00:01", "label": "1", "conn_state": "S0"}],
    )

    with pytest.raises(ValueError, match="Invalid daytime value"):
        combine_csv_directories(str(input_a), str(input_b), str(output_dir), chunk_size=10)


def test_combine_rejects_when_input_has_no_data_rows(tmp_path):
    root = Path(tmp_path)
    input_a = root / "a"
    input_b = root / "b"
    output_dir = root / "out"
    input_a.mkdir()
    input_b.mkdir()

    write_csv(input_a / "000.csv", [])
    write_csv(input_b / "000.csv", [])

    with pytest.raises(ValueError, match="at least one data row"):
        combine_csv_directories(str(input_a), str(input_b), str(output_dir), chunk_size=10)
