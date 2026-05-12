import io
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.util.FeatureExtract.Zeek import pcap_to_log_extractor as extractor


class FakeTty(io.StringIO):
    def isatty(self):
        return True


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


def test_resolve_config_returns_input_and_output_paths(monkeypatch, tmp_path):
    root = Path(tmp_path)
    monkeypatch.setattr(extractor, "PROJECT_ROOT", root)

    input_path, output_root = extractor.resolve_config(
        {
            "PcapToLog": {
                "INPUT_DIR_PATH": "data/pcap/sample",
                "OUTPUT_ROOT_DIR_PATH": "data/logs/sample",
            }
        }
    )

    assert input_path == (root / "data/pcap/sample").resolve()
    assert output_root == (root / "data/logs/sample").resolve()


def test_prompt_existing_batch_dir_action_retries_until_valid_choice(tmp_path):
    batch_dir = Path(tmp_path) / "sample_batch"
    batch_dir.mkdir()
    stdin = FakeTty("x\nu\n")
    stdout = FakeTty()

    action = extractor.prompt_existing_batch_dir_action(batch_dir, stdin=stdin, stdout=stdout)

    assert action == "reuse"
    output = stdout.getvalue()
    assert "既存のログディレクトリが見つかりました" in output
    assert "無効な選択です" in output


def test_prompt_existing_batch_dir_action_rejects_non_interactive_mode(tmp_path):
    batch_dir = Path(tmp_path) / "sample_batch"
    batch_dir.mkdir()

    with pytest.raises(SystemExit, match="非対話環境のため確認できません"):
        extractor.prompt_existing_batch_dir_action(
            batch_dir,
            stdin=io.StringIO(),
            stdout=io.StringIO(),
        )


def test_prepare_batch_dir_reuses_existing_dir_after_confirmation(tmp_path, monkeypatch, capsys):
    batch_dir = Path(tmp_path) / "sample_batch"
    batch_dir.mkdir()
    existing_file = batch_dir / "keep.txt"
    existing_file.write_text("keep", encoding="utf-8")
    monkeypatch.setattr(extractor, "prompt_existing_batch_dir_action", lambda *_args, **_kwargs: "reuse")

    action = extractor.prepare_batch_dir(batch_dir)

    assert action == "reuse"
    assert existing_file.is_file()
    assert "既存ディレクトリを再利用します" in capsys.readouterr().out


def test_prepare_batch_dir_reuses_existing_dir_with_explicit_action_without_prompt(tmp_path, monkeypatch, capsys):
    batch_dir = Path(tmp_path) / "sample_batch"
    batch_dir.mkdir()
    existing_file = batch_dir / "keep.txt"
    existing_file.write_text("keep", encoding="utf-8")
    monkeypatch.setattr(
        extractor,
        "prompt_existing_batch_dir_action",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("prompt should not be called")),
    )

    action = extractor.prepare_batch_dir(batch_dir, existing_batch_dir_action="reuse")

    assert action == "reuse"
    assert existing_file.is_file()
    captured = capsys.readouterr().out
    assert "既存ディレクトリを再利用します" in captured
    assert "今回の PCAP だけの結果にはなりません" in captured


def test_prepare_batch_dir_replaces_existing_dir_after_confirmation(tmp_path, monkeypatch, capsys):
    batch_dir = Path(tmp_path) / "sample_batch"
    batch_dir.mkdir()
    (batch_dir / "stale.txt").write_text("stale", encoding="utf-8")
    monkeypatch.setattr(extractor, "prompt_existing_batch_dir_action", lambda *_args, **_kwargs: "replace")

    action = extractor.prepare_batch_dir(batch_dir)

    assert action == "replace"
    assert batch_dir.is_dir()
    assert not any(batch_dir.iterdir())
    assert "削除して再作成しました" in capsys.readouterr().out


def test_prepare_batch_dir_replaces_existing_dir_with_explicit_action_without_prompt(tmp_path, monkeypatch):
    batch_dir = Path(tmp_path) / "sample_batch"
    batch_dir.mkdir()
    (batch_dir / "stale.txt").write_text("stale", encoding="utf-8")
    monkeypatch.setattr(
        extractor,
        "prompt_existing_batch_dir_action",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("prompt should not be called")),
    )

    action = extractor.prepare_batch_dir(batch_dir, existing_batch_dir_action="replace")

    assert action == "replace"
    assert batch_dir.is_dir()
    assert not any(batch_dir.iterdir())


def test_prepare_batch_dir_aborts_when_user_requests_abort(tmp_path, monkeypatch):
    batch_dir = Path(tmp_path) / "sample_batch"
    batch_dir.mkdir()
    monkeypatch.setattr(extractor, "prompt_existing_batch_dir_action", lambda *_args, **_kwargs: "abort")

    with pytest.raises(SystemExit, match="ユーザー要求により中止しました"):
        extractor.prepare_batch_dir(batch_dir)


