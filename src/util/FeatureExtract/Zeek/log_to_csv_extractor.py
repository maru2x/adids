#!/usr/bin/env python3
"""Convert configured Zeek JSON logs to CSV using the current batch layout."""

from __future__ import annotations

import argparse
import csv
import heapq
import ipaddress
import json
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, Iterator, List, Sequence


JST = timezone(timedelta(hours=9))
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[3]
SETTINGS_PATH = SCRIPT_DIR / "settings.json"
DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"
DEFAULT_OUTPUT_CHUNK_SIZE = 3000
DEFAULT_RUN_ROW_LIMIT = 100000
DEFAULT_MERGE_FAN_IN = 256
DEFAULT_AUTO_VALIDATE_CONN_OUTPUT = True


def current_settings_path(settings_path: Path | None = None) -> Path:
    return SETTINGS_PATH if settings_path is None else settings_path

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from src.util.Validate import validate_csv_dataset as csv_validator


@dataclass
class RunCreationStats:
    matched_log_dir_count: int = 0
    scanned_record_count: int = 0
    skipped_invalid_ts_count: int = 0
    excluded_record_count: int = 0
    unlabeled_record_count: int = 0
    emitted_row_count: int = 0
    run_count: int = 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Convert configured Zeek JSON log directories into CSV using "
            "the current batch layout."
        )
    )
    parser.add_argument(
        "--settings",
        dest="settings_path",
        help="利用する settings.json の path を明示指定する",
    )
    return parser.parse_args()


def resolve_settings_path(settings_path_arg: str | None) -> Path:
    if not settings_path_arg:
        return SETTINGS_PATH
    raw_path = Path(settings_path_arg).expanduser()
    if raw_path.is_absolute():
        return raw_path.resolve()
    return (PROJECT_ROOT / raw_path).resolve()


def load_settings(settings_path: Path | None = None) -> dict:
    settings_path = current_settings_path(settings_path)
    if not settings_path.is_file():
        raise SystemExit(f"Settings file not found: {settings_path}")
    with settings_path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def resolve_repo_path(
    path_str: str,
    *,
    field_name: str,
    settings_path: Path | None = None,
) -> Path:
    settings_path = current_settings_path(settings_path)
    if not path_str:
        raise SystemExit(f"{field_name} is required in {settings_path}")
    raw_path = Path(path_str).expanduser()
    if raw_path.is_absolute():
        return raw_path.resolve()
    return (PROJECT_ROOT / raw_path).resolve()


def normalize_target_logs(
    target_logs: object,
    settings_path: Path | None = None,
) -> list[str]:
    settings_path = current_settings_path(settings_path)
    if not isinstance(target_logs, list) or not target_logs:
        raise SystemExit(f"LogToCsv.TARGET_LOGS must be a non-empty array in {settings_path}")
    normalized: list[str] = []
    seen: set[str] = set()
    for value in target_logs:
        if not isinstance(value, str) or not value.strip():
            raise SystemExit(f"LogToCsv.TARGET_LOGS must contain non-empty strings in {settings_path}")
        name = value.strip()
        if name not in seen:
            seen.add(name)
            normalized.append(name)
    return normalized


def resolve_network_config(
    settings: dict,
    network_key: str,
    settings_path: Path | None = None,
) -> dict:
    settings_path = current_settings_path(settings_path)
    network_map = settings.get("NetworkAddress")
    if not isinstance(network_map, dict):
        raise SystemExit(f"NetworkAddress section not found in {settings_path}")
    network_conf = network_map.get(network_key)
    if not isinstance(network_conf, dict):
        raise SystemExit(f"NetworkAddress '{network_key}' not found in {settings_path}")
    return network_conf


def resolve_output_chunk_size(value: object, settings_path: Path | None = None) -> int:
    settings_path = current_settings_path(settings_path)
    if value is None:
        return DEFAULT_OUTPUT_CHUNK_SIZE
    if isinstance(value, bool):
        raise SystemExit(f"LogToCsv.OUTPUT_CHUNK_SIZE must be a positive integer in {settings_path}")
    try:
        chunk_size = int(value)
    except (TypeError, ValueError) as exc:
        raise SystemExit(
            f"LogToCsv.OUTPUT_CHUNK_SIZE must be a positive integer in {settings_path}"
        ) from exc
    if chunk_size <= 0:
        raise SystemExit(f"LogToCsv.OUTPUT_CHUNK_SIZE must be a positive integer in {settings_path}")
    return chunk_size


