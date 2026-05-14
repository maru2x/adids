#!/usr/bin/env python3
"""Export Zeek conn.log data to runtime-compatible leaf CSV directories."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Sequence

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.util.FeatureExtract.Zeek import log_to_csv_extractor as extractor
from src.util.Validate import validate_csv_dataset as csv_validator


DEFAULT_RUNTIME_SETTINGS_PATH = csv_validator.DEFAULT_RUNTIME_SETTINGS_PATH
DEFAULT_ZEEK_SETTINGS_PATH = extractor.SETTINGS_PATH
DEFAULT_OUTPUT_CHUNK_SIZE = extractor.DEFAULT_OUTPUT_CHUNK_SIZE
DEFAULT_RUN_ROW_LIMIT = extractor.DEFAULT_RUN_ROW_LIMIT
DEFAULT_MERGE_FAN_IN = extractor.DEFAULT_MERGE_FAN_IN
DEFAULT_VALIDATE_OUTPUT = True
CONN_LOG_NAME = "conn.log"
RUNTIME_COMPATIBLE_CONN_COLUMNS = (
    "daytime",
    "label",
    "proto",
    "id.orig_h",
    "id.orig_p",
    "id.resp_h",
    "id.resp_p",
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
)


@dataclass
class LiveExportState:
    source_inode: int | None = None
    offset: int = 0
    next_output_index: int = 0
    current_chunk_name: str | None = None
    current_chunk_row_count: int = 0
    current_chunk_first_daytime: str | None = None


@dataclass
class LiveExportStats:
    scanned_record_count: int = 0
    skipped_invalid_ts_count: int = 0
    emitted_row_count: int = 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Export Zeek conn.log data into runtime-compatible leaf CSV directories "
            "for both static batch inputs and growing live logs."
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    batch_parser = subparsers.add_parser(
        "batch",
        help="Export a static Zeek log batch directory to a runtime-compatible leaf CSV directory.",
    )
    batch_parser.add_argument("--input-dir", required=True, help="Log batch dir or single log dir")
    batch_parser.add_argument(
        "--output-dir",
        required=True,
        help="Leaf CSV directory to create for runtime-compatible conn features",
    )
    batch_parser.add_argument(
        "--network-key",
        required=True,
        help="NetworkAddress key in the Zeek settings file used for label assignment",
    )
    batch_parser.add_argument(
        "--zeek-settings",
        default=str(DEFAULT_ZEEK_SETTINGS_PATH),
        help="Path to src/util/FeatureExtract/Zeek/settings.json",
    )
    batch_parser.add_argument(
        "--runtime-settings",
        default=str(DEFAULT_RUNTIME_SETTINGS_PATH),
        help="Path to src/main/settings.json used for output validation",
    )
    batch_parser.add_argument(
        "--output-chunk-size",
        type=int,
        default=DEFAULT_OUTPUT_CHUNK_SIZE,
        help="How many rows to place in each output CSV chunk",
    )
    batch_parser.add_argument(
        "--run-row-limit",
        type=int,
        default=DEFAULT_RUN_ROW_LIMIT,
        help="How many rows to buffer before flushing a sorted temp run",
    )
    batch_parser.add_argument(
        "--merge-fan-in",
        type=int,
        default=DEFAULT_MERGE_FAN_IN,
        help="How many temp runs to merge at once",
    )
    batch_parser.add_argument(
        "--no-validate",
        action="store_true",
        help="Skip runtime contract validation after CSV export",
    )

    live_parser = subparsers.add_parser(
        "live",
        help="Incrementally export new rows from a growing Zeek conn.log into leaf CSV chunks.",
    )
    live_parser.add_argument("--input-dir", required=True, help="Directory containing conn.log")
    live_parser.add_argument(
        "--output-dir",
        required=True,
        help="Leaf CSV directory to append runtime-compatible conn features into",
    )
    live_parser.add_argument(
        "--label",
        type=int,
        required=True,
        choices=(0, 1),
        help="Fixed label to assign to every exported live row",
    )
    live_parser.add_argument(
        "--state-path",
        help="Path to the incremental export state file. Defaults to a hidden file next to the output dir.",
    )
    live_parser.add_argument(
        "--runtime-settings",
        default=str(DEFAULT_RUNTIME_SETTINGS_PATH),
        help="Path to src/main/settings.json used for output validation",
    )
    live_parser.add_argument(
        "--output-chunk-size",
        type=int,
        default=DEFAULT_OUTPUT_CHUNK_SIZE,
        help="How many rows to place in each output CSV chunk",
    )
    live_parser.add_argument(
        "--no-validate",
        action="store_true",
        help="Skip runtime contract validation after CSV export",
    )
    return parser.parse_args()


def resolve_repo_path(path_str: str) -> Path:
    raw_path = Path(path_str).expanduser()
    if raw_path.is_absolute():
        return raw_path.resolve()
    return (extractor.PROJECT_ROOT / raw_path).resolve()


def resolve_positive_int(value: int, *, field_name: str) -> int:
    if value <= 0:
        raise SystemExit(f"{field_name} must be a positive integer.")
    return value


def validate_output_leaf_dir(output_dir: Path) -> None:
    if not output_dir.exists():
        return
    if not output_dir.is_dir():
        raise SystemExit(f"Output path exists and is not a directory: {output_dir}")
    invalid_entries = [
        path.name
        for path in output_dir.iterdir()
        if path.is_dir() or path.suffix.lower() != ".csv"
    ]
    if invalid_entries:
        raise SystemExit(
            f"Output leaf dir must contain CSV files only: {output_dir} (invalid entries: {invalid_entries})"
        )


def load_zeek_settings(settings_path: Path) -> dict:
    return extractor.load_settings(settings_path)


def resolve_network_conf(settings_path: Path, network_key: str) -> dict:
    settings = load_zeek_settings(settings_path)
    return extractor.resolve_network_config(settings, network_key, settings_path)


def build_runtime_compatible_row_with_reason(
    record: dict,
    *,
    network_conf: dict | None = None,
    fixed_label: int | None = None,
) -> tuple[dict | None, str | None]:
    if network_conf is not None:
        if extractor.should_exclude_record(record, network_conf):
            return None, "excluded"
        label = extractor.assign_label(record, network_conf)
        if label is None:
            return None, "unlabeled"
    elif fixed_label is not None:
        label = fixed_label
    else:
        raise ValueError("Either network_conf or fixed_label must be provided.")

    row = {}
    for key in RUNTIME_COMPATIBLE_CONN_COLUMNS:
        if key == "daytime":
            row[key] = extractor.convert_ts_to_daytime(extractor.resolve_flow_end_ts(record))
        elif key == "label":
            row[key] = label
        else:
            row[key] = extractor.resolve_csv_value(record, key)
    return row, None


def flush_feature_rows(
    temp_dir: Path,
    run_rows: list[dict],
    run_index: int,
) -> tuple[Path, int, int]:
    row_count = len(run_rows)
    extractor.sort_rows_by_daytime(run_rows)
    run_path = temp_dir / f"run_l0_{run_index:05d}.csv"
    extractor.write_rows_to_csv(run_rows, RUNTIME_COMPATIBLE_CONN_COLUMNS, run_path)
    run_rows.clear()
    return run_path, run_index + 1, row_count


def create_initial_feature_runs(
    log_dirs: Sequence[Path],
    temp_dir: Path,
    *,
    network_conf: dict | None = None,
    fixed_label: int | None = None,
    run_row_limit: int,
    caller_tag: str,
) -> tuple[list[Path], extractor.RunCreationStats]:
    run_paths: list[Path] = []
    run_rows: list[dict] = []
    run_index = 0
    stats = extractor.RunCreationStats()
    total_log_dir_count = len(log_dirs)

    for directory_index, log_dir in enumerate(log_dirs, start=1):
        target_file = log_dir / CONN_LOG_NAME
        if not target_file.is_file():
            continue
        stats.matched_log_dir_count += 1
        dir_scanned_record_count = 0
        dir_skipped_invalid_ts_count = 0
        dir_excluded_record_count = 0
        dir_unlabeled_record_count = 0
        dir_emitted_row_count = 0
        print(
            f"{caller_tag} 読み込み開始 ({directory_index}/{total_log_dir_count}): {target_file}"
        )
        for record in extractor.iter_records([target_file]):
            stats.scanned_record_count += 1
            dir_scanned_record_count += 1
            if not extractor.has_valid_record_timestamp(record):
                stats.skipped_invalid_ts_count += 1
                dir_skipped_invalid_ts_count += 1
                continue
            row, reason = build_runtime_compatible_row_with_reason(
                record,
                network_conf=network_conf,
                fixed_label=fixed_label,
            )
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
                run_path, run_index, flushed_row_count = flush_feature_rows(
                    temp_dir,
                    run_rows,
                    run_index,
                )
                run_paths.append(run_path)
                stats.run_count += 1
                print(f"{caller_tag} 一時 run 出力: {run_path.name} / rows={flushed_row_count}")
        print(
            f"{caller_tag} 読み込み完了: {target_file.name} / record={dir_scanned_record_count} "
            f"/ 出力行={dir_emitted_row_count} / ts不正={dir_skipped_invalid_ts_count} "
            f"/ 例外除外={dir_excluded_record_count} / ラベル未確定={dir_unlabeled_record_count}"
        )

    if run_rows:
        run_path, run_index, flushed_row_count = flush_feature_rows(
            temp_dir,
            run_rows,
            run_index,
        )
        run_paths.append(run_path)
        stats.run_count += 1
        print(f"{caller_tag} 一時 run 出力: {run_path.name} / rows={flushed_row_count}")

    if stats.matched_log_dir_count == 0:
        raise SystemExit(f"No {CONN_LOG_NAME} files were found in the discovered log directories.")
    print(
        f"{caller_tag} 一時 run 作成完了: run数={stats.run_count} / record={stats.scanned_record_count} "
        f"/ 出力行={stats.emitted_row_count} / ts不正={stats.skipped_invalid_ts_count} "
        f"/ 例外除外={stats.excluded_record_count} / ラベル未確定={stats.unlabeled_record_count}"
    )
    if stats.emitted_row_count == 0:
        if stats.skipped_invalid_ts_count > 0:
            raise SystemExit(
                "No CSV rows were produced. "
                f"Skipped {stats.skipped_invalid_ts_count} records because ts/duration were missing or invalid."
            )
        raise SystemExit("No CSV rows were produced after filtering and labeling.")
    return run_paths, stats


def export_batch_conn_logs_with_stats(
    log_dirs: Sequence[Path],
    output_dir: Path,
    *,
    network_conf: dict,
    output_chunk_size: int,
    run_row_limit: int,
    merge_fan_in: int,
    caller_tag: str,
) -> tuple[list[Path], extractor.RunCreationStats]:
    temp_dir = output_dir.parent / f".tmp_feature_export_{output_dir.name}"
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.mkdir(parents=True, exist_ok=True)
    try:
        run_paths, stats = create_initial_feature_runs(
            log_dirs,
            temp_dir,
            network_conf=network_conf,
            run_row_limit=run_row_limit,
            caller_tag=caller_tag,
        )
        if output_dir.exists():
            shutil.rmtree(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        created_files = extractor.external_merge_sorted_runs_to_chunks(
            run_paths,
            temp_dir,
            output_dir,
            RUNTIME_COMPATIBLE_CONN_COLUMNS,
            output_chunk_size,
            merge_fan_in,
        )
        return created_files, stats
    finally:
        if temp_dir.exists():
            shutil.rmtree(temp_dir)


def validate_runtime_csv_output(
    output_dir: Path,
    *,
    runtime_settings_path: Path,
    network_conf: dict | None = None,
    zeek_settings_path: Path | None = None,
    caller_tag: str,
) -> None:
    print(f"{caller_tag} runtime契約チェック開始: {output_dir}")
    report = csv_validator.validate_csv_dataset(
        output_dir,
        schema="zeek",
        runtime_settings_path=runtime_settings_path,
        network_conf=network_conf,
        zeek_settings_path=zeek_settings_path,
    )
    csv_validator.print_report(report)
    if not report.ok:
        raise SystemExit(f"Exported CSV failed runtime contract validation: {output_dir}")


def run_batch_command(args: argparse.Namespace) -> Path:
    input_dir = resolve_repo_path(args.input_dir)
    output_dir = resolve_repo_path(args.output_dir)
    runtime_settings_path = resolve_repo_path(args.runtime_settings)
    zeek_settings_path = resolve_repo_path(args.zeek_settings)
    output_chunk_size = resolve_positive_int(args.output_chunk_size, field_name="--output-chunk-size")
    run_row_limit = resolve_positive_int(args.run_row_limit, field_name="--run-row-limit")
    merge_fan_in = resolve_positive_int(args.merge_fan_in, field_name="--merge-fan-in")
    if merge_fan_in < 2:
        raise SystemExit("--merge-fan-in must be at least 2.")

    validate_output_leaf_dir(output_dir)
    network_conf = resolve_network_conf(zeek_settings_path, args.network_key)
    log_dirs, batch_name = extractor.discover_log_dirs(input_dir, [CONN_LOG_NAME])
    print(
        "[feature-export] batch 開始: "
        f"入力={input_dir} / バッチ={batch_name} / ログdir数={len(log_dirs)} / 出力={output_dir}"
    )
    created_files, stats = export_batch_conn_logs_with_stats(
        log_dirs,
        output_dir,
        network_conf=network_conf,
        output_chunk_size=output_chunk_size,
        run_row_limit=run_row_limit,
        merge_fan_in=merge_fan_in,
        caller_tag="[feature-export]",
    )
    print(
        "[feature-export] batch 完了: "
        f"出力行={stats.emitted_row_count} / chunk数={len(created_files)} / run数={stats.run_count}"
    )
    for created_file in created_files:
        print(created_file)
    if not args.no_validate:
        validate_runtime_csv_output(
            output_dir,
            runtime_settings_path=runtime_settings_path,
            network_conf=network_conf,
            zeek_settings_path=zeek_settings_path,
            caller_tag="[feature-export]",
        )
    else:
        print("[feature-export] runtime契約チェックを設定で無効化しています")
    return output_dir


def default_state_path(output_dir: Path) -> Path:
    return output_dir.parent / f".feature_export_state_{output_dir.name}.json"


def load_live_state(state_path: Path) -> LiveExportState:
    if not state_path.exists():
        return LiveExportState()
    with state_path.open("r", encoding="utf-8") as fh:
        return LiveExportState(**json.load(fh))


def save_live_state(state_path: Path, state: LiveExportState) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    with state_path.open("w", encoding="utf-8") as fh:
        json.dump(asdict(state), fh, ensure_ascii=True, indent=2)


def prepare_live_output_dir(output_dir: Path, state_path: Path) -> None:
    validate_output_leaf_dir(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    if state_path.exists():
        return
    if output_dir.exists() and any(output_dir.glob("*.csv")):
        raise SystemExit(
            f"Existing CSV files were found in {output_dir} without a state file. "
            "Refusing to continue because duplicate exports could be produced."
        )


def iter_new_live_records(conn_log_path: Path, state: LiveExportState) -> tuple[list[dict], int]:
    stat = conn_log_path.stat()
    if state.source_inode is not None and state.source_inode != stat.st_ino:
        state.offset = 0
        state.current_chunk_name = None
        state.current_chunk_row_count = 0
        state.current_chunk_first_daytime = None
    elif stat.st_size < state.offset:
        state.offset = 0
        state.current_chunk_name = None
        state.current_chunk_row_count = 0
        state.current_chunk_first_daytime = None

    records: list[dict] = []
    new_offset = state.offset
    with conn_log_path.open("rb") as fh:
        fh.seek(state.offset)
        while True:
            line_start_offset = fh.tell()
            line = fh.readline()
            if not line:
                break
            stripped = line.strip()
            if not stripped:
                new_offset = fh.tell()
                continue
            try:
                records.append(json.loads(stripped.decode("utf-8")))
                new_offset = fh.tell()
            except json.JSONDecodeError as exc:
                line_end_offset = fh.tell()
                if line_end_offset == stat.st_size and not line.endswith(b"\n"):
                    new_offset = line_start_offset
                    break
                raise SystemExit(f"Invalid JSON in live conn.log at byte offset {fh.tell()}: {exc}") from exc
    state.source_inode = stat.st_ino
    return records, new_offset


def open_chunk_writer(chunk_path: Path, *, write_header: bool) -> csv.DictWriter:
    fh = chunk_path.open("a", encoding="utf-8", newline="")
    writer = csv.DictWriter(
        fh,
        fieldnames=RUNTIME_COMPATIBLE_CONN_COLUMNS,
        extrasaction="ignore",
    )
    if write_header:
        writer.writeheader()
    writer._feature_export_file_handle = fh  # type: ignore[attr-defined]
    return writer


def close_chunk_writer(writer: csv.DictWriter) -> None:
    file_handle = getattr(writer, "_feature_export_file_handle", None)
    if file_handle is not None:
        file_handle.close()


def start_new_chunk(
    output_dir: Path,
    state: LiveExportState,
    row_daytime: str,
) -> tuple[Path, csv.DictWriter]:
    first_daytime = datetime.strptime(row_daytime, extractor.DATETIME_FORMAT)
    chunk_name = extractor.chunk_output_filename(state.next_output_index, first_daytime)
    chunk_path = output_dir / chunk_name
    state.current_chunk_name = chunk_name
    state.current_chunk_first_daytime = row_daytime
    state.current_chunk_row_count = 0
    state.next_output_index += 1
    return chunk_path, open_chunk_writer(chunk_path, write_header=True)


def open_existing_chunk(output_dir: Path, state: LiveExportState) -> tuple[Path, csv.DictWriter]:
    if not state.current_chunk_name:
        raise SystemExit("Live export state is missing its current chunk name.")
    chunk_path = output_dir / state.current_chunk_name
    if not chunk_path.is_file():
        raise SystemExit(f"Live export chunk referenced by state does not exist: {chunk_path}")
    return chunk_path, open_chunk_writer(chunk_path, write_header=False)


def export_live_conn_log_with_state(
    input_dir: Path,
    output_dir: Path,
    *,
    fixed_label: int,
    output_chunk_size: int,
    state_path: Path,
) -> LiveExportStats:
    if not input_dir.is_dir():
        raise SystemExit(f"Live input dir not found: {input_dir}")
    conn_log_path = input_dir / CONN_LOG_NAME
    if not conn_log_path.is_file():
        raise SystemExit(f"Live input dir does not contain {CONN_LOG_NAME}: {input_dir}")

    prepare_live_output_dir(output_dir, state_path)
    state = load_live_state(state_path)
    new_records, new_offset = iter_new_live_records(conn_log_path, state)
    stats = LiveExportStats(scanned_record_count=len(new_records))

    if not new_records:
        save_live_state(state_path, state)
        print("[feature-export] live 追加入力なし")
        return stats

    writer: csv.DictWriter | None = None
    current_chunk_path: Path | None = None
    try:
        for record in new_records:
            if not extractor.has_valid_record_timestamp(record):
                stats.skipped_invalid_ts_count += 1
                continue
            row, _reason = build_runtime_compatible_row_with_reason(
                record,
                fixed_label=fixed_label,
            )
            if row is None:
                continue

            if state.current_chunk_name is None or state.current_chunk_row_count >= output_chunk_size:
                if writer is not None:
                    close_chunk_writer(writer)
                current_chunk_path, writer = start_new_chunk(output_dir, state, row["daytime"])
            elif writer is None:
                current_chunk_path, writer = open_existing_chunk(output_dir, state)

            writer.writerow(row)
            state.current_chunk_row_count += 1
            stats.emitted_row_count += 1

        state.offset = new_offset
        save_live_state(state_path, state)
    finally:
        if writer is not None:
            close_chunk_writer(writer)

    if current_chunk_path is not None:
        print(f"[feature-export] live 出力先: {current_chunk_path}")
    print(
        "[feature-export] live 完了: "
        f"record={stats.scanned_record_count} / 出力行={stats.emitted_row_count} "
        f"/ ts不正={stats.skipped_invalid_ts_count}"
    )
    return stats


def run_live_command(args: argparse.Namespace) -> Path:
    input_dir = resolve_repo_path(args.input_dir)
    output_dir = resolve_repo_path(args.output_dir)
    runtime_settings_path = resolve_repo_path(args.runtime_settings)
    output_chunk_size = resolve_positive_int(args.output_chunk_size, field_name="--output-chunk-size")
    state_path = resolve_repo_path(args.state_path) if args.state_path else default_state_path(output_dir)

    print(
        "[feature-export] live 開始: "
        f"入力={input_dir} / 出力={output_dir} / label={args.label} / state={state_path}"
    )
    stats = export_live_conn_log_with_state(
        input_dir,
        output_dir,
        fixed_label=args.label,
        output_chunk_size=output_chunk_size,
        state_path=state_path,
    )
    if not args.no_validate and stats.emitted_row_count > 0:
        validate_runtime_csv_output(
            output_dir,
            runtime_settings_path=runtime_settings_path,
            caller_tag="[feature-export]",
        )
    elif args.no_validate:
        print("[feature-export] runtime契約チェックを設定で無効化しています")
    return output_dir


def main() -> None:
    args = parse_args()
    if args.command == "batch":
        run_batch_command(args)
        return
    if args.command == "live":
        run_live_command(args)
        return
    raise SystemExit(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    main()