def test_prepare_batch_dir_aborts_with_explicit_action_without_prompt(tmp_path, monkeypatch):
    batch_dir = Path(tmp_path) / "sample_batch"
    batch_dir.mkdir()
    monkeypatch.setattr(
        extractor,
        "prompt_existing_batch_dir_action",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("prompt should not be called")),
    )

    with pytest.raises(SystemExit, match="ユーザー要求により中止しました"):
        extractor.prepare_batch_dir(batch_dir, existing_batch_dir_action="abort")


def test_normalize_existing_batch_dir_action_rejects_unknown_value():
    with pytest.raises(SystemExit, match="Unsupported existing batch dir action"):
        extractor.normalize_existing_batch_dir_action("keep")


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
# - stderr を含む ZeekRunError が送出される
# Target method:
# - run_zeek()
# Overview:
# - zeek コマンドを外部実行し、指定ディレクトリに JSON log を生成させる wrapper。
# Note:
# - wrapper が外部コマンド失敗の詳細を落とさないことを確認する。
def test_run_zeek_reports_called_process_error(monkeypatch, tmp_path):
    def raise_called_process_error(*args, **kwargs):
        raise subprocess.CalledProcessError(1, ["zeek"], stderr="truncated dump file")

    monkeypatch.setattr(extractor.subprocess, "run", raise_called_process_error)

    with pytest.raises(extractor.ZeekRunError, match="truncated dump file"):
        extractor.run_zeek(Path(tmp_path) / "sample.pcap", Path(tmp_path))


def test_main_passes_existing_batch_dir_action_from_cli(tmp_path, monkeypatch, capsys):
    input_dir = Path(tmp_path) / "pcap" / "sample_batch"
    input_dir.mkdir(parents=True)
    (input_dir / "good.pcap").write_bytes(b"good")
    output_root = Path(tmp_path) / "logs"
    monkeypatch.setattr(extractor, "parse_args", lambda: SimpleNamespace(existing_batch_dir_action="replace"))
    monkeypatch.setattr(
        extractor,
        "load_settings",
        lambda: {
            "PcapToLog": {
                "INPUT_DIR_PATH": str(input_dir),
                "OUTPUT_ROOT_DIR_PATH": str(output_root),
            }
        },
    )

    captured = {}

    def fake_convert(input_path, output_root_path, *, existing_batch_dir_action=None):
        captured["input_path"] = input_path
        captured["output_root"] = output_root_path
        captured["existing_batch_dir_action"] = existing_batch_dir_action
        batch_dir = output_root_path / input_path.name
        batch_dir.mkdir(parents=True, exist_ok=True)
        return extractor.PcapToLogResult(
            batch_dir=batch_dir,
            created_dirs=[],
            success_count=0,
            failures=[],
            batch_dir_action=existing_batch_dir_action or "create",
        )

    monkeypatch.setattr(extractor, "convert_pcap_dir_to_logs", fake_convert)

    extractor.main()

    assert captured["input_path"] == input_dir.resolve()
    assert captured["output_root"] == output_root.resolve()
    assert captured["existing_batch_dir_action"] == "replace"
    assert str((output_root / input_dir.name).resolve()) in capsys.readouterr().out


def test_main_skips_failed_pcap_and_continues(tmp_path, monkeypatch, capsys):
    input_dir = Path(tmp_path) / "pcap" / "sample_batch"
    input_dir.mkdir(parents=True)
    bad_pcap = input_dir / "bad.pcap"
    good_pcap = input_dir / "good.pcap"
    bad_pcap.write_bytes(b"bad")
    good_pcap.write_bytes(b"good")
    output_root = Path(tmp_path) / "logs"

    monkeypatch.setattr(extractor, "parse_args", lambda: None)
    monkeypatch.setattr(
        extractor,
        "load_settings",
        lambda: {
            "PcapToLog": {
                "INPUT_DIR_PATH": str(input_dir),
                "OUTPUT_ROOT_DIR_PATH": str(output_root),
            }
        },
    )

    def fake_run_zeek(pcap_file, output_dir):
        if pcap_file.name == "bad.pcap":
            raise extractor.ZeekRunError(pcap_file, 1, "truncated dump file")
        (output_dir / "conn.log").write_text('{"ts": 1640995200}\n', encoding="utf-8")

    monkeypatch.setattr(extractor, "run_zeek", fake_run_zeek)

    extractor.main()

    batch_dir = output_root / input_dir.name
    assert (batch_dir / "20220101090000" / "conn.log").is_file()
    assert not any(path.name.startswith(".tmp_") for path in batch_dir.iterdir())

    captured = capsys.readouterr()
    assert "skipped 1 failed PCAP file" in captured.err
    assert str(bad_pcap) in captured.err
    assert "truncated dump file" in captured.err
    assert str(batch_dir) in captured.out