def resolve_positive_int(
    value: object,
    *,
    field_name: str,
    default: int,
    settings_path: Path | None = None,
) -> int:
    settings_path = current_settings_path(settings_path)
    if value is None:
        return default
    if isinstance(value, bool):
        raise SystemExit(f"{field_name} must be a positive integer in {settings_path}")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise SystemExit(f"{field_name} must be a positive integer in {settings_path}") from exc
    if parsed <= 0:
        raise SystemExit(f"{field_name} must be a positive integer in {settings_path}")
    return parsed


def resolve_bool(
    value: object,
    *,
    field_name: str,
    default: bool,
    settings_path: Path | None = None,
) -> bool:
    settings_path = current_settings_path(settings_path)
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    raise SystemExit(f"{field_name} must be a boolean in {settings_path}")


def resolve_config(
    settings: dict,
    settings_path: Path | None = None,
) -> tuple[Path, Path, list[str], dict, int, int, int, bool]:
    settings_path = current_settings_path(settings_path)
    section = settings.get("LogToCsv")
    if not isinstance(section, dict):
        raise SystemExit(f"LogToCsv section not found in {settings_path}")
    input_path = resolve_repo_path(
        section.get("INPUT_DIR_PATH", ""),
        field_name="LogToCsv.INPUT_DIR_PATH",
        settings_path=settings_path,
    )
    output_root = resolve_repo_path(
        section.get("OUTPUT_ROOT_DIR_PATH", ""),
        field_name="LogToCsv.OUTPUT_ROOT_DIR_PATH",
        settings_path=settings_path,
    )
    target_logs = normalize_target_logs(section.get("TARGET_LOGS"), settings_path)
    network_key = section.get("NETWORK_KEY")
    if not isinstance(network_key, str) or not network_key.strip():
        raise SystemExit(f"LogToCsv.NETWORK_KEY is required in {settings_path}")
    network_conf = resolve_network_config(settings, network_key.strip(), settings_path)
    output_chunk_size = resolve_output_chunk_size(section.get("OUTPUT_CHUNK_SIZE"), settings_path)
    run_row_limit = resolve_positive_int(
        section.get("RUN_ROW_LIMIT"),
        field_name="LogToCsv.RUN_ROW_LIMIT",
        default=DEFAULT_RUN_ROW_LIMIT,
        settings_path=settings_path,
    )
    merge_fan_in = resolve_positive_int(
        section.get("MERGE_FAN_IN"),
        field_name="LogToCsv.MERGE_FAN_IN",
        default=DEFAULT_MERGE_FAN_IN,
        settings_path=settings_path,
    )
    auto_validate_conn_output = resolve_bool(
        section.get("AUTO_VALIDATE_CONN_OUTPUT"),
        field_name="LogToCsv.AUTO_VALIDATE_CONN_OUTPUT",
        default=DEFAULT_AUTO_VALIDATE_CONN_OUTPUT,
        settings_path=settings_path,
    )
    if merge_fan_in < 2:
        raise SystemExit(f"LogToCsv.MERGE_FAN_IN must be at least 2 in {settings_path}")
    return (
        input_path,
        output_root,
        target_logs,
        network_conf,
        output_chunk_size,
        run_row_limit,
        merge_fan_in,
        auto_validate_conn_output,
    )


def find_target_log_files(log_dir: Path, target_logs: Sequence[str]) -> List[Path]:
    files = [log_dir / log_name for log_name in target_logs if (log_dir / log_name).is_file()]
    if not files:
        joined = ", ".join(target_logs)
        raise SystemExit(f"No target logs ({joined}) were found under {log_dir}")
    return files


def target_output_dir_name(target_log: str) -> str:
    path = Path(target_log)
    if path.suffix:
        return path.stem or path.name
    return path.name


def iter_records(files: Sequence[Path]) -> Iterator[dict]:
    for log_file in files:
        with log_file.open("r", encoding="utf-8") as fh:
            for line_number, line in enumerate(fh, start=1):
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    yield json.loads(stripped)
                except json.JSONDecodeError as exc:
                    raise SystemExit(
                        f"Invalid JSON in {log_file}:{line_number}: {exc}"
                    ) from exc


