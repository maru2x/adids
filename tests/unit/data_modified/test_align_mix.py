import csv
from pathlib import Path

import pytest

from src.util.DataModified.align_mix import align_and_mix_directories


def write_csv(path, rows, fieldnames=("daytime", "label", "conn_state")):
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def flatten_output(output_dir):
    rows = []
    for csv_path in sorted(Path(output_dir).glob("*.csv")):
        with csv_path.open("r", encoding="utf-8", newline="") as f:
            rows.extend(list(csv.DictReader(f)))
    return rows


def test_align_and_mix_aligns_b_to_a_then_combines(tmp_path):
    root = Path(tmp_path)
    input_a = root / "a"
    input_b = root / "b"
    shifted = root / "shifted"
    output_dir = root / "out"
    input_a.mkdir()
    input_b.mkdir()

    write_csv(
        input_a / "000.csv",
        [
            {"daytime": "2022-01-01 09:00:00", "label": "0", "conn_state": "SF"},
            {"daytime": "2022-01-01 09:00:05", "label": "0", "conn_state": "SF"},
        ],
    )
    write_csv(
        input_b / "000.csv",
        [
            {"daytime": "2022-01-02 12:00:00", "label": "1", "conn_state": "S0"},
            {"daytime": "2022-01-02 12:00:03", "label": "1", "conn_state": "S0"},
        ],
    )

    align_and_mix_directories(
        str(input_a),
        str(input_b),
        "A",
        str(shifted),
        str(output_dir),
        chunk_size=10,
    )

    assert [row["daytime"] for row in flatten_output(output_dir)] == [
        "2022-01-01 09:00:00",
        "2022-01-01 09:00:00",
        "2022-01-01 09:00:03",
        "2022-01-01 09:00:05",
    ]


def test_align_and_mix_rejects_path_reuse(tmp_path):
    root = Path(tmp_path)
    input_a = root / "a"
    input_b = root / "b"
    input_a.mkdir()
    input_b.mkdir()

    with pytest.raises(ValueError, match="distinct"):
        align_and_mix_directories(
            str(input_a),
            str(input_b),
            "A",
            str(input_b),
            str(root / "out"),
            chunk_size=10,
        )
