#!/usr/bin/env python3
"""Validate a leaf CSV dataset directory before passing it to runtime."""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"
SCRIPT_DIR = Path(__file__).resolve().parent
SETTINGS_PATH = SCRIPT_DIR / "settings.json"
DEFAULT_RUNTIME_SETTINGS_PATH = SCRIPT_DIR.parents[1] / "main" / "settings.json"
ZEEK_EMPTY_ALLOWED_COLUMNS = {
    "duration",
    "orig_bytes",
    "resp_bytes",
    "orig_pkts",
    "resp_pkts",
    "orig_ip_bytes",
    "resp_ip_bytes",
    "missed_bytes",
}
LEGACY_REQUIRED_COLUMNS = (
    "ex_address",
    "in_address",
    "daytime",
    "rcv_packet_count",
    "snd_packet_count",
    "tcp_count",
    "udp_count",
    "most_port",
    "port_count",
    "rcv_max_interval",
    "rcv_min_interval",
    "rcv_max_length",
    "rcv_min_length",
    "snd_max_interval",
    "snd_min_interval",
    "snd_max_length",
    "snd_min_length",
    "label",
)
LEGACY_EMPTY_ALLOWED_COLUMNS: set[str] = set()
TRUE_VALUES = {"1", "true", "t", "yes", "y"}
FALSE_VALUES = {"0", "false", "f", "no", "n"}


@dataclass
class Problem:
    level: str
    message: str
    file_name: str | None = None
    row_number: int | None = None


@dataclass
class ValidationReport:
    dataset_dir: Path
    schema: str
    file_count: int = 0
    row_count: int = 0
    problems: list[Problem] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems

    def add_problem(self, level, message, *, file_name=None, row_number=None):
        self.problems.append(
            Problem(
                level=level,
                message=message,
                file_name=file_name,
                row_number=row_number,
            )
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate that a leaf CSV dataset directory satisfies the runtime contract."
    )
    parser.add_argument("dataset_dir", nargs="?", help="Leaf CSV directory to validate")
    parser.add_argument(
        "--schema",
        choices=("zeek", "legacy"),
        help="Expected runtime schema. If omitted, use Validate/settings.json.",
    )
    parser.add_argument(
        "--runtime-settings",
        help="Path to src/main/settings.json used to resolve required columns for the selected schema.",
    )
    return parser.parse_args()


def load_settings(settings_path: Path = SETTINGS_PATH) -> dict:
    with settings_path.open("r", encoding="utf-8") as f:
        settings = json.load(f)
    return settings["CsvDatasetValidator"]


def load_runtime_settings(runtime_settings_path: str | Path) -> dict:
    with Path(runtime_settings_path).open("r", encoding="utf-8") as f:
        return json.load(f)


def ordered_unique(values):
    seen = set()
    result = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return tuple(result)


def required_columns_for(schema: str, runtime_settings_path: str | Path | None = None) -> tuple[tuple[str, ...], set[str]]:
    if schema == "legacy":
        if runtime_settings_path is None:
            return LEGACY_REQUIRED_COLUMNS, LEGACY_EMPTY_ALLOWED_COLUMNS
        runtime_settings = load_runtime_settings(runtime_settings_path)
        feature_schema = runtime_settings.get("FeatureSchema", {})
        label_column = feature_schema.get("LABEL_COLUMN", "label")
        legacy_features = feature_schema.get("LEGACY_FEATURES", [])
        required = ordered_unique(["daytime", label_column, *legacy_features])
        return required, LEGACY_EMPTY_ALLOWED_COLUMNS

    if runtime_settings_path is None:
        raise ValueError("runtime_settings_path is required for zeek schema validation.")
    runtime_settings = load_runtime_settings(runtime_settings_path)
    feature_schema = runtime_settings.get("FeatureSchema", {})
    label_column = feature_schema.get("LABEL_COLUMN", "label")
    label_features = feature_schema.get("LABEL_FEATURES", [])
    vector_features = feature_schema.get("VECTOR_FEATURES", [])
    required = ordered_unique(["daytime", label_column, *label_features, *vector_features])
    return required, ZEEK_EMPTY_ALLOWED_COLUMNS