CONN_REQUIRED_COLUMNS = [
    "daytime",
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
    "label",
]


def collect_record_header(record: dict) -> List[str]:
    seen = set()
    header: List[str] = []
    for key in record.keys():
        normalized_key = "daytime" if key == "ts" else key
        if normalized_key not in seen:
            seen.add(normalized_key)
            header.append(normalized_key)
    return header


def extend_header_for_target_logs(
    header: Sequence[str],
    target_logs: Sequence[str] | None = None,
) -> List[str]:
    extended = list(header)
    seen = set(extended)
    if target_logs and "conn.log" in target_logs:
        for column in CONN_REQUIRED_COLUMNS:
            if column not in seen:
                seen.add(column)
                extended.append(column)
    if "label" not in seen:
        extended.append("label")
    return extended


def collect_header(records: Iterable[dict], target_logs: Sequence[str] | None = None) -> List[str]:
    header: List[str] = []
    for record in records:
        header = merge_headers(header, collect_record_header(record))
    header = extend_header_for_target_logs(header, target_logs)
    if not header:
        raise SystemExit("No JSON objects were found in the provided log files.")
    return header


def parse_unix_ts(value) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_duration_seconds(value) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def resolve_flow_end_ts(record: dict) -> float | None:
    start_ts = parse_unix_ts(record.get("ts"))
    if start_ts is None:
        return None
    duration = parse_duration_seconds(record.get("duration"))
    if duration is None:
        return start_ts
    return start_ts + duration


def has_valid_record_timestamp(record: dict) -> bool:
    return resolve_flow_end_ts(record) is not None


def convert_ts_to_daytime(ts: float | None) -> str:
    if ts is None:
        return ""
    utc_dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    return utc_dt.astimezone(JST).strftime(DATETIME_FORMAT)


def _ip_in_any(ip_str: str, networks: Sequence[str]) -> bool:
    try:
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


def should_exclude_record(record: dict, network_conf: dict) -> bool:
    src = record.get("id.orig_h")
    dst = record.get("id.resp_h")
    if not src or not dst:
        return False
    exception = network_conf.get("EXCEPTION", [])
    return _ip_in_any(src, exception) or _ip_in_any(dst, exception)


def assign_label(record: dict, network_conf: dict) -> int | None:
    src = record.get("id.orig_h")
    dst = record.get("id.resp_h")
    if not src or not dst:
        return None
    malicious = network_conf.get("MALICIOUS", [])
    benign = network_conf.get("BENIGN", [])
    if _ip_in_any(src, malicious) or _ip_in_any(dst, malicious):
        return 1
    if _ip_in_any(src, benign) and not _ip_in_any(dst, benign):
        return 0
    if _ip_in_any(dst, benign) and not _ip_in_any(src, benign):
        return 0
    return None


def normalize_value(value):
    if value is None:
        return ""
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=True)
    return value


def resolve_csv_value(record: dict, key: str):
    if key == "duration":
        duration = parse_duration_seconds(record.get("duration"))
        if duration is None:
            return 0
        return duration
    return normalize_value(record.get(key, ""))


def build_csv_row_with_reason(
    record: dict,
    header: Sequence[str],
    network_conf: dict,
) -> tuple[dict | None, str | None]:
    if should_exclude_record(record, network_conf):
        return None, "excluded"
    label = assign_label(record, network_conf)
    if label is None:
        return None, "unlabeled"
    row = {}
    for key in header:
        if key == "daytime":
            row[key] = convert_ts_to_daytime(resolve_flow_end_ts(record))
        elif key == "label":
            row[key] = label
        else:
            row[key] = resolve_csv_value(record, key)
    return row, None


def build_csv_row(record: dict, header: Sequence[str], network_conf: dict) -> dict | None:
    row, _reason = build_csv_row_with_reason(record, header, network_conf)
    return row


