import csv
import json
from datetime import datetime
from pathlib import Path


SETTINGS_PATH = Path(__file__).with_name("settings.json")
DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"


def load_settings(settings_path=SETTINGS_PATH):
    with Path(settings_path).open("r", encoding="utf-8") as f:
        settings = json.load(f)
    return settings["Combiner"]


def list_csv_files(input_dir):
    csv_files = sorted(
        path for path in Path(input_dir).iterdir() if path.is_file() and path.suffix == ".csv"
    )
    if not csv_files:
        raise ValueError(f"No CSV files found in input directory: {input_dir}")
    return csv_files


def parse_daytime(value, source_name):
    try:
        return datetime.strptime(value, DATETIME_FORMAT)
    except ValueError as exc:
        raise ValueError(
            f"Invalid daytime value '{value}' in {source_name}. Expected format: {DATETIME_FORMAT}"
        ) from exc


def validate_output_dir(output_dir):
    output_path = Path(output_dir)
    if output_path.exists():
        if any(output_path.iterdir()):
            raise ValueError(f"OUTPUT_DIR must be empty before running: {output_dir}")
    else:
        output_path.mkdir(parents=True, exist_ok=True)
    return output_path


class CsvSequence:
    def __init__(self, csv_files):
        self.csv_files = iter(csv_files)
        self.expected_header = None
        self.current_file = None
        self.current_path = None
        self.reader = None
        self.current_row = None
        self.current_dt = None
        self.header = None
        self.ended = False
        try:
            self.advance()
        except Exception:
            self.close()
            raise

    def close(self):
        if self.current_file is not None:
            self.current_file.close()
            self.current_file = None
            self.reader = None
            self.current_path = None

    def _open_next_file(self):
        self.close()
        while True:
            try:
                next_path = next(self.csv_files)
            except StopIteration:
                self.ended = True
                self.header = self.expected_header
                return False

            current_file = next_path.open("r", encoding="utf-8", newline="")
            reader = csv.DictReader(current_file)
            fieldnames = reader.fieldnames
            if not fieldnames or "daytime" not in fieldnames:
                current_file.close()
                raise ValueError(f"Missing 'daytime' column in {next_path}")
            if self.expected_header is None:
                self.expected_header = list(fieldnames)
            elif list(fieldnames) != self.expected_header:
                current_file.close()
                raise ValueError(
                    f"CSV header mismatch in {next_path}. Expected {self.expected_header}, got {list(fieldnames)}"
                )

            self.current_file = current_file
            self.current_path = next_path
            self.reader = reader
            self.header = self.expected_header
            return True

    def advance(self):
        while True:
            # Header-only CSVs are skipped so downstream merge logic always sees a real row or EOF.
            if self.reader is None and not self._open_next_file():
                self.current_row = None
                self.current_dt = None
                return
            try:
                row = next(self.reader)
            except StopIteration:
                self.reader = None
                continue

            self.current_row = row
            self.current_dt = parse_daytime(row["daytime"], self.current_path.name)
            self.ended = False
            return

    def pop_current(self):
        if self.ended or self.current_row is None:
            raise StopIteration("No current row available.")
        row = dict(self.current_row)
        self.advance()
        return row


def output_filename(output_index, first_daytime):
    return f"{output_index:05d}_{first_daytime.strftime('%Y%m%d%H%M')}.csv"


def flush_rows(output_dir, fieldnames, rows, output_index):
    if not rows:
        return output_index
    first_daytime = parse_daytime(rows[0]["daytime"], "combined output")
    output_path = Path(output_dir) / output_filename(output_index, first_daytime)
    with output_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    rows.clear()
    return output_index + 1


def combine_csv_directories(input_dir_a, input_dir_b, output_dir, chunk_size):
    if chunk_size <= 0:
        raise ValueError(f"CHUNK_SIZE must be a positive integer: {chunk_size}")

    csv_files_a = list_csv_files(input_dir_a)
    csv_files_b = list_csv_files(input_dir_b)
    output_path = validate_output_dir(output_dir)

    seq_a = None
    seq_b = None
    try:
        seq_a = CsvSequence(csv_files_a)
        seq_b = CsvSequence(csv_files_b)

        if seq_a.header is None or seq_b.header is None:
            raise ValueError("Input directories must contain at least one data row.")
        if seq_a.current_row is None or seq_b.current_row is None:
            raise ValueError("Input directories must contain at least one data row.")
        if seq_a.header != seq_b.header:
            raise ValueError(
                f"CSV header mismatch between directories. A={seq_a.header}, B={seq_b.header}"
            )

        combined_rows = []
        output_index = 0

        while not (seq_a.ended and seq_b.ended):
            # Keep a single pending buffer and always consume the earlier row first.
            # If one side has ended, continue draining the other side without resetting the buffer.
            if seq_a.ended:
                combined_rows.append(seq_b.pop_current())
            elif seq_b.ended:
                combined_rows.append(seq_a.pop_current())
            elif seq_a.current_dt <= seq_b.current_dt:
                combined_rows.append(seq_a.pop_current())
            else:
                combined_rows.append(seq_b.pop_current())

            if len(combined_rows) >= chunk_size:
                output_index = flush_rows(output_path, seq_a.header, combined_rows, output_index)

        flush_rows(output_path, seq_a.header, combined_rows, output_index)
    finally:
        if seq_a is not None:
            seq_a.close()
        if seq_b is not None:
            seq_b.close()


def main():
    settings = load_settings()
    combine_csv_directories(
        input_dir_a=settings["INPUT_DIR_A"],
        input_dir_b=settings["INPUT_DIR_B"],
        output_dir=settings["OUTPUT_DIR"],
        chunk_size=settings["CHUNK_SIZE"],
    )
    print("csv combine complete")


if __name__ == "__main__":
    main()
