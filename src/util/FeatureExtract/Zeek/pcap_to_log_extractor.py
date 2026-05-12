#!/usr/bin/env python3
"""Convert the configured PCAP directory into Zeek JSON log directories."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TextIO


JST = timezone(timedelta(hours=9))
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[3]
SETTINGS_PATH = SCRIPT_DIR / "settings.json"


@dataclass
class ZeekRunError(Exception):
    pcap_file: Path
    returncode: int
    stderr: str

    def __str__(self) -> str:
        return format_zeek_failure(self.pcap_file, self.returncode, self.stderr)


@dataclass
class PcapToLogResult:
    batch_dir: Path
    created_dirs: list[Path]
    success_count: int
    failures: list[ZeekRunError]
    batch_dir_action: str


EXISTING_BATCH_DIR_ACTIONS = {"reuse", "replace", "abort"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Convert the configured PCAP directory into Zeek JSON logs using "
            "the current batch layout."
        )
    )
    add_existing_batch_dir_args(parser)
    return parser.parse_args()


def add_existing_batch_dir_args(parser: argparse.ArgumentParser) -> None:
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--reuse",
        dest="existing_batch_dir_action",
        action="store_const",
        const="reuse",
        help="既存の batch ディレクトリがあればそのまま使う",
    )
    group.add_argument(
        "--replace",
        dest="existing_batch_dir_action",
        action="store_const",
        const="replace",
        help="既存の batch ディレクトリがあれば削除して作り直す",
    )
    group.add_argument(
        "--abort",
        dest="existing_batch_dir_action",
        action="store_const",
        const="abort",
        help="既存の batch ディレクトリがあれば確認せず中止する",
    )


def normalize_existing_batch_dir_action(action: str | None) -> str | None:
    if action is None:
        return None
    if action not in EXISTING_BATCH_DIR_ACTIONS:
        allowed = ", ".join(sorted(EXISTING_BATCH_DIR_ACTIONS))
        raise SystemExit(f"Unsupported existing batch dir action: {action}. Expected one of: {allowed}")
    return action


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


def format_zeek_failure(pcap_file: Path, returncode: int, stderr: str) -> str:
    detail = stderr.strip() or "no stderr captured"
    return f"zeek failed for {pcap_file} (exit {returncode}): {detail}"


def is_interactive_terminal(stdin: TextIO, stdout: TextIO) -> bool:
    return bool(
        hasattr(stdin, "isatty")
        and stdin.isatty()
        and hasattr(stdout, "isatty")
        and stdout.isatty()
    )


def prompt_existing_batch_dir_action(
    batch_dir: Path,
    *,
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
) -> str:
    if stdin is None:
        stdin = sys.stdin
    if stdout is None:
        stdout = sys.stdout
    if not is_interactive_terminal(stdin, stdout):
        raise SystemExit(
            "既存のログディレクトリが見つかりましたが、非対話環境のため確認できません: "
            f"{batch_dir}"
        )

    prompt_lines = [
        "既存のログディレクトリが見つかりました:",
        f"  {batch_dir}",
        "",
        "どうしますか?",
        "  [u] 既存ディレクトリを使う",
        "  [r] 既存ディレクトリを削除して作り直す",
        "  [a] 中止する",
    ]
    stdout.write("\n".join(prompt_lines) + "\n")
    stdout.flush()

    while True:
        stdout.write("選択 (u/r/a): ")
        stdout.flush()
        answer = stdin.readline()
        if answer == "":
            raise SystemExit(
                "既存のログディレクトリに対する選択を受け取れなかったため中止しました: "
                f"{batch_dir}"
            )
        choice = answer.strip().lower()
        if choice in {"u", "use"}:
            return "reuse"
        if choice in {"r", "replace"}:
            return "replace"
        if choice in {"a", "abort"}:
            return "abort"
        stdout.write("無効な選択です。u / r / a のいずれかを入力してください。\n")
        stdout.flush()


def print_reuse_warning(batch_dir: Path, *, caller_tag: str) -> None:
    print(f"{caller_tag}[警告] 既存ディレクトリを再利用します: {batch_dir}")
    print(
        f"{caller_tag}[警告] 既存ログも後続の CSV 化対象に含まれます。"
        "今回の PCAP だけの結果にはなりません。"
    )


def prepare_batch_dir(
    batch_dir: Path,
    *,
    existing_batch_dir_action: str | None = None,
) -> str:
    existing_batch_dir_action = normalize_existing_batch_dir_action(existing_batch_dir_action)
    if batch_dir.exists():
        if not batch_dir.is_dir():
            raise SystemExit(f"Output path exists and is not a directory: {batch_dir}")
        action = existing_batch_dir_action or prompt_existing_batch_dir_action(batch_dir)
        if action == "replace":
            shutil.rmtree(batch_dir)
            batch_dir.mkdir()
            print(f"[pcap-to-log] 既存ディレクトリを削除して再作成しました: {batch_dir}")
            return action
        if action == "reuse":
            print_reuse_warning(batch_dir, caller_tag="[pcap-to-log]")
            return action
        raise SystemExit(f"ユーザー要求により中止しました: {batch_dir}")
    batch_dir.mkdir()
    return "create"


def run_zeek(pcap_file: Path, output_dir: Path) -> None:
    try:
        subprocess.run(
            ["zeek", "-r", str(pcap_file), "LogAscii::use_json=T"],
            cwd=output_dir,
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise SystemExit("zeek command not found.") from exc
    except subprocess.CalledProcessError as exc:
        raise ZeekRunError(
            pcap_file=pcap_file,
            returncode=exc.returncode,
            stderr=exc.stderr or "",
        ) from exc


def convert_pcap_dir_to_logs(
    input_path: Path,
    output_root: Path,
    *,
    existing_batch_dir_action: str | None = None,
) -> PcapToLogResult:
    pcap_files = collect_pcap_files(input_path)
    failures: list[ZeekRunError] = []
    success_count = 0
    created_dirs: list[Path] = []

    if output_root.exists() and not output_root.is_dir():
        raise SystemExit(f"Output root exists and is not a directory: {output_root}")
    output_root.mkdir(parents=True, exist_ok=True)

    batch_dir = output_root / input_path.name
    batch_dir_action = prepare_batch_dir(
        batch_dir,
        existing_batch_dir_action=existing_batch_dir_action,
    )

    print(f"[pcap-to-log] 開始: 入力={input_path} / pcap数={len(pcap_files)}")

    for index, pcap_file in enumerate(pcap_files, start=1):
        tmp_dir = batch_dir / f".tmp_{index:04d}_{sanitize_name(pcap_file.stem)}"
        final_dir: Path | None = None
        try:
            tmp_dir.mkdir()
            run_zeek(pcap_file, tmp_dir)
            output_name = ts_to_name(read_first_ts(tmp_dir), pcap_file.stem)
            final_dir = make_unique_dir(batch_dir / output_name)
            tmp_dir.rename(final_dir)
        except ZeekRunError as exc:
            failures.append(exc)
            if tmp_dir.exists():
                shutil.rmtree(tmp_dir)
            continue
        except BaseException:
            if tmp_dir.exists():
                shutil.rmtree(tmp_dir)
            raise
        success_count += 1
        created_dirs.append(final_dir)
        print(f"{pcap_file} -> {final_dir}")

    if failures:
        print(
            f"warning: skipped {len(failures)} failed PCAP file(s); "
            f"succeeded: {success_count}",
            file=sys.stderr,
        )
        for failure in failures:
            print(f"warning: {failure}", file=sys.stderr)

    print(f"[pcap-to-log] 完了: 出力先={batch_dir} / 成功={success_count} / 失敗={len(failures)}")
    return PcapToLogResult(
        batch_dir=batch_dir,
        created_dirs=created_dirs,
        success_count=success_count,
        failures=failures,
        batch_dir_action=batch_dir_action,
    )


def main() -> None:
    args = parse_args()
    settings = load_settings()
    input_path, output_root = resolve_config(settings)
    result = convert_pcap_dir_to_logs(
        input_path,
        output_root,
        existing_batch_dir_action=getattr(args, "existing_batch_dir_action", None),
    )
    print(result.batch_dir)


if __name__ == "__main__":
    main()