def write_rows_to_csv(rows: Sequence[dict], header: Sequence[str], destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=header, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def merge_headers(existing: list[str], new_header: Sequence[str]) -> list[str]:
    seen = set(existing)
    merged = list(existing)
    for key in new_header:
        if key not in seen:
            seen.add(key)
            merged.append(key)
    return merged


def log_dir_contains_logs(log_dir: Path, target_logs: Sequence[str]) -> bool:
    return any((log_dir / log_name).is_file() for log_name in target_logs)


def infer_single_batch_name(log_dir: Path) -> str:
    parent_name = log_dir.parent.name
    if parent_name and parent_name not in {"logs", "unproc", "data"}:
        return parent_name
    return log_dir.name


def discover_log_dirs(input_path: Path, target_logs: Sequence[str]) -> tuple[list[Path], str]:
    if not input_path.is_dir():
        raise SystemExit(f"Log path not found: {input_path}")
    if log_dir_contains_logs(input_path, target_logs):
        return [input_path], infer_single_batch_name(input_path)
    log_dirs = sorted(
        p for p in input_path.iterdir() if p.is_dir() and log_dir_contains_logs(p, target_logs)
    )
    if not log_dirs:
        raise SystemExit(f"No log directories were found under {input_path}")
    return log_dirs, input_path.name


def parse_daytime(value: str, source_name: str) -> datetime:
    try:
        return datetime.strptime(value, DATETIME_FORMAT)
    except ValueError as exc:
        raise SystemExit(
            f"Invalid daytime value '{value}' in {source_name}. Expected format: {DATETIME_FORMAT}"
        ) from exc


class CsvSequence:
    def __init__(self, csv_path: Path):
        self.csv_path = csv_path
        self.file = csv_path.open("r", encoding="utf-8", newline="")
        self.reader = csv.DictReader(self.file)
        self.current_row: dict | None = None
        self.current_dt: datetime | None = None
        self.header = self.reader.fieldnames or []
        self.exhausted = False
        self.advance()

    def close(self) -> None:
        self.file.close()

    def advance(self) -> None:
        try:
            row = next(self.reader)
        except StopIteration:
            self.current_row = None
            self.current_dt = None
            self.exhausted = True
            return
        if "daytime" not in row:
            raise SystemExit(f"Missing 'daytime' column in {self.csv_path}")
        self.current_row = row
        self.current_dt = parse_daytime(row["daytime"], self.csv_path.name)
        self.exhausted = False

    def pop_current(self) -> tuple[datetime, dict]:
        if self.current_row is None or self.current_dt is None:
            raise StopIteration("No current row available.")
        current_dt = self.current_dt
        row = dict(self.current_row)
        self.advance()
        return current_dt, row


def chunk_output_filename(output_index: int, first_daytime: datetime) -> str:
    return f"{output_index:05d}_{first_daytime.strftime('%Y%m%d%H%M%S')}.csv"


def flush_chunk_rows(
    output_dir: Path,
    header: Sequence[str],
    rows: list[dict],
    output_index: int,
    first_daytime: datetime,
) -> int:
    destination = output_dir / chunk_output_filename(output_index, first_daytime)
    write_rows_to_csv(rows, header, destination)
    rows.clear()
    return output_index + 1


def push_sequence_if_available(
    heap: list[tuple[datetime, int]],
    sequences: Sequence[CsvSequence],
    sequence_index: int,
) -> None:
    current_dt = sequences[sequence_index].current_dt
    if current_dt is not None:
        heapq.heappush(heap, (current_dt, sequence_index))


def merge_sorted_csv_group_to_single_csv(
    sorted_csv_paths: Sequence[Path],
    destination: Path,
    final_header: Sequence[str],
) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    sequences = [CsvSequence(path) for path in sorted_csv_paths]
    heap: list[tuple[datetime, int]] = []
    try:
        for index, _sequence in enumerate(sequences):
            push_sequence_if_available(heap, sequences, index)
        with destination.open("w", newline="", encoding="utf-8") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=final_header, extrasaction="ignore")
            writer.writeheader()
            while heap:
                _, sequence_index = heapq.heappop(heap)
                _, row = sequences[sequence_index].pop_current()
                writer.writerow(row)
                if not sequences[sequence_index].exhausted:
                    push_sequence_if_available(heap, sequences, sequence_index)
        return destination
    finally:
        for sequence in sequences:
            sequence.close()


