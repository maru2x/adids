#!/usr/bin/env python3
"""Convert configured Zeek JSON logs to CSV using the current batch layout."""

from __future__ import annotations

import argparse
import csv
import ipaddress
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, Iterator, List, Sequence


JST = timezone(timedelta(hours=9))
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[3]
SETTINGS_PATH = SCRIPT_DIR / "settings.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Convert configured Zeek JSON log directories into CSV using "
            "the current batch layout."
        )
    )
    return parser.parse_args()


def load_settings() -> dict:
    if not SETTINGS_PATH.is_file():
        raise SystemExit(f"Settings file not found: {SETTINGS_PATH}")
    with SETTINGS_PATH.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def resolve_repo_path(path_str: str, *, field_name: str) -> Path:
    if not path_str:
        raise SystemExit(f"{field_name} is required in {SETTINGS_PATH}")
    raw_path = Path(path_str).expanduser()
    if raw_path.is_absolute():
        return raw_path.resolve()
    return (PROJECT_ROOT / raw_path).resolve()


def normalize_target_logs(target_logs: object) -> list[str]:
    if not isinstance(target_logs, list) or not target_logs:
        raise SystemExit(f"LogToCsv.TARGET_LOGS must be a non-empty array in {SETTINGS_PATH}")
    normalized: list[str] = []
    seen: set[str] = set()
    for value in target_logs:
        if not isinstance(value, str) or not value.strip():
            raise SystemExit(f"LogToCsv.TARGET_LOGS must contain non-empty strings in {SETTINGS_PATH}")
        name = value.strip()
        if name not in seen:
            seen.add(name)
            normalized.append(name)
    return normalized


def resolve_network_config(settings: dict, network_key: str) -> dict:
    network_map = settings.get("NetworkAddress")
    if not isinstance(network_map, dict):
        raise SystemExit(f"NetworkAddress section not found in {SETTINGS_PATH}")
    network_conf = network_map.get(network_key)
    if not isinstance(network_conf, dict):
        raise SystemExit(f"NetworkAddress '{network_key}' not found in {SETTINGS_PATH}")
    return network_conf


def resolve_config(settings: dict) -> tuple[Path, Path, list[str], dict]:
    section = settings.get("LogToCsv")
    if not isinstance(section, dict):
        raise SystemExit(f"LogToCsv section not found in {SETTINGS_PATH}")
    input_path = resolve_repo_path(section.get("INPUT_DIR_PATH", ""), field_name="LogToCsv.INPUT_DIR_PATH")
    output_root = resolve_repo_path(
        section.get("OUTPUT_ROOT_DIR_PATH", ""),
        field_name="LogToCsv.OUTPUT_ROOT_DIR_PATH",
    )
    target_logs = normalize_target_logs(section.get("TARGET_LOGS"))
    network_key = section.get("NETWORK_KEY")
    if not isinstance(network_key, str) or not network_key.strip():
        raise SystemExit(f"LogToCsv.NETWORK_KEY is required in {SETTINGS_PATH}")
    network_conf = resolve_network_config(settings, network_key.strip())
    return input_path, output_root, target_logs, network_conf


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


def load_records(files: Sequence[Path]) -> List[dict]:
    return list(iter_records(files))


def collect_header(records: Iterable[dict]) -> List[str]:
    seen = set()
    header: List[str] = []
    for record in records:
        for key in record.keys():
            normalized_key = "daytime" if key == "ts" else key
            if normalized_key not in seen:
                seen.add(normalized_key)
                header.append(normalized_key)
    if "label" not in seen:
        header.append("label")
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


def convert_ts_to_daytime(ts: float | None) -> str:
    if ts is None:
        return ""
    utc_dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    return utc_dt.astimezone(JST).strftime("%Y-%m-%d %H:%M:%S")


def sort_records_by_flow_end_time(records: Sequence[dict]) -> List[dict]:
    sortable_records = []
    for index, record in enumerate(records):
        flow_end_ts = resolve_flow_end_ts(record)
        sort_key = float("inf") if flow_end_ts is None else flow_end_ts
        sortable_records.append((sort_key, index, record))
    sortable_records.sort(key=lambda item: (item[0], item[1]))
    return [record for _, _, record in sortable_records]


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


def write_csv(
    records: Sequence[dict],
    header: Sequence[str],
    destination: Path,
    network_conf: dict,
) -> None:
    records = sort_records_by_flow_end_time(records)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=header, extrasaction="ignore")
        writer.writeheader()
        for record in records:
            if should_exclude_record(record, network_conf):
                continue
            label = assign_label(record, network_conf)
            if label is None:
                continue
            row = {}
            for key in header:
                if key == "daytime":
                    row[key] = convert_ts_to_daytime(resolve_flow_end_ts(record))
                elif key == "label":
                    row[key] = label
                else:
                    row[key] = normalize_value(record.get(key, ""))
            writer.writerow(row)


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


def convert_log_dir(
    log_dir: Path,
    destination: Path,
    network_conf: dict,
    target_logs: Sequence[str],
) -> None:
    files = find_target_log_files(log_dir, target_logs)
    records = load_records(files)
    header = collect_header(records)
    write_csv(records, header, destination, network_conf)


def main() -> None:
    parse_args()
    settings = load_settings()
    input_path, output_root, target_logs, network_conf = resolve_config(settings)

    if output_root.exists() and not output_root.is_dir():
        raise SystemExit(f"Output root exists and is not a directory: {output_root}")

    log_dirs, batch_name = discover_log_dirs(input_path, target_logs)
    output_dir = output_root / batch_name
    output_dir.mkdir(parents=True, exist_ok=True)

    created_output_dirs: list[Path] = []
    for target_log in target_logs:
        target_output_dir = output_dir / target_output_dir_name(target_log)
        target_output_dir.mkdir(parents=True, exist_ok=True)
        created_output_dirs.append(target_output_dir)
        for log_dir in log_dirs:
            target_file = log_dir / target_log
            if not target_file.is_file():
                continue
            destination = target_output_dir / f"{log_dir.name}.csv"
            convert_log_dir(log_dir, destination, network_conf, [target_log])
            print(f"{target_file} -> {destination}")

    for created_output_dir in created_output_dirs:
        print(created_output_dir)


if __name__ == "__main__":
    main()
