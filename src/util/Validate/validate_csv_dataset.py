#!/usr/bin/env python3
"""Validate a leaf CSV dataset directory before passing it to runtime."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from unicodedata import east_asian_width


DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"
SCRIPT_DIR = Path(__file__).resolve().parent
SETTINGS_PATH = SCRIPT_DIR / "settings.json"
DEFAULT_RUNTIME_SETTINGS_PATH = SCRIPT_DIR.parents[1] / "main" / "settings.json"
DEFAULT_ZEEK_SETTINGS_PATH = SCRIPT_DIR.parent / "FeatureExtract" / "Zeek" / "settings.json"
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
CHECK_DEFINITIONS = (
    ("input_dir", "入力ディレクトリ"),
    ("directory_layout", "直下の構成"),
    ("csv_files", "CSV ファイル検出"),
    ("required_columns", "必須列の存在"),
    ("header", "ヘッダ"),
    ("row_structure", "空行 / 列数不一致"),
    ("daytime_format", "daytime 形式"),
    ("time_order", "時系列順序"),
    ("label_value", "label の値"),
    ("zeek_types", "Zeek 数値列 / 真偽値列"),
)
DIRECTION_OUTBOUND = "外向き"
DIRECTION_INBOUND = "内向き"
DIRECTION_OTHER = "その他/不明"
LEVEL_LABELS = {
    "ERROR": "エラー",
    "WARNING": "警告",
}


@dataclass
class Problem:
    level: str
    message: str
    file_name: str | None = None
    row_number: int | None = None


@dataclass
class CheckState:
    label: str
    status: str = "未実行"
    messages: list[str] = field(default_factory=list)

    def mark_ok(self) -> None:
        if self.status == "未実行":
            self.status = "OK"

    def add_problem(self, level: str, message: str) -> None:
        self.messages.append(message)
        if level == "ERROR":
            self.status = "NG"
            return
        if level == "WARNING" and self.status != "NG":
            self.status = "警告"


@dataclass
class SchemaInfo:
    schema: str
    label_column: str
    label_features: tuple[str, ...]
    vector_features: tuple[str, ...]
    required_columns: tuple[str, ...]
    empty_allowed_columns: set[str]


@dataclass
class DatasetSummary:
    rows_per_file: list[int] = field(default_factory=list)
    first_daytime: datetime | None = None
    last_daytime: datetime | None = None
    label_counts: Counter[int] = field(default_factory=Counter)
    direction_counts: Counter[str] = field(default_factory=Counter)
    feature_value_counts: dict[str, Counter[str]] = field(default_factory=dict)
    missing_counts: dict[str, int] = field(default_factory=dict)
    column_order: list[str] = field(default_factory=list)

    def register_column(self, column: str) -> None:
        if column in self.missing_counts:
            return
        self.missing_counts[column] = 0
        self.column_order.append(column)

    def add_daytime(self, current_daytime: datetime) -> None:
        if self.first_daytime is None or current_daytime < self.first_daytime:
            self.first_daytime = current_daytime
        if self.last_daytime is None or current_daytime > self.last_daytime:
            self.last_daytime = current_daytime


@dataclass
class ValidationReport:
    dataset_dir: Path
    schema: str
    file_count: int = 0
    row_count: int = 0
    problems: list[Problem] = field(default_factory=list)
    checks: dict[str, CheckState] = field(init=False)
    summary: DatasetSummary = field(default_factory=DatasetSummary)
    schema_info: SchemaInfo | None = None

    def __post_init__(self) -> None:
        self.checks = {key: CheckState(label) for key, label in CHECK_DEFINITIONS}

    @property
    def ok(self) -> bool:
        return not any(problem.level == "ERROR" for problem in self.problems)

    def add_problem(self, level, message, *, check_key=None, file_name=None, row_number=None):
        self.problems.append(
            Problem(
                level=level,
                message=message,
                file_name=file_name,
                row_number=row_number,
            )
        )
        if check_key is not None:
            self.checks[check_key].add_problem(level, message)

    def mark_check_ok(self, check_key: str) -> None:
        self.checks[check_key].mark_ok()


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
    parser.add_argument(
        "--zeek-settings",
        help="Path to src/util/FeatureExtract/Zeek/settings.json used for direction summary.",
    )
    return parser.parse_args()


def load_settings(settings_path: Path = SETTINGS_PATH) -> dict:
    with settings_path.open("r", encoding="utf-8") as f:
        settings = json.load(f)
    return settings["CsvDatasetValidator"]


def load_runtime_settings(runtime_settings_path: str | Path) -> dict:
    with Path(runtime_settings_path).open("r", encoding="utf-8") as f:
        return json.load(f)


def load_zeek_network_conf(zeek_settings_path: str | Path) -> dict | None:
    settings_path = Path(zeek_settings_path)
    if not settings_path.is_file():
        return None
    with settings_path.open("r", encoding="utf-8") as f:
        settings = json.load(f)
    section = settings.get("LogToCsv", {})
    if not isinstance(section, dict):
        return None
    network_key = section.get("NETWORK_KEY")
    if not isinstance(network_key, str) or not network_key.strip():
        return None
    network_map = settings.get("NetworkAddress")
    if not isinstance(network_map, dict):
        return None
    network_conf = network_map.get(network_key.strip())
    if not isinstance(network_conf, dict):
        return None
    return network_conf


def ordered_unique(values):
    seen = set()
    result = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return tuple(result)


def resolve_schema_info(schema: str, runtime_settings_path: str | Path | None = None) -> SchemaInfo:
    if schema == "legacy":
        if runtime_settings_path is None:
            return SchemaInfo(
                schema="legacy",
                label_column="label",
                label_features=tuple(),
                vector_features=tuple(),
                required_columns=LEGACY_REQUIRED_COLUMNS,
                empty_allowed_columns=LEGACY_EMPTY_ALLOWED_COLUMNS,
            )
        runtime_settings = load_runtime_settings(runtime_settings_path)
        feature_schema = runtime_settings.get("FeatureSchema", {})
        label_column = feature_schema.get("LABEL_COLUMN", "label")
        legacy_features = tuple(feature_schema.get("LEGACY_FEATURES", []))
        required = ordered_unique(["daytime", label_column, *legacy_features])
        return SchemaInfo(
            schema="legacy",
            label_column=label_column,
            label_features=tuple(),
            vector_features=legacy_features,
            required_columns=required,
            empty_allowed_columns=LEGACY_EMPTY_ALLOWED_COLUMNS,
        )

    if runtime_settings_path is None:
        raise ValueError("runtime_settings_path is required for zeek schema validation.")
    runtime_settings = load_runtime_settings(runtime_settings_path)
    feature_schema = runtime_settings.get("FeatureSchema", {})
    label_column = feature_schema.get("LABEL_COLUMN", "label")
    label_features = tuple(feature_schema.get("LABEL_FEATURES", []))
    vector_features = tuple(feature_schema.get("VECTOR_FEATURES", []))
    required = ordered_unique(["daytime", label_column, *label_features, *vector_features])
    return SchemaInfo(
        schema="zeek",
        label_column=label_column,
        label_features=label_features,
        vector_features=vector_features,
        required_columns=required,
        empty_allowed_columns=ZEEK_EMPTY_ALLOWED_COLUMNS,
    )


def collect_directory_entries(dataset_dir: Path, report: ValidationReport) -> list[Path]:
    if not dataset_dir.exists():
        report.add_problem(
            "ERROR",
            f"対象ディレクトリが存在しません: {dataset_dir}",
            check_key="input_dir",
        )
        return []
    if not dataset_dir.is_dir():
        report.add_problem(
            "ERROR",
            f"対象パスがディレクトリではありません: {dataset_dir}",
            check_key="input_dir",
        )
        return []
    report.mark_check_ok("input_dir")

    entries = sorted(dataset_dir.iterdir())
    csv_files: list[Path] = []
    for entry in entries:
        if entry.is_dir():
            report.add_problem(
                "ERROR",
                f"サブディレクトリは置けません: {entry.name}",
                check_key="directory_layout",
            )
            continue
        if entry.suffix.lower() != ".csv":
            report.add_problem(
                "ERROR",
                f"CSV 以外のファイルは置けません: {entry.name}",
                check_key="directory_layout",
            )
            continue
        csv_files.append(entry)

    if report.checks["directory_layout"].status == "未実行":
        report.mark_check_ok("directory_layout")

    if not csv_files:
        report.add_problem(
            "ERROR",
            f"CSV ファイルが 1 件も見つかりません: {dataset_dir}",
            check_key="csv_files",
        )
        return []

    report.mark_check_ok("csv_files")
    return csv_files


def parse_daytime(value: str, report: ValidationReport, file_name: str, row_number: int) -> datetime | None:
    try:
        return datetime.strptime(value, DATETIME_FORMAT)
    except ValueError:
        report.add_problem(
            "ERROR",
            f"daytime の形式が不正です: {value} (期待形式: {DATETIME_FORMAT})",
            check_key="daytime_format",
            file_name=file_name,
            row_number=row_number,
        )
        return None


def validate_label(value: str, report: ValidationReport, file_name: str, row_number: int) -> int | None:
    try:
        numeric = int(float(value))
    except ValueError:
        report.add_problem(
            "ERROR",
            f"label が数値として読めません: {value}",
            check_key="label_value",
            file_name=file_name,
            row_number=row_number,
        )
        return None
    if numeric not in (0, 1):
        report.add_problem(
            "ERROR",
            f"label は 0 または 1 である必要があります: {value}",
            check_key="label_value",
            file_name=file_name,
            row_number=row_number,
        )
        return None
    return numeric


def parse_bool_like(value: str | None) -> bool | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    if normalized in TRUE_VALUES:
        return True
    if normalized in FALSE_VALUES:
        return False
    return None


def validate_bool(value: str, column: str, report: ValidationReport, file_name: str, row_number: int) -> None:
    if parse_bool_like(value) is not None:
        return
    report.add_problem(
        "ERROR",
        f"{column} が真偽値として読めません: {value}",
        check_key="zeek_types",
        file_name=file_name,
        row_number=row_number,
    )


def validate_numeric(value: str, column: str, report: ValidationReport, file_name: str, row_number: int) -> None:
    try:
        float(value)
    except ValueError:
        report.add_problem(
            "ERROR",
            f"{column} が数値として読めません: {value}",
            check_key="zeek_types",
            file_name=file_name,
            row_number=row_number,
        )


def ip_in_any(ip_str: str | None, networks: list[str] | tuple[str, ...] | None) -> bool:
    if not ip_str or not networks:
        return False
    try:
        import ipaddress

        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return False
    for net in networks:
        try:
            if ip in ipaddress.ip_network(net, strict=False):
                return True
        except ValueError:
            continue
    return False


def classify_direction(row: dict, network_conf: dict | None) -> str:
    if network_conf is not None:
        src = row.get("id.orig_h")
        dst = row.get("id.resp_h")
        malicious = network_conf.get("MALICIOUS", [])
        benign = network_conf.get("BENIGN", [])
        if ip_in_any(src, malicious):
            return DIRECTION_OUTBOUND
        if ip_in_any(dst, malicious):
            return DIRECTION_INBOUND
        if ip_in_any(src, benign) and not ip_in_any(dst, benign):
            return DIRECTION_OUTBOUND
        if ip_in_any(dst, benign) and not ip_in_any(src, benign):
            return DIRECTION_INBOUND
    local_orig = parse_bool_like(row.get("local_orig"))
    local_resp = parse_bool_like(row.get("local_resp"))
    if local_orig is True and local_resp is False:
        return DIRECTION_OUTBOUND
    if local_orig is False and local_resp is True:
        return DIRECTION_INBOUND
    return DIRECTION_OTHER


def update_summary_for_row(
    report: ValidationReport,
    row: dict,
    header: list[str],
    current_daytime: datetime | None,
    label_numeric: int | None,
    network_conf: dict | None,
) -> None:
    summary = report.summary
    for column in header:
        value = row.get(column)
        if value in ("", None):
            summary.missing_counts[column] += 1
    if current_daytime is not None:
        summary.add_daytime(current_daytime)
    if label_numeric is not None:
        summary.label_counts[label_numeric] += 1

    direction = classify_direction(row, network_conf)
    summary.direction_counts[direction] += 1

    if report.schema_info is None:
        return
    for feature in report.schema_info.label_features:
        if feature not in row:
            continue
        counter = summary.feature_value_counts.setdefault(feature, Counter())
        feature_value = row.get(feature, "")
        counter[feature_value if feature_value != "" else "(空欄)"] += 1


def validate_file_rows(
    csv_file: Path,
    report: ValidationReport,
    schema_info: SchemaInfo,
    network_conf: dict | None,
    previous_global_daytime: datetime | None,
    expected_header: list[str] | None,
) -> tuple[datetime | None, list[str] | None]:
    file_name = csv_file.name
    previous_file_daytime: datetime | None = None

    with csv_file.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        header = reader.fieldnames
        if not header:
            report.add_problem(
                "ERROR",
                "CSV ヘッダがありません",
                check_key="header",
                file_name=file_name,
            )
            return previous_global_daytime, expected_header

        for column in header:
            report.summary.register_column(column)

        duplicate_headers = sorted({column for column in header if header.count(column) > 1})
        if duplicate_headers:
            report.add_problem(
                "ERROR",
                f"ヘッダ列名が重複しています: {', '.join(duplicate_headers)}",
                check_key="header",
                file_name=file_name,
            )

        missing_columns = [column for column in schema_info.required_columns if column not in header]
        if missing_columns:
            report.add_problem(
                "ERROR",
                f"必須列が不足しています: {', '.join(missing_columns)}",
                check_key="required_columns",
                file_name=file_name,
            )
            return previous_global_daytime, expected_header

        if expected_header is None:
            expected_header = list(header)
        elif list(header) != expected_header:
            report.add_problem(
                "WARNING",
                "ヘッダが先頭 CSV と一致していません",
                check_key="header",
                file_name=file_name,
            )

        data_row_count = 0
        for row_index, row in enumerate(reader, start=2):
            if all((value is None or value == "") for value in row.values()):
                report.add_problem(
                    "ERROR",
                    "空行は許可されていません",
                    check_key="row_structure",
                    file_name=file_name,
                    row_number=row_index,
                )
                continue
            if None in row:
                report.add_problem(
                    "ERROR",
                    "列数がヘッダと一致していません",
                    check_key="row_structure",
                    file_name=file_name,
                    row_number=row_index,
                )
                continue

            data_row_count += 1
            report.row_count += 1

            for column in schema_info.required_columns:
                value = row.get(column, "")
                if value == "" and column not in schema_info.empty_allowed_columns:
                    report.add_problem(
                        "ERROR",
                        f"必須列が空欄です: {column}",
                        check_key="required_columns",
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
                    "同一 CSV 内で daytime が逆行しています",
                    check_key="time_order",
                    file_name=file_name,
                    row_number=row_index,
                )
            if current_daytime is not None and previous_global_daytime is not None and current_daytime < previous_global_daytime:
                report.add_problem(
                    "ERROR",
                    "CSV ファイル間で daytime が逆行しています",
                    check_key="time_order",
                    file_name=file_name,
                    row_number=row_index,
                )

            if current_daytime is not None:
                previous_file_daytime = current_daytime
                previous_global_daytime = current_daytime

            label_numeric = None
            label_value = row.get(schema_info.label_column, "")
            if label_value != "":
                label_numeric = validate_label(label_value, report, file_name, row_index)

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

            update_summary_for_row(report, row, header, current_daytime, label_numeric, network_conf)

        if data_row_count == 0:
            report.add_problem(
                "ERROR",
                "ヘッダだけでデータ行がありません",
                check_key="row_structure",
                file_name=file_name,
            )
        else:
            report.summary.rows_per_file.append(data_row_count)

    return previous_global_daytime, expected_header


def finalize_check_statuses(report: ValidationReport) -> None:
    if report.checks["input_dir"].status == "未実行" and report.dataset_dir.is_dir():
        report.mark_check_ok("input_dir")
    if report.file_count > 0 and report.checks["directory_layout"].status == "未実行":
        report.mark_check_ok("directory_layout")
    if report.file_count > 0 and report.checks["csv_files"].status == "未実行":
        report.mark_check_ok("csv_files")
    if report.file_count > 0 and report.checks["required_columns"].status == "未実行":
        report.mark_check_ok("required_columns")
    if report.file_count > 0 and report.checks["header"].status == "未実行":
        report.mark_check_ok("header")
    if report.row_count > 0 and report.checks["row_structure"].status == "未実行":
        report.mark_check_ok("row_structure")
    if report.row_count > 0 and report.checks["daytime_format"].status == "未実行":
        report.mark_check_ok("daytime_format")
    if report.row_count > 0 and report.checks["time_order"].status == "未実行":
        report.mark_check_ok("time_order")
    if report.row_count > 0 and report.checks["label_value"].status == "未実行":
        report.mark_check_ok("label_value")
    if report.schema == "zeek" and report.row_count > 0 and report.checks["zeek_types"].status == "未実行":
        report.mark_check_ok("zeek_types")


def validate_csv_dataset(
    dataset_dir: str | Path,
    schema: str = "zeek",
    runtime_settings_path: str | Path | None = DEFAULT_RUNTIME_SETTINGS_PATH,
    *,
    network_conf: dict | None = None,
    zeek_settings_path: str | Path | None = DEFAULT_ZEEK_SETTINGS_PATH,
) -> ValidationReport:
    dataset_path = Path(dataset_dir)
    report = ValidationReport(dataset_dir=dataset_path, schema=schema)
    schema_info = resolve_schema_info(schema, runtime_settings_path)
    report.schema_info = schema_info

    if network_conf is None and schema == "zeek" and zeek_settings_path is not None:
        network_conf = load_zeek_network_conf(zeek_settings_path)

    csv_files = collect_directory_entries(dataset_path, report)
    if not csv_files:
        finalize_check_statuses(report)
        return report

    report.file_count = len(csv_files)
    previous_global_daytime: datetime | None = None
    expected_header: list[str] | None = None
    for csv_file in csv_files:
        previous_global_daytime, expected_header = validate_file_rows(
            csv_file,
            report,
            schema_info,
            network_conf,
            previous_global_daytime,
            expected_header,
        )
    finalize_check_statuses(report)
    return report


def display_width(text: str) -> int:
    width = 0
    for ch in text:
        width += 2 if east_asian_width(ch) in {"F", "W", "A"} else 1
    return width


def pad_display(text: str, width: int) -> str:
    return text + (" " * max(width - display_width(text), 0))


def format_int(value: int) -> str:
    return f"{value:,}"


def format_ratio(count: int, total: int) -> str:
    if total <= 0:
        return f"0.0% ({format_int(count)})"
    ratio = (count / total) * 100
    return f"{ratio:4.1f}% ({format_int(count)})"


def format_datetime(value: datetime | None) -> str:
    if value is None:
        return "-"
    return value.strftime(DATETIME_FORMAT)


def format_duration(delta: timedelta | None) -> str:
    if delta is None:
        return "-"
    total_seconds = int(delta.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    parts = []
    if hours:
        parts.append(f"{hours}時間")
    if minutes or hours:
        parts.append(f"{minutes}分")
    parts.append(f"{seconds}秒")
    return "".join(parts)


def build_pair_rows(entries: list[tuple[str, str]]) -> list[tuple[str, str, str, str]]:
    rows: list[tuple[str, str, str, str]] = []
    for index in range(0, len(entries), 2):
        left_label, left_value = entries[index]
        if index + 1 < len(entries):
            right_label, right_value = entries[index + 1]
        else:
            right_label, right_value = "", ""
        rows.append((left_label, left_value, right_label, right_value))
    return rows


def render_pair_table(entries: list[tuple[str, str]]) -> list[str]:
    if not entries:
        return []
    rows = build_pair_rows(entries)
    label_width = max(display_width(cell) for row in rows for cell in (row[0], row[2]))
    value_width = max(display_width(cell) for row in rows for cell in (row[1], row[3]))
    border = (
        "+"
        + "-" * (label_width + 2)
        + "+"
        + "-" * (value_width + 2)
        + "+"
        + "-" * (label_width + 2)
        + "+"
        + "-" * (value_width + 2)
        + "+"
    )
    rendered = [border]
    for left_label, left_value, right_label, right_value in rows:
        rendered.append(
            "| "
            + pad_display(left_label, label_width)
            + " | "
            + pad_display(left_value, value_width)
            + " | "
            + pad_display(right_label, label_width)
            + " | "
            + pad_display(right_value, value_width)
            + " |"
        )
    rendered.append(border)
    return rendered


def build_runtime_check_lines(report: ValidationReport) -> list[str]:
    error_count = sum(1 for problem in report.problems if problem.level == "ERROR")
    warning_count = sum(1 for problem in report.problems if problem.level == "WARNING")
    lines = [
        "[runtime契約チェック]",
        f"対象ディレクトリ: {report.dataset_dir}",
        f"スキーマ: {report.schema}",
        f"総合判定: {'合格' if report.ok else '不合格'}",
        f"エラー: {error_count} 件",
        f"警告: {warning_count} 件",
    ]
    for check_key, _label in CHECK_DEFINITIONS:
        state = report.checks[check_key]
        lines.append(f"- {state.label}: {state.status}")
    return lines


def build_basic_summary_tables(report: ValidationReport) -> list[list[str]]:
    summary = report.summary
    if report.row_count == 0:
        return []
    average_rows = round(sum(summary.rows_per_file) / len(summary.rows_per_file)) if summary.rows_per_file else 0
    observation = None
    if summary.first_daytime is not None and summary.last_daytime is not None:
        observation = summary.last_daytime - summary.first_daytime
    first_table = render_pair_table(
        [
            ("総フロー数", format_int(report.row_count)),
            ("CSV数", format_int(report.file_count)),
            ("先頭 daytime", format_datetime(summary.first_daytime)),
            ("末尾 daytime", format_datetime(summary.last_daytime)),
        ]
    )
    second_table = render_pair_table(
        [
            ("1ファイル最小行数", format_int(min(summary.rows_per_file) if summary.rows_per_file else 0)),
            ("1ファイル平均行数", format_int(average_rows)),
            ("1ファイル最大行数", format_int(max(summary.rows_per_file) if summary.rows_per_file else 0)),
            ("観測期間", format_duration(observation)),
        ]
    )
    return [first_table, second_table]


def build_label_direction_table(report: ValidationReport) -> list[str]:
    summary = report.summary
    total = report.row_count
    left_entries = [
        ("label=0", format_ratio(summary.label_counts.get(0, 0), total)),
        ("label=1", format_ratio(summary.label_counts.get(1, 0), total)),
    ]
    right_entries = [
        (DIRECTION_OUTBOUND, format_ratio(summary.direction_counts.get(DIRECTION_OUTBOUND, 0), total)),
        (DIRECTION_INBOUND, format_ratio(summary.direction_counts.get(DIRECTION_INBOUND, 0), total)),
        (DIRECTION_OTHER, format_ratio(summary.direction_counts.get(DIRECTION_OTHER, 0), total)),
    ]
    rows: list[tuple[str, str, str, str]] = []
    row_count = max(len(left_entries), len(right_entries))
    for index in range(row_count):
        left_label, left_value = left_entries[index] if index < len(left_entries) else ("", "")
        right_label, right_value = right_entries[index] if index < len(right_entries) else ("", "")
        rows.append((left_label, left_value, right_label, right_value))

    label_width = max(display_width(cell) for row in rows for cell in (row[0], row[2]))
    value_width = max(display_width(cell) for row in rows for cell in (row[1], row[3]))
    border = (
        "+"
        + "-" * (label_width + 2)
        + "+"
        + "-" * (value_width + 2)
        + "+"
        + "-" * (label_width + 2)
        + "+"
        + "-" * (value_width + 2)
        + "+"
    )
    rendered = [border]
    for left_label, left_value, right_label, right_value in rows:
        rendered.append(
            "| "
            + pad_display(left_label, label_width)
            + " | "
            + pad_display(left_value, value_width)
            + " | "
            + pad_display(right_label, label_width)
            + " | "
            + pad_display(right_value, value_width)
            + " |"
        )
    rendered.append(border)
    return rendered


def build_feature_distribution_tables(report: ValidationReport) -> list[tuple[str, list[str]]]:
    if report.schema_info is None:
        return []
    tables: list[tuple[str, list[str]]] = []
    for feature in report.schema_info.label_features:
        counter = report.summary.feature_value_counts.get(feature)
        if not counter:
            continue
        entries = [
            (f"{feature}={value}", format_ratio(count, report.row_count))
            for value, count in sorted(counter.items(), key=lambda item: (-item[1], item[0]))
        ]
        tables.append((f"{feature} の内訳", render_pair_table(entries)))
    return tables


def build_missing_table(report: ValidationReport) -> list[str]:
    entries = [
        (f"{column} 欠損", format_ratio(report.summary.missing_counts.get(column, 0), report.row_count))
        for column in report.summary.column_order
    ]
    return render_pair_table(entries)


def build_problem_lines(report: ValidationReport) -> list[str]:
    if not report.problems:
        return []
    lines = ["[詳細]"]
    for problem in report.problems:
        location = []
        if problem.file_name is not None:
            location.append(problem.file_name)
        if problem.row_number is not None:
            location.append(f"row {problem.row_number}")
        location_text = f" [{', '.join(location)}]" if location else ""
        level_text = LEVEL_LABELS.get(problem.level, problem.level)
        lines.append(f"- {level_text}: {problem.message}{location_text}")
    return lines


def build_report_text(report: ValidationReport) -> str:
    lines = build_runtime_check_lines(report)
    if report.row_count > 0:
        lines.append("")
        lines.append("[データサマリ]")
        for table in build_basic_summary_tables(report):
            lines.extend(table)
            lines.append("")
        lines.extend(build_label_direction_table(report))
        feature_tables = build_feature_distribution_tables(report)
        for title, table in feature_tables:
            lines.append("")
            lines.append(f"[{title}]")
            lines.extend(table)
        missing_table = build_missing_table(report)
        if missing_table:
            lines.append("")
            lines.append("[欠損値]")
            lines.extend(missing_table)

    problem_lines = build_problem_lines(report)
    if problem_lines:
        lines.append("")
        lines.extend(problem_lines)
    return "\n".join(lines)


def print_report(report: ValidationReport) -> None:
    print(build_report_text(report))


def main() -> int:
    args = parse_args()
    settings = load_settings()
    dataset_dir = args.dataset_dir or settings["DATASET_DIR_PATH"]
    schema = args.schema or settings["SCHEMA"]
    runtime_settings_path = args.runtime_settings or settings.get(
        "RUNTIME_SETTINGS_PATH",
        str(DEFAULT_RUNTIME_SETTINGS_PATH),
    )
    zeek_settings_path = args.zeek_settings or settings.get(
        "ZEEK_SETTINGS_PATH",
        str(DEFAULT_ZEEK_SETTINGS_PATH),
    )
    report = validate_csv_dataset(
        dataset_dir,
        schema=schema,
        runtime_settings_path=runtime_settings_path,
        zeek_settings_path=zeek_settings_path,
    )
    print_report(report)
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