def merge_sorted_csv_group_to_output_chunks(
    sorted_csv_paths: Sequence[Path],
    destination_dir: Path,
    final_header: Sequence[str],
    output_chunk_size: int,
) -> list[Path]:
    if not sorted_csv_paths:
        return []
    destination_dir.mkdir(parents=True, exist_ok=True)
    sequences = [CsvSequence(path) for path in sorted_csv_paths]
    created_paths: list[Path] = []
    heap: list[tuple[datetime, int]] = []
    try:
        for index, _sequence in enumerate(sequences):
            push_sequence_if_available(heap, sequences, index)
        output_index = 0
        chunk_rows: list[dict] = []
        chunk_first_daytime: datetime | None = None
        if not heap:
            raise SystemExit("No sorted CSV rows were available for chunk output.")
        while heap:
            _, sequence_index = heapq.heappop(heap)
            current_dt, row = sequences[sequence_index].pop_current()
            if chunk_first_daytime is None:
                chunk_first_daytime = current_dt
            chunk_rows.append(row)
            if not sequences[sequence_index].exhausted:
                push_sequence_if_available(heap, sequences, sequence_index)
            if len(chunk_rows) >= output_chunk_size:
                created_paths.append(
                    destination_dir / chunk_output_filename(output_index, chunk_first_daytime)
                )
                output_index = flush_chunk_rows(
                    destination_dir, final_header, chunk_rows, output_index, chunk_first_daytime
                )
                chunk_first_daytime = None
        if chunk_rows:
            if chunk_first_daytime is None:
                raise SystemExit("Chunk output is missing its first daytime.")
            created_paths.append(destination_dir / chunk_output_filename(output_index, chunk_first_daytime))
            flush_chunk_rows(destination_dir, final_header, chunk_rows, output_index, chunk_first_daytime)
        return created_paths
    finally:
        for sequence in sequences:
            sequence.close()


def sort_rows_by_daytime(rows: list[dict]) -> None:
    rows.sort(key=lambda row: row["daytime"])


def flush_run_rows(
    temp_dir: Path,
    run_rows: list[dict],
    final_header: Sequence[str],
    run_index: int,
) -> tuple[Path, int, int]:
    row_count = len(run_rows)
    sort_rows_by_daytime(run_rows)
    run_path = temp_dir / f"run_l0_{run_index:05d}.csv"
    write_rows_to_csv(run_rows, final_header, run_path)
    run_rows.clear()
    return run_path, run_index + 1, row_count


def create_initial_sorted_runs(
    log_dirs: Sequence[Path],
    temp_dir: Path,
    network_conf: dict,
    target_log: str,
    run_row_limit: int,
) -> tuple[list[Path], list[str], RunCreationStats]:
    final_header = extend_header_for_target_logs([], [target_log])
    run_paths: list[Path] = []
    run_rows: list[dict] = []
    run_index = 0
    stats = RunCreationStats()
    total_log_dir_count = len(log_dirs)
    for directory_index, log_dir in enumerate(log_dirs, start=1):
        target_file = log_dir / target_log
        if not target_file.is_file():
            continue
        stats.matched_log_dir_count += 1
        dir_scanned_record_count = 0
        dir_skipped_invalid_ts_count = 0
        dir_excluded_record_count = 0
        dir_unlabeled_record_count = 0
        dir_emitted_row_count = 0
        files = find_target_log_files(log_dir, [target_log])
        print(
            f"[log-to-csv] 読み込み開始 ({directory_index}/{total_log_dir_count}): "
            f"{target_file}"
        )
        for record in iter_records(files):
            stats.scanned_record_count += 1
            dir_scanned_record_count += 1
            if not has_valid_record_timestamp(record):
                stats.skipped_invalid_ts_count += 1
                dir_skipped_invalid_ts_count += 1
                continue
            row_header = extend_header_for_target_logs(collect_record_header(record), [target_log])
            final_header = merge_headers(final_header, row_header)
            row, reason = build_csv_row_with_reason(record, row_header, network_conf)
            if row is None:
                if reason == "excluded":
                    stats.excluded_record_count += 1
                    dir_excluded_record_count += 1
                elif reason == "unlabeled":
                    stats.unlabeled_record_count += 1
                    dir_unlabeled_record_count += 1
                continue
            run_rows.append(row)
            stats.emitted_row_count += 1
            dir_emitted_row_count += 1
            if len(run_rows) >= run_row_limit:
                run_path, run_index, flushed_row_count = flush_run_rows(
                    temp_dir, run_rows, final_header, run_index
                )
                run_paths.append(run_path)
                stats.run_count += 1
                print(
                    f"[log-to-csv] 一時 run 出力: {run_path.name} / rows={flushed_row_count}"
                )
        print(
            f"[log-to-csv] 読み込み完了: {target_file.name} / record={dir_scanned_record_count} "
            f"/ 出力行={dir_emitted_row_count} / ts不正={dir_skipped_invalid_ts_count} "
            f"/ 例外除外={dir_excluded_record_count} / ラベル未確定={dir_unlabeled_record_count}"
        )
    if run_rows:
        run_path, run_index, flushed_row_count = flush_run_rows(
            temp_dir, run_rows, final_header, run_index
        )
        run_paths.append(run_path)
        stats.run_count += 1
        print(f"[log-to-csv] 一時 run 出力: {run_path.name} / rows={flushed_row_count}")
    if stats.matched_log_dir_count == 0:
        raise SystemExit(f"No target logs ({target_log}) were found in the discovered log directories.")
    print(
        f"[log-to-csv] 一時 run 作成完了: run数={stats.run_count} / record={stats.scanned_record_count} "
        f"/ 出力行={stats.emitted_row_count} / ts不正={stats.skipped_invalid_ts_count} "
        f"/ 例外除外={stats.excluded_record_count} / ラベル未確定={stats.unlabeled_record_count}"
    )
    if stats.emitted_row_count == 0:
        if stats.skipped_invalid_ts_count > 0:
            raise SystemExit(
                f"No CSV rows were produced for {target_log}. "
                f"Skipped {stats.skipped_invalid_ts_count} records because ts/duration were missing or invalid."
            )
        raise SystemExit(f"No CSV rows were produced for {target_log} after filtering and labeling.")
    return run_paths, final_header, stats


