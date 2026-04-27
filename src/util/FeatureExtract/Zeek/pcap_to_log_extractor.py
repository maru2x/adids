#!/usr/bin/env python3
"""Convert the configured PCAP directory into Zeek JSON log directories."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


JST = timezone(timedelta(hours=9))
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[3]
SETTINGS_PATH = SCRIPT_DIR / "settings.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Convert the configured PCAP directory into Zeek JSON logs using "
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


def resolve_config(settings: dict) -> tuple[Path, Path]:
    section = settings.get("PcapToLog")
    if not isinstance(section, dict):
        raise SystemExit(f"PcapToLog section not found in {SETTINGS_PATH}")
    input_path = resolve_repo_path(section.get("INPUT_DIR_PATH", ""), field_name="PcapToLog.INPUT_DIR_PATH")
    output_root = resolve_repo_path(
        section.get("OUTPUT_ROOT_DIR_PATH", ""),
        field_name="PcapToLog.OUTPUT_ROOT_DIR_PATH",
    )
    return input_path, output_root


def collect_pcap_files(input_path: Path) -> list[Path]:
    if input_path.is_file():
        raise SystemExit(f"Expected a directory containing .pcap/.pcapng files: {input_path}")
    if input_path.is_dir():
        files = sorted(
            p
            for p in input_path.rglob("*")
            if p.is_file() and p.suffix.lower() in {".pcap", ".pcapng"}
        )
        if files:
            return files
        raise SystemExit(f"No .pcap/.pcapng files were found under {input_path}")
    raise SystemExit(f"Input path not found: {input_path}")


def sanitize_name(name: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in name)
    return safe.strip("_") or "unknown"


def read_first_ts(log_dir: Path) -> float | None:
    first_ts = None
    for log_file in sorted(log_dir.glob("*.log")):
        with log_file.open("r", encoding="utf-8") as fh:
            for line_number, line in enumerate(fh, start=1):
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    record = json.loads(stripped)
                except json.JSONDecodeError as exc:
                    raise SystemExit(
                        f"Invalid JSON in {log_file}:{line_number}: {exc}"
                    ) from exc
                raw_ts = record.get("ts")
                if raw_ts in (None, ""):
                    continue
                try:
                    ts = float(raw_ts)
                except (TypeError, ValueError):
                    continue
                if first_ts is None or ts < first_ts:
                    first_ts = ts
    return first_ts


def ts_to_name(ts: float | None, fallback: str) -> str:
    if ts is None:
        return sanitize_name(fallback)
    dt = datetime.fromtimestamp(ts, tz=timezone.utc).astimezone(JST)
    return dt.strftime("%Y%m%d%H%M%S")


def make_unique_dir(path: Path) -> Path:
    if not path.exists():
        return path
    suffix = 1
    while True:
        candidate = path.with_name(f"{path.name}_{suffix:02d}")
        if not candidate.exists():
            return candidate
        suffix += 1


def run_zeek(pcap_file: Path, output_dir: Path) -> None:
    try:
        subprocess.run(
            ["zeek", "-r", str(pcap_file), "LogAscii::use_json=T"],
            cwd=output_dir,
            check=True,
        )
    except FileNotFoundError as exc:
        raise SystemExit("zeek command not found.") from exc
    except subprocess.CalledProcessError as exc:
        raise SystemExit(f"zeek failed for {pcap_file}: {exc}") from exc


def main() -> None:
    parse_args()
    settings = load_settings()
    input_path, output_root = resolve_config(settings)
    pcap_files = collect_pcap_files(input_path)

    if output_root.exists() and not output_root.is_dir():
        raise SystemExit(f"Output root exists and is not a directory: {output_root}")
    output_root.mkdir(parents=True, exist_ok=True)

    batch_dir = output_root / input_path.name
    if batch_dir.exists():
        if not batch_dir.is_dir():
            raise SystemExit(f"Output path exists and is not a directory: {batch_dir}")
        print(f"warning: output directory already exists: {batch_dir}", file=sys.stderr)
    else:
        batch_dir.mkdir()

    for index, pcap_file in enumerate(pcap_files, start=1):
        tmp_dir = batch_dir / f".tmp_{index:04d}_{sanitize_name(pcap_file.stem)}"
        final_dir: Path | None = None
        try:
            tmp_dir.mkdir()
            run_zeek(pcap_file, tmp_dir)
            output_name = ts_to_name(read_first_ts(tmp_dir), pcap_file.stem)
            final_dir = make_unique_dir(batch_dir / output_name)
            tmp_dir.rename(final_dir)
        except BaseException:
            if tmp_dir.exists():
                shutil.rmtree(tmp_dir)
            raise
        print(f"{pcap_file} -> {final_dir}")

    print(batch_dir)


if __name__ == "__main__":
    main()