def collect_directory_entries(dataset_dir: Path, report: ValidationReport) -> list[Path]:
    if not dataset_dir.exists():
        report.add_problem("ERROR", f"Dataset directory not found: {dataset_dir}")
        return []
    if not dataset_dir.is_dir():
        report.add_problem("ERROR", f"Dataset path is not a directory: {dataset_dir}")
        return []

    entries = sorted(dataset_dir.iterdir())
    csv_files: list[Path] = []
    for entry in entries:
        if entry.is_dir():
            report.add_problem("ERROR", f"Nested directory is not allowed: {entry.name}")
            continue
        if entry.suffix.lower() != ".csv":
            report.add_problem("ERROR", f"Non-CSV entry is not allowed: {entry.name}")
            continue
        csv_files.append(entry)

    if not csv_files:
        report.add_problem("ERROR", f"No CSV files found in dataset directory: {dataset_dir}")
    return csv_files


def parse_daytime(value: str, report: ValidationReport, file_name: str, row_number: int) -> datetime | None:
    try:
        return datetime.strptime(value, DATETIME_FORMAT)
    except ValueError:
        report.add_problem(
            "ERROR",
            f"Invalid daytime format '{value}'. Expected {DATETIME_FORMAT}",
            file_name=file_name,
            row_number=row_number,
        )
        return None


def validate_label(value: str, report: ValidationReport, file_name: str, row_number: int) -> None:
    try:
        numeric = int(float(value))
    except ValueError:
        report.add_problem(
            "ERROR",
            f"label is not numeric: {value}",
            file_name=file_name,
            row_number=row_number,
        )
        return
    if numeric not in (0, 1):
        report.add_problem(
            "ERROR",
            f"label must be binary 0/1: {value}",
            file_name=file_name,
            row_number=row_number,
        )


def validate_bool(value: str, column: str, report: ValidationReport, file_name: str, row_number: int) -> None:
    normalized = value.strip().lower()
    if normalized not in TRUE_VALUES and normalized not in FALSE_VALUES:
        report.add_problem(
            "ERROR",
            f"{column} is not a recognized boolean value: {value}",
            file_name=file_name,
            row_number=row_number,
        )


def validate_numeric(value: str, column: str, report: ValidationReport, file_name: str, row_number: int) -> None:
    try:
        float(value)
    except ValueError:
        report.add_problem(
            "ERROR",
            f"{column} is not numeric: {value}",
            file_name=file_name,
            row_number=row_number,
        )