def merge_run_level(
    input_paths: Sequence[Path],
    temp_dir: Path,
    final_header: Sequence[str],
    merge_fan_in: int,
    level: int,
) -> list[Path]:
    merged_paths: list[Path] = []
    for group_start in range(0, len(input_paths), merge_fan_in):
        group = input_paths[group_start : group_start + merge_fan_in]
        destination = temp_dir / f"run_l{level}_{group_start // merge_fan_in:05d}.csv"
        merged_paths.append(merge_sorted_csv_group_to_single_csv(group, destination, final_header))
    return merged_paths


def external_merge_sorted_runs_to_chunks(
    run_paths: Sequence[Path],
    temp_dir: Path,
    destination_dir: Path,
    final_header: Sequence[str],
    output_chunk_size: int,
    merge_fan_in: int,
) -> list[Path]:
    current_paths = list(run_paths)
    level = 1
    while len(current_paths) > merge_fan_in:
        print(
            f"[log-to-csv] 段階マージ: level={level} / 入力 run 数={len(current_paths)} "
            f"/ fan-in={merge_fan_in}"
        )
        next_paths = merge_run_level(current_paths, temp_dir, final_header, merge_fan_in, level)
        for old_path in current_paths:
            old_path.unlink()
        current_paths = next_paths
        level += 1
    print(
        f"[log-to-csv] 最終チャンク出力: 入力 run 数={len(current_paths)} / chunk_size={output_chunk_size}"
    )
    return merge_sorted_csv_group_to_output_chunks(
        current_paths, destination_dir, final_header, output_chunk_size
    )


def convert_batch_to_chunked_csv_with_stats(
    log_dirs: Sequence[Path],
    destination_dir: Path,
    network_conf: dict,
    target_log: str,
    output_chunk_size: int,
    run_row_limit: int,
    merge_fan_in: int,
) -> tuple[list[Path], RunCreationStats]:
    temp_dir = destination_dir.parent / f".tmp_log_to_csv_{destination_dir.name}"
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.mkdir(parents=True, exist_ok=True)
    try:
        run_paths, final_header, stats = create_initial_sorted_runs(
            log_dirs, temp_dir, network_conf, target_log, run_row_limit
        )
        if destination_dir.exists():
            shutil.rmtree(destination_dir)
        destination_dir.mkdir(parents=True, exist_ok=True)
        created_files = external_merge_sorted_runs_to_chunks(
            run_paths,
            temp_dir,
            destination_dir,
            final_header,
            output_chunk_size,
            merge_fan_in,
        )
        return created_files, stats
    finally:
        if temp_dir.exists():
            shutil.rmtree(temp_dir)


