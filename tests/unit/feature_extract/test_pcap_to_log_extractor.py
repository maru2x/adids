import subprocess
from pathlib import Path

import pytest

from src.util.FeatureExtract.Zeek import pcap_to_log_extractor as extractor


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


def test_collect_pcap_files_rejects_file_input(tmp_path):
    input_file = Path(tmp_path) / "single.pcap"
    input_file.write_bytes(b"pcap")

    with pytest.raises(SystemExit, match="Expected a directory containing .pcap/.pcapng files"):
        extractor.collect_pcap_files(input_file)


def test_collect_pcap_files_rejects_missing_input(tmp_path):
    with pytest.raises(SystemExit, match="Input path not found"):
        extractor.collect_pcap_files(Path(tmp_path) / "missing")


def test_resolve_repo_path_uses_project_root_for_relative_paths(monkeypatch, tmp_path):
    root = Path(tmp_path)
    monkeypatch.setattr(extractor, "PROJECT_ROOT", root)

    resolved = extractor.resolve_repo_path("data/pcap/sample", field_name="PcapToLog.INPUT_DIR_PATH")

    assert resolved == (root / "data/pcap/sample").resolve()


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


def test_make_unique_dir_adds_numeric_suffix(tmp_path):
    base = Path(tmp_path) / "20220101000000"
    base.mkdir()
    (Path(tmp_path) / "20220101000000_01").mkdir()

    assert extractor.make_unique_dir(base) == Path(tmp_path) / "20220101000000_02"


def test_run_zeek_reports_missing_command(monkeypatch, tmp_path):
    def raise_missing(*args, **kwargs):
        raise FileNotFoundError()

    monkeypatch.setattr(extractor.subprocess, "run", raise_missing)

    with pytest.raises(SystemExit, match="zeek command not found"):
        extractor.run_zeek(Path(tmp_path) / "sample.pcap", Path(tmp_path))


def test_run_zeek_reports_called_process_error(monkeypatch, tmp_path):
    def raise_called_process_error(*args, **kwargs):
        raise subprocess.CalledProcessError(1, ["zeek"])

    monkeypatch.setattr(extractor.subprocess, "run", raise_called_process_error)

    with pytest.raises(SystemExit, match="zeek failed for"):
        extractor.run_zeek(Path(tmp_path) / "sample.pcap", Path(tmp_path))