def validate_file_rows(
    csv_file: Path,
    report: ValidationReport,
    required_columns: tuple[str, ...],
    empty_allowed_columns: set[str],
    previous_global_daytime: datetime | None,
    expected_header: list[str] | None,
) -> tuple[datetime | None, list[str] | None]:
    file_name = csv_file.name
    previous_file_daytime: datetime | None = None

    with csv_file.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        header = reader.fieldnames
        if not header:
            report.add_problem("ERROR", "CSV header is missing", file_name=file_name)
            return previous_global_daytime, expected_header

        duplicate_headers = sorted({column for column in header if header.count(column) > 1})
        if duplicate_headers:
            report.add_problem(
                "ERROR",
                f"Duplicate header columns are not allowed: {', '.join(duplicate_headers)}",
                file_name=file_name,
            )

        missing_columns = [column for column in required_columns if column not in header]
        if missing_columns:
            report.add_problem(
                "ERROR",
                f"Missing required columns: {', '.join(missing_columns)}",
                file_name=file_name,
            )
            return previous_global_daytime, expected_header

        if expected_header is None:
            expected_header = list(header)
        elif list(header) != expected_header:
            report.add_problem(
                "WARNING",
                "CSV header does not match the first CSV file",
                file_name=file_name,
            )

        data_row_count = 0
        for row_index, row in enumerate(reader, start=2):
            if all((value is None or value == "") for value in row.values()):
                report.add_problem("ERROR", "Empty row is not allowed", file_name=file_name, row_number=row_index)
                continue
            if None in row:
                report.add_problem(
                    "ERROR",
                    "Row column count does not match header column count",
                    file_name=file_name,
                    row_number=row_index,
                )
                continue
            data_row_count += 1
            report.row_count += 1

            for column in required_columns:
                value = row.get(column, "")
                if value == "" and column not in empty_allowed_columns:
                    report.add_problem(
                        "ERROR",
                        f"Required value is empty: {column}",
                        file_name=file_name,
                        row_number=row_index,
                    )

            daytime_value = row.get("daytime", "")
            current_daytime = None
            if daytime_value != "":
                current_daytime = parse_daytime(daytime_value, report, file_name, row_index)

            if current_daytime is not None and previous_file_daytime is not None and current_daytime < previous_file_daytime:
                report.add_problem(
                    "ERROR",
                    "daytime is decreasing inside the CSV file",
                    file_name=file_name,
                    row_number=row_index,
                )
            if current_daytime is not None and previous_global_daytime is not None and current_daytime < previous_global_daytime:
                report.add_problem(
                    "ERROR",
                    "daytime is decreasing across CSV files in directory order",
                    file_name=file_name,
                    row_number=row_index,
                )

            if current_daytime is not None:
                previous_file_daytime = current_daytime
                previous_global_daytime = current_daytime

            label_value = row.get("label", "")
            if label_value != "":
                validate_label(label_value, report, file_name, row_index)

            if report.schema == "zeek":
                for column in (
                    "duration",
                    "orig_bytes",
                    "resp_bytes",
                    "orig_pkts",
                    "resp_pkts",
                    "orig_ip_bytes",
                    "resp_ip_bytes",
                    "missed_bytes",
                ):
                    value = row.get(column, "")
                    if value != "":
                        validate_numeric(value, column, report, file_name, row_index)
                for column in ("local_orig", "local_resp"):
                    value = row.get(column, "")
                    if value != "":
                        validate_bool(value, column, report, file_name, row_index)

        if data_row_count == 0:
            report.add_problem("ERROR", "CSV contains header only and no data rows", file_name=file_name)

    return previous_global_daytime, expected_header


def validate_csv_dataset(
    dataset_dir: str | Path,
    schema: str = "zeek",
    runtime_settings_path: str | Path | None = DEFAULT_RUNTIME_SETTINGS_PATH,
) -> ValidationReport:
    dataset_path = Path(dataset_dir)
    report = ValidationReport(dataset_dir=dataset_path, schema=schema)
    csv_files = collect_directory_entries(dataset_path, report)
    if not csv_files:
        return report

    report.file_count = len(csv_files)
    required_columns, empty_allowed_columns = required_columns_for(schema, runtime_settings_path)
    previous_global_daytime: datetime | None = None
    expected_header: list[str] | None = None
    for csv_file in csv_files:
        previous_global_daytime, expected_header = validate_file_rows(
            csv_file,
            report,
            required_columns,
            empty_allowed_columns,
            previous_global_daytime,
            expected_header,
        )
    return report


def print_report(report: ValidationReport) -> None:
    error_count = sum(1 for problem in report.problems if problem.level == "ERROR")
    warning_count = sum(1 for problem in report.problems if problem.level == "WARNING")
    status = "OK" if error_count == 0 else "NG"
    print(f"[{status}] schema={report.schema} dataset_dir={report.dataset_dir}")
    print(
        f"files={report.file_count} rows={report.row_count} "
        f"errors={error_count} warnings={warning_count}"
    )
    if error_count == 0:
        print("dataset contract looks valid")
        if warning_count == 0:
            return

    for problem in report.problems:
        location = []
        if problem.file_name is not None:
            location.append(problem.file_name)
        if problem.row_number is not None:
            location.append(f"row {problem.row_number}")
        location_text = ""
        if location:
            location_text = " [" + ", ".join(location) + "]"
        print(f"{problem.level}: {problem.message}{location_text}")


def main() -> int:
    args = parse_args()
    settings = load_settings()
    dataset_dir = args.dataset_dir or settings["DATASET_DIR_PATH"]
    schema = args.schema or settings["SCHEMA"]
    runtime_settings_path = args.runtime_settings or settings.get(
        "RUNTIME_SETTINGS_PATH",
        str(DEFAULT_RUNTIME_SETTINGS_PATH),
    )
    report = validate_csv_dataset(
        dataset_dir,
        schema=schema,
        runtime_settings_path=runtime_settings_path,
    )
    print_report(report)
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
