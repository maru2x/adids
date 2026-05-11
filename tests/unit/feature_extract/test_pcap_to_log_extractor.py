import subprocess
from pathlib import Path

import pytest

from src.util.FeatureExtract.Zeek import pcap_to_log_extractor as extractor


# Input:
# - .pcap/.pcapng と無関係ファイルが混在する再帰ディレクトリ
# Expectation:
# - .pcap/.pcapng だけが順序付きで返る
# Target method:
# - collect_pcap_files()
# Overview:
# - 入力ディレクトリを再帰探索し、対象拡張子の PCAP だけを収集して返す。
# Note:
# - pcap_to_log 前段の入力探索契約を固定する。
def test_collect_pcap_files_recurses_and_filters_extensions(tmp_path):
    root = Path(tmp_path)
    nested = root / "nested"
    nested.mkdir()

    keep_a = root / "a.pcap"
    keep_b = nested / "b.pcapng"
    ignore = nested / "c.txt"
    keep_a.write_bytes(b"pcap")
    keep_b.write_bytes(b"pcapng")
    ignore.write_text("ignore", encoding="utf-8")

    files = extractor.collect_pcap_files(root)

    assert files == [keep_a, keep_b]


# Input:
# - 入力として単一ファイルを渡す
# Expectation:
# - ディレクトリ要求違反として SystemExit
# Target method:
# - collect_pcap_files()
# Overview:
# - 入力ディレクトリを再帰探索し、対象拡張子の PCAP だけを収集して返す。
def test_collect_pcap_files_rejects_file_input(tmp_path):
    input_file = Path(tmp_path) / "single.pcap"
    input_file.write_bytes(b"pcap")

    with pytest.raises(SystemExit, match="Expected a directory containing .pcap/.pcapng files"):
        extractor.collect_pcap_files(input_file)


# Input:
# - 存在しない入力パス
# Expectation:
# - Input path not found で SystemExit
# Target method:
# - collect_pcap_files()
# Overview:
# - 入力ディレクトリを再帰探索し、対象拡張子の PCAP だけを収集して返す。
def test_collect_pcap_files_rejects_missing_input(tmp_path):
    with pytest.raises(SystemExit, match="Input path not found"):
        extractor.collect_pcap_files(Path(tmp_path) / "missing")


# Input:
# - relative path と差し替えた PROJECT_ROOT
# Expectation:
# - カレントディレクトリではなく PROJECT_ROOT 基準で解決される
# Target method:
# - resolve_repo_path()
# Overview:
# - settings 上のパス文字列を repo root 基準の絶対 Path に解決する。
def test_resolve_repo_path_uses_project_root_for_relative_paths(monkeypatch, tmp_path):
    root = Path(tmp_path)
    monkeypatch.setattr(extractor, "PROJECT_ROOT", root)

    resolved = extractor.resolve_repo_path("data/pcap/sample", field_name="PcapToLog.INPUT_DIR_PATH")

    assert resolved == (root / "data/pcap/sample").resolve()


# Input:
# - ts の順序が逆転している log dir
# Expectation:
# - 全 log 中の最小 ts が返る
# Target method:
# - read_first_ts()
# Overview:
# - 出力された JSON log 群を走査し、最小の ts を最終ディレクトリ名の元として返す。
# Note:
# - 最終ディレクトリ名の timestamp 決定ロジックの基礎。
def test_read_first_ts_returns_smallest_timestamp(tmp_path):
    log_dir = Path(tmp_path) / "logs"
    log_dir.mkdir()
    (log_dir / "conn.log").write_text(
        "\n".join(
            [
                '{"ts": 1640995210, "uid": "B"}',
                '{"ts": 1640995200, "uid": "A"}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    assert extractor.read_first_ts(log_dir) == 1640995200


# Input:
# - base dir と base_01 がすでに存在する出力先
# Expectation:
# - 次の空き suffix として _02 が選ばれる
# Target method:
# - make_unique_dir()
# Overview:
# - 既存ディレクトリと衝突しない最終出力ディレクトリ名を suffix 付きで決める。
def test_make_unique_dir_adds_numeric_suffix(tmp_path):
    base = Path(tmp_path) / "20220101000000"
    base.mkdir()
    (Path(tmp_path) / "20220101000000_01").mkdir()

    assert extractor.make_unique_dir(base) == Path(tmp_path) / "20220101000000_02"


# Input:
# - subprocess.run が FileNotFoundError を投げる zeek 実行
# Expectation:
# - zeek command not found として SystemExit
# Target method:
# - run_zeek()
# Overview:
# - zeek コマンドを外部実行し、指定ディレクトリに JSON log を生成させる wrapper。
def test_run_zeek_reports_missing_command(monkeypatch, tmp_path):
    def raise_missing(*args, **kwargs):
        raise FileNotFoundError()

    monkeypatch.setattr(extractor.subprocess, "run", raise_missing)

    with pytest.raises(SystemExit, match="zeek command not found"):
        extractor.run_zeek(Path(tmp_path) / "sample.pcap", Path(tmp_path))


# Input:
# - subprocess.run が CalledProcessError を投げる zeek 実行
# Expectation:
# - zeek failed for として SystemExit
# Target method:
# - run_zeek()
# Overview:
# - zeek コマンドを外部実行し、指定ディレクトリに JSON log を生成させる wrapper。
# Note:
# - wrapper が外部コマンド失敗を握り潰さないことを確認する。
def test_run_zeek_reports_called_process_error(monkeypatch, tmp_path):
    def raise_called_process_error(*args, **kwargs):
        raise subprocess.CalledProcessError(1, ["zeek"])

    monkeypatch.setattr(extractor.subprocess, "run", raise_called_process_error)

    with pytest.raises(SystemExit, match="zeek failed for"):
        extractor.run_zeek(Path(tmp_path) / "sample.pcap", Path(tmp_path))
