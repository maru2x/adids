import csv
from pathlib import Path

from src.main.Live.csv_cursor import LiveCsvCursor


def write_csv(path: Path, rows):
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["daytime", "label", "id.resp_p", "proto", "conn_state"],
        )
        writer.writeheader()
        writer.writerows(rows)


def test_live_csv_cursor_end_mode_skips_existing_rows_then_returns_appended_rows(tmp_path):
    output_dir = tmp_path / "live_csv"
    output_dir.mkdir()
    csv_path = output_dir / "00000_20220101090000.csv"
    write_csv(
        csv_path,
        [
            {
                "daytime": "2022-01-01 09:00:00",
                "label": "0",
                "id.resp_p": "2223",
                "proto": "tcp",
                "conn_state": "OTH",
            }
        ],
    )
    cursor = LiveCsvCursor(output_dir, tmp_path / "cursor_state.json", initial_position="end")

    assert cursor.collect_new_rows() == []

    write_csv(
        csv_path,
        [
            {
                "daytime": "2022-01-01 09:00:00",
                "label": "0",
                "id.resp_p": "2223",
                "proto": "tcp",
                "conn_state": "OTH",
            },
            {
                "daytime": "2022-01-01 09:00:01",
                "label": "0",
                "id.resp_p": "2223",
                "proto": "tcp",
                "conn_state": "OTH",
            },
        ],
    )

    rows = cursor.collect_new_rows()
    assert len(rows) == 1
    assert rows[0]["daytime"] == "2022-01-01 09:00:01"