def convert_batch_to_chunked_csv(
    log_dirs: Sequence[Path],
    destination_dir: Path,
    network_conf: dict,
    target_log: str,
    output_chunk_size: int,
    run_row_limit: int,
    merge_fan_in: int,
) -> list[Path]:
    created_files, _stats = convert_batch_to_chunked_csv_with_stats(
        log_dirs,
        destination_dir,
        network_conf,
        target_log,
        output_chunk_size,
        run_row_limit,
        merge_fan_in,
    )
    return created_files


def should_run_runtime_validation(target_log: str) -> bool:
    return target_log == "conn.log"


def convert_logs_to_csv(
    input_path: Path,
    output_root: Path,
    target_logs: Sequence[str],
    network_conf: dict,
    output_chunk_size: int,
    run_row_limit: int,
    merge_fan_in: int,
    *,
    runtime_settings_path: str | Path = csv_validator.DEFAULT_RUNTIME_SETTINGS_PATH,
    auto_validate_conn_output: bool = DEFAULT_AUTO_VALIDATE_CONN_OUTPUT,
    zeek_settings_path: str | Path = SETTINGS_PATH,
) -> list[Path]:
    if output_root.exists() and not output_root.is_dir():
        raise SystemExit(f"Output root exists and is not a directory: {output_root}")

    log_dirs, batch_name = discover_log_dirs(input_path, target_logs)
    print(
        f"[log-to-csv] 開始: 入力={input_path} / バッチ={batch_name} / "
        f"対象ログ={', '.join(target_logs)} / ログディレクトリ数={len(log_dirs)}"
    )

    created_output_dirs: list[Path] = []
    for target_log in target_logs:
        target_output_dir = output_root / target_output_dir_name(target_log) / batch_name
        created_output_dirs.append(target_output_dir)
        print(
            f"[log-to-csv] 変換開始: target_log={target_log} / 出力先={target_output_dir}"
        )
        created_files, stats = convert_batch_to_chunked_csv_with_stats(
            log_dirs,
            target_output_dir,
            network_conf,
            target_log,
            output_chunk_size,
            run_row_limit,
            merge_fan_in,
        )
        print(
            f"[log-to-csv] 変換完了: target_log={target_log} / 出力行={stats.emitted_row_count} "
            f"/ chunk数={len(created_files)} / run数={stats.run_count}"
        )
        for created_file in created_files:
            print(created_file)
        if auto_validate_conn_output and should_run_runtime_validation(target_log):
            print(f"[log-to-csv] runtime契約チェック開始: {target_output_dir}")
            report = csv_validator.validate_csv_dataset(
                target_output_dir,
                schema="zeek",
                runtime_settings_path=runtime_settings_path,
                network_conf=network_conf,
                zeek_settings_path=zeek_settings_path,
            )
            csv_validator.print_report(report)
            if not report.ok:
                raise SystemExit(
                    f"Converted CSV failed runtime contract validation: {target_output_dir}"
                )
        elif should_run_runtime_validation(target_log):
            print("[log-to-csv] runtime契約チェックを設定で無効化しています")
        else:
            print(
                f"[log-to-csv] runtime契約チェックを省略: {target_log} は make run の標準入力ではありません"
            )

    for created_output_dir in created_output_dirs:
        print(created_output_dir)
    print(f"[log-to-csv] 完了: 出力ディレクトリ数={len(created_output_dirs)}")
    return created_output_dirs


def main() -> None:
    args = parse_args()
    settings_path_arg = getattr(args, "settings_path", None)
    settings_path = resolve_settings_path(settings_path_arg)
    settings = load_settings(settings_path) if settings_path_arg else load_settings()
    (
        input_path,
        output_root,
        target_logs,
        network_conf,
        output_chunk_size,
        run_row_limit,
        merge_fan_in,
        auto_validate_conn_output,
    ) = resolve_config(settings, settings_path)
    convert_logs_to_csv(
        input_path,
        output_root,
        target_logs,
        network_conf,
        output_chunk_size,
        run_row_limit,
        merge_fan_in,
        auto_validate_conn_output=auto_validate_conn_output,
        zeek_settings_path=settings_path,
    )


if __name__ == "__main__":
    main()
