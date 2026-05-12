import csv
import json
from pathlib import Path

import pytest

from src.util.FeatureExtract.Zeek import log_to_csv_extractor as extractor

# zeek log から csv ファイルを抽出する処理が想定どおりの挙動で動いているか？をテストする pytest

def read_csv_rows(path):
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def network_conf():
    return {
        "BENIGN": ["192.168.0.0/24"],
        "MALICIOUS": ["10.0.0.0/24"],
        "EXCEPTION": ["192.168.0.200/32"],
    }


ROOT_DIR = Path(__file__).resolve().parents[3]
FIXTURE_DIR = ROOT_DIR / "tests" / "fixtures" / "zeek_logs"


# Input:
# - 通信の送受信 IP と network_conf
# Expectation:
# - malicious を含む通信は 1
# - benign <-> external は 0
# - benign <-> benign / external <-> external / IP 欠損は None
# Target method:
# - assign_label()
# Overview:
# - record(入力されたlog一行のこと) の送受信 IP を BENIGN / MALICIOUS network と照合して 0 / 1 / None を返す。
# Note:
# - assign_label() の分岐表そのものを固定するテスト。
@pytest.mark.parametrize(
    ("record", "expected"),
    [
        ({"id.orig_h": "10.0.0.10", "id.resp_h": "8.8.8.8"}, 1),
        ({"id.orig_h": "192.168.0.10", "id.resp_h": "8.8.8.8"}, 0),
        ({"id.orig_h": "8.8.8.8", "id.resp_h": "192.168.0.10"}, 0),
        ({"id.orig_h": "192.168.0.10", "id.resp_h": "192.168.0.20"}, None),
        ({"id.orig_h": "8.8.8.8", "id.resp_h": "1.1.1.1"}, None),
        ({"id.orig_h": "192.168.0.10"}, None),
    ],
)
def test_assign_label_covers_malicious_benign_and_unknown_cases(record, expected):
    assert extractor.assign_label(record, network_conf()) == expected


# Input:
# - record の送受信 IP と exception network
# Expectation:
# - EXCEPTION に当たる通信だけ True
# - 不正 IP や片側欠損では落ちずに False
# Target method:
# - should_exclude_record()
# Overview:
# - record が EXCEPTION network を含むかだけを判定し、CSV 出力前に除外すべきか返す。
# Note:
# - _ip_in_any() の失敗耐性も間接的に見ている。
@pytest.mark.parametrize(
    ("record", "expected"),
    [
        ({"id.orig_h": "192.168.0.200", "id.resp_h": "8.8.8.8"}, True),
        ({"id.orig_h": "8.8.8.8", "id.resp_h": "192.168.0.200"}, True),
        ({"id.orig_h": "not-an-ip", "id.resp_h": "8.8.8.8"}, False),
        ({"id.orig_h": "192.168.0.10"}, False),
    ],
)
def test_should_exclude_record_uses_exception_networks_and_ignores_invalid_ips(record, expected):
    assert extractor.should_exclude_record(record, network_conf()) is expected


# Input:
# - key 集合が異なる 2 record
# Expectation:
# - ts は daytime に変換される
# - key は出現順の union になる
# - label が末尾に追加される
# Target method:
# - collect_header()
# Overview:
# - JSON record 群から CSV header を組み立て、ts を daytime に読み替える。
# Note:
# - CSV schema を決める collect_header() の基本契約。
def test_collect_header_renames_ts_merges_keys_and_appends_label():
    header = extractor.collect_header(
        [
            {"ts": 1640995200, "uid": "A"},
            {"duration": 1.5, "service": "dns"},
        ]
    )

    assert header == ["daytime", "uid", "duration", "service", "label"]


# Input:
# - record が 1 件もない
# Expectation:
# - 現実装どおり ["label"] を返す
# Target method:
# - collect_header()
# Overview:
# - JSON record 群から CSV header を組み立て、空入力時の現挙動も含めて返す。
# Note:
# - 理想仕様かどうかではなく、現状挙動の固定が目的。
def test_collect_header_returns_label_only_for_empty_records():
    assert extractor.collect_header([]) == ["label"]


# Input:
# - conn.log 由来だが duration や byte 列を持たない sparse record
# Expectation:
# - runtime 必須列が header に補完される
# - label も含まれる
# Target method:
# - collect_header()
# Overview:
# - conn.log を CSV 化するとき、Zeek record に存在しない列でも runtime 契約上必要な列を落とさない。
def test_collect_header_adds_conn_required_columns_for_sparse_conn_records():
    header = extractor.collect_header(
        [
            {
                "ts": 1640995200,
                "uid": "A",
                "id.orig_h": "192.168.0.10",
                "id.resp_h": "9.9.9.9",
                "proto": "udp",
                "conn_state": "S0",
                "local_orig": True,
                "local_resp": False,
                "missed_bytes": 0,
                "history": "D",
                "orig_pkts": 1,
                "orig_ip_bytes": 29,
                "resp_pkts": 0,
                "resp_ip_bytes": 0,
            }
        ],
        ["conn.log"],
    )

    for column in extractor.CONN_REQUIRED_COLUMNS:
        assert column in header


# Input:
# - 重複を含む TARGET_LOGS
# Expectation:
# - 順序を保ったまま重複だけ落とす
# Target method:
# - normalize_target_logs()
# Overview:
# - settings 由来の TARGET_LOGS を検証しつつ、重複を除いた log 名配列に正規化する。
def test_normalize_target_logs_deduplicates_entries():
    assert extractor.normalize_target_logs(["conn.log", "dns.log", "conn.log"]) == [
        "conn.log",
        "dns.log",
    ]


# Input:
# - TARGET_LOGS として不正な値
# Expectation:
# - 設定エラーとして SystemExit
# Target method:
# - normalize_target_logs()
# Overview:
# - settings 由来の TARGET_LOGS が「空でない文字列配列」であることを強制する。
# Note:
# - 空配列、空文字、非文字列を弾く契約。
@pytest.mark.parametrize("target_logs", [None, [], [""], ["conn.log", None]])
def test_normalize_target_logs_rejects_invalid_values(target_logs):
    with pytest.raises(SystemExit, match="LogToCsv.TARGET_LOGS"):
        extractor.normalize_target_logs(target_logs)


# Input:
# - すでに conn.log を含む単一 log dir
# Expectation:
# - その dir 自身が処理対象として返る
# - batch_name は親ディレクトリ名になる
# Target method:
# - discover_log_dirs()
# Overview:
# - 入力が単一 log dir か batch dir かを判定し、処理対象 dir 群と batch 名を返す。
def test_discover_log_dirs_accepts_single_log_dir(tmp_path):
    log_dir = Path(tmp_path) / "batch_a" / "20220101000000"
    log_dir.mkdir(parents=True)
    (log_dir / "conn.log").write_text("{}\n", encoding="utf-8")

    log_dirs, batch_name = extractor.discover_log_dirs(log_dir, ["conn.log"])

    assert log_dirs == [log_dir]
    assert batch_name == "batch_a"


# Input:
# - 親 dir の下に複数 timestamp dir と無関係 dir がある batch layout
# Expectation:
# - target log を持つ dir だけが順序付きで返る
# - batch_name は入力 dir 名になる
# Target method:
# - discover_log_dirs()
# Overview:
# - 入力が単一 log dir か batch dir かを判定し、処理対象 dir 群と batch 名を返す。
def test_discover_log_dirs_accepts_batch_dir(tmp_path):
    batch_dir = Path(tmp_path) / "batch_a"
    first = batch_dir / "20220101000000"
    second = batch_dir / "20220101000001"
    ignored = batch_dir / "notes"
    first.mkdir(parents=True)
    second.mkdir()
    ignored.mkdir()
    (first / "conn.log").write_text("{}\n", encoding="utf-8")
    (second / "conn.log").write_text("{}\n", encoding="utf-8")

    log_dirs, batch_name = extractor.discover_log_dirs(batch_dir, ["conn.log"])

    assert log_dirs == [first, second]
    assert batch_name == "batch_a"


# Input:
# - target log を含まない空ディレクトリ
# Expectation:
# - 無言で空処理せず SystemExit
# Target method:
# - discover_log_dirs()
# Overview:
# - 入力が単一 log dir か batch dir かを判定し、処理対象が無ければ失敗する。
def test_discover_log_dirs_rejects_directories_without_target_logs(tmp_path):
    empty_dir = Path(tmp_path) / "empty"
    empty_dir.mkdir()

    with pytest.raises(SystemExit, match="No log directories were found"):
        extractor.discover_log_dirs(empty_dir, ["conn.log"])


# Input:
# - 2 行目だけ壊れた JSON log
# Expectation:
# - file path と line number を含む SystemExit
# Target method:
# - iter_records()
# Overview:
# - 対象 log file 群を JSON Lines として順に読み、壊れた行では即時に失敗する。
# Note:
# - 失敗時の診断性を守るテスト。
def test_iter_records_reports_invalid_json_line_number(tmp_path):
    log_file = Path(tmp_path) / "conn.log"
    log_file.write_text('{"ts": 1}\nnot-json\n', encoding="utf-8")

    with pytest.raises(SystemExit, match=r"Invalid JSON in .*conn\.log:2"):
        list(extractor.iter_records([log_file]))


def test_convert_batch_to_chunked_csv_merges_log_dirs_in_global_daytime_order(tmp_path):
    root = Path(tmp_path)
    batch_dir = root / "logs" / "batch_a"
    first_dir = batch_dir / "20220101090000"
    second_dir = batch_dir / "20220101090001"
    first_dir.mkdir(parents=True)
    second_dir.mkdir()
    destination_dir = root / "csv" / "conn" / "batch_a"

    (first_dir / "conn.log").write_text(
        json.dumps(
            {
                "ts": 1640995200,
                "duration": 10,
                "uid": "late-end",
                "id.orig_h": "192.168.0.10",
                "id.resp_h": "8.8.8.8",
                "conn_state": "SF",
                "local_orig": True,
                "local_resp": False,
                "missed_bytes": 0,
                "orig_pkts": 1,
                "resp_pkts": 1,
                "orig_ip_bytes": 29,
                "resp_ip_bytes": 29,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (second_dir / "conn.log").write_text(
        json.dumps(
            {
                "ts": 1640995201,
                "duration": 1,
                "uid": "early-end",
                "id.orig_h": "192.168.0.20",
                "id.resp_h": "1.1.1.1",
                "conn_state": "SF",
                "local_orig": True,
                "local_resp": False,
                "missed_bytes": 0,
                "orig_pkts": 1,
                "resp_pkts": 1,
                "orig_ip_bytes": 29,
                "resp_ip_bytes": 29,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    created_files = extractor.convert_batch_to_chunked_csv(
        [first_dir, second_dir],
        destination_dir,
        network_conf(),
        "conn.log",
        output_chunk_size=10,
        run_row_limit=100,
        merge_fan_in=2,
    )

    assert [path.name for path in created_files] == ["00000_20220101090002.csv"]
    rows = read_csv_rows(created_files[0])
    assert [row["uid"] for row in rows] == ["early-end", "late-end"]
    assert [row["daytime"] for row in rows] == [
        "2022-01-01 09:00:02",
        "2022-01-01 09:00:10",
    ]


def test_convert_batch_to_chunked_csv_fails_when_all_rows_are_filtered(tmp_path):
    root = Path(tmp_path)
    log_dir = root / "logs" / "batch_a" / "20220101090000"
    log_dir.mkdir(parents=True)
    destination_dir = root / "csv" / "conn" / "batch_a"

    (log_dir / "conn.log").write_text(
        json.dumps(
            {
                "ts": 1640995200,
                "duration": 1,
                "uid": "skip-exception",
                "id.orig_h": "192.168.0.200",
                "id.resp_h": "8.8.8.8",
                "conn_state": "SF",
                "local_orig": True,
                "local_resp": False,
                "missed_bytes": 0,
                "orig_pkts": 1,
                "resp_pkts": 1,
                "orig_ip_bytes": 29,
                "resp_ip_bytes": 29,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(SystemExit, match="No CSV rows were produced for conn\\.log after filtering and labeling"):
        extractor.convert_batch_to_chunked_csv(
            [log_dir],
            destination_dir,
            network_conf(),
            "conn.log",
            output_chunk_size=10,
            run_row_limit=100,
            merge_fan_in=2,
        )


def test_convert_batch_to_chunked_csv_streams_records_without_old_helper(tmp_path, monkeypatch):
    root = Path(tmp_path)
    log_dir = root / "logs" / "batch_a" / "20220101090000"
    log_dir.mkdir(parents=True)
    destination_dir = root / "csv" / "conn" / "batch_a"

    (log_dir / "conn.log").write_text(
        json.dumps(
            {
                "ts": 1640995200,
                "duration": 1,
                "uid": "streamed-row",
                "id.orig_h": "192.168.0.10",
                "id.resp_h": "8.8.8.8",
                "conn_state": "SF",
                "local_orig": True,
                "local_resp": False,
                "missed_bytes": 0,
                "orig_pkts": 1,
                "resp_pkts": 1,
                "orig_ip_bytes": 29,
                "resp_ip_bytes": 29,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    def fail_convert_log_dir(*_args, **_kwargs):
        raise AssertionError("convert_log_dir() should not be used by convert_batch_to_chunked_csv")

    monkeypatch.setattr(extractor, "convert_log_dir", fail_convert_log_dir, raising=False)

    created_files = extractor.convert_batch_to_chunked_csv(
        [log_dir],
        destination_dir,
        network_conf(),
        "conn.log",
        output_chunk_size=10,
        run_row_limit=1,
        merge_fan_in=2,
    )

    assert [path.name for path in created_files] == ["00000_20220101090001.csv"]
    rows = read_csv_rows(created_files[0])
    assert [row["uid"] for row in rows] == ["streamed-row"]


def test_convert_batch_to_chunked_csv_preserves_conn_required_columns_in_streaming_path(tmp_path):
    root = Path(tmp_path)
    log_dir = root / "logs" / "batch_a" / "20220101090000"
    log_dir.mkdir(parents=True)
    destination_dir = root / "csv" / "conn" / "batch_a"

    (log_dir / "conn.log").write_text(
        json.dumps(
            {
                "ts": 1640995200,
                "uid": "missing-duration",
                "id.orig_h": "192.168.0.10",
                "id.resp_h": "8.8.8.8",
                "conn_state": "SF",
                "local_orig": True,
                "local_resp": False,
                "missed_bytes": 0,
                "orig_pkts": 1,
                "resp_pkts": 1,
                "orig_ip_bytes": 29,
                "resp_ip_bytes": 29,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    created_files = extractor.convert_batch_to_chunked_csv(
        [log_dir],
        destination_dir,
        network_conf(),
        "conn.log",
        output_chunk_size=10,
        run_row_limit=1,
        merge_fan_in=2,
    )

    rows = read_csv_rows(created_files[0])
    assert len(rows) == 1
    row = rows[0]
    for column in extractor.CONN_REQUIRED_COLUMNS:
        assert column in row
    assert row["duration"] == "0"


def test_convert_batch_to_chunked_csv_handles_multi_run_multi_level_merge_and_multi_chunk_output(tmp_path):
    root = Path(tmp_path)
    batch_dir = root / "logs" / "batch_a"
    destination_dir = root / "csv" / "conn" / "batch_a"
    records = [
        ("20220101090005", 1640995204, "u4"),
        ("20220101090001", 1640995200, "u0"),
        ("20220101090003", 1640995202, "u2"),
        ("20220101090002", 1640995201, "u1"),
        ("20220101090004", 1640995203, "u3"),
    ]

    log_dirs = []
    for dir_name, ts, uid in records:
        log_dir = batch_dir / dir_name
        log_dir.mkdir(parents=True, exist_ok=True)
        (log_dir / "conn.log").write_text(
            json.dumps(
                {
                    "ts": ts,
                    "duration": 1,
                    "uid": uid,
                    "id.orig_h": "192.168.0.10",
                    "id.resp_h": "8.8.8.8",
                    "conn_state": "SF",
                    "local_orig": True,
                    "local_resp": False,
                    "missed_bytes": 0,
                    "orig_pkts": 1,
                    "resp_pkts": 1,
                    "orig_ip_bytes": 29,
                    "resp_ip_bytes": 29,
                }
            )
            + "\n",
            encoding="utf-8",
        )
        log_dirs.append(log_dir)

    created_files = extractor.convert_batch_to_chunked_csv(
        log_dirs,
        destination_dir,
        network_conf(),
        "conn.log",
        output_chunk_size=2,
        run_row_limit=1,
        merge_fan_in=2,
    )

    assert [path.name for path in created_files] == [
        "00000_20220101090001.csv",
        "00001_20220101090003.csv",
        "00002_20220101090005.csv",
    ]
    rows = []
    for path in created_files:
        rows.extend(read_csv_rows(path))
    assert [row["uid"] for row in rows] == ["u0", "u1", "u2", "u3", "u4"]
    assert [row["daytime"] for row in rows] == [
        "2022-01-01 09:00:01",
        "2022-01-01 09:00:02",
        "2022-01-01 09:00:03",
        "2022-01-01 09:00:04",
        "2022-01-01 09:00:05",
    ]


def test_convert_batch_to_chunked_csv_preserves_existing_outputs_when_conversion_fails(tmp_path):
    root = Path(tmp_path)
    log_dir = root / "logs" / "batch_a" / "20220101090000"
    log_dir.mkdir(parents=True)
    destination_dir = root / "csv" / "conn" / "batch_a"
    destination_dir.mkdir(parents=True)
    stale_csv = destination_dir / "stale.csv"
    stale_csv.write_text("daytime,label\n2022-01-01 09:00:00,0\n", encoding="utf-8")

    (log_dir / "conn.log").write_text(
        json.dumps(
            {
                "ts": 1640995200,
                "duration": 1,
                "uid": "skip-exception",
                "id.orig_h": "192.168.0.200",
                "id.resp_h": "8.8.8.8",
                "conn_state": "SF",
                "local_orig": True,
                "local_resp": False,
                "missed_bytes": 0,
                "orig_pkts": 1,
                "resp_pkts": 1,
                "orig_ip_bytes": 29,
                "resp_ip_bytes": 29,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(SystemExit, match="No CSV rows were produced for conn\\.log after filtering and labeling"):
        extractor.convert_batch_to_chunked_csv(
            [log_dir],
            destination_dir,
            network_conf(),
            "conn.log",
            output_chunk_size=10,
            run_row_limit=100,
            merge_fan_in=2,
        )

    assert sorted(path.name for path in destination_dir.iterdir()) == ["stale.csv"]


def test_convert_batch_to_chunked_csv_fails_when_target_log_is_missing_everywhere(tmp_path):
    root = Path(tmp_path)
    log_dir = root / "logs" / "batch_a" / "20220101090000"
    log_dir.mkdir(parents=True)
    destination_dir = root / "csv" / "dns" / "batch_a"
    (log_dir / "conn.log").write_text("{}\n", encoding="utf-8")

    with pytest.raises(SystemExit, match=r"No target logs \(dns\.log\) were found"):
        extractor.convert_batch_to_chunked_csv(
            [log_dir],
            destination_dir,
            network_conf(),
            "dns.log",
            output_chunk_size=10,
            run_row_limit=100,
            merge_fan_in=2,
        )


def test_convert_batch_to_chunked_csv_skips_invalid_ts_and_fails_if_nothing_remains(tmp_path):
    root = Path(tmp_path)
    log_dir = root / "logs" / "batch_a" / "20220101090000"
    log_dir.mkdir(parents=True)
    destination_dir = root / "csv" / "conn" / "batch_a"
    (log_dir / "conn.log").write_text(
        json.dumps(
            {
                "ts": "",
                "duration": 1,
                "uid": "bad-ts",
                "id.orig_h": "192.168.0.10",
                "id.resp_h": "8.8.8.8",
                "conn_state": "SF",
                "local_orig": True,
                "local_resp": False,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(SystemExit, match=r"Skipped 1 records because ts/duration were missing or invalid"):
        extractor.convert_batch_to_chunked_csv(
            [log_dir],
            destination_dir,
            network_conf(),
            "conn.log",
            output_chunk_size=10,
            run_row_limit=100,
            merge_fan_in=2,
        )


def test_convert_logs_to_csv_runs_runtime_validation_for_conn_log(tmp_path, monkeypatch):
    root = Path(tmp_path)
    input_dir = root / "logs" / "batch_a"
    output_root = root / "csv"
    target_output_dir = output_root / "conn" / "batch_a"
    created_csv = target_output_dir / "00000_20220101090001.csv"
    log_dirs = [input_dir / "20220101090000"]

    monkeypatch.setattr(extractor, "discover_log_dirs", lambda *_args, **_kwargs: (log_dirs, "batch_a"))
    monkeypatch.setattr(
        extractor,
        "convert_batch_to_chunked_csv_with_stats",
        lambda *_args, **_kwargs: ([created_csv], extractor.RunCreationStats(emitted_row_count=1, run_count=1)),
    )

    called = {"validate": 0, "print": 0}

    def fake_validate(*_args, **_kwargs):
        called["validate"] += 1
        return type("FakeReport", (), {"ok": True})()

    def fake_print(_report):
        called["print"] += 1

    monkeypatch.setattr(extractor.csv_validator, "validate_csv_dataset", fake_validate)
    monkeypatch.setattr(extractor.csv_validator, "print_report", fake_print)

    created_dirs = extractor.convert_logs_to_csv(
        input_dir,
        output_root,
        ["conn.log"],
        network_conf(),
        output_chunk_size=10,
        run_row_limit=100,
        merge_fan_in=2,
    )

    assert created_dirs == [target_output_dir]
    assert called == {"validate": 1, "print": 1}


def test_convert_logs_to_csv_skips_runtime_validation_for_non_conn_logs(tmp_path, monkeypatch):
    root = Path(tmp_path)
    input_dir = root / "logs" / "batch_a"
    output_root = root / "csv"
    target_output_dir = output_root / "dns" / "batch_a"
    created_csv = target_output_dir / "00000_20220101090001.csv"
    log_dirs = [input_dir / "20220101090000"]

    monkeypatch.setattr(extractor, "discover_log_dirs", lambda *_args, **_kwargs: (log_dirs, "batch_a"))
    monkeypatch.setattr(
        extractor,
        "convert_batch_to_chunked_csv_with_stats",
        lambda *_args, **_kwargs: ([created_csv], extractor.RunCreationStats(emitted_row_count=1, run_count=1)),
    )

    def fail_validate(*_args, **_kwargs):
        raise AssertionError("runtime validation should be skipped for non-conn logs")

    monkeypatch.setattr(extractor.csv_validator, "validate_csv_dataset", fail_validate)

    created_dirs = extractor.convert_logs_to_csv(
        input_dir,
        output_root,
        ["dns.log"],
        network_conf(),
        output_chunk_size=10,
        run_row_limit=100,
        merge_fan_in=2,
    )

    assert created_dirs == [target_output_dir]


def test_convert_logs_to_csv_skips_runtime_validation_when_disabled(tmp_path, monkeypatch):
    root = Path(tmp_path)
    input_dir = root / "logs" / "batch_a"
    output_root = root / "csv"
    target_output_dir = output_root / "conn" / "batch_a"
    created_csv = target_output_dir / "00000_20220101090001.csv"
    log_dirs = [input_dir / "20220101090000"]

    monkeypatch.setattr(extractor, "discover_log_dirs", lambda *_args, **_kwargs: (log_dirs, "batch_a"))
    monkeypatch.setattr(
        extractor,
        "convert_batch_to_chunked_csv_with_stats",
        lambda *_args, **_kwargs: ([created_csv], extractor.RunCreationStats(emitted_row_count=1, run_count=1)),
    )

    def fail_validate(*_args, **_kwargs):
        raise AssertionError("runtime validation should be disabled")

    monkeypatch.setattr(extractor.csv_validator, "validate_csv_dataset", fail_validate)

    created_dirs = extractor.convert_logs_to_csv(
        input_dir,
        output_root,
        ["conn.log"],
        network_conf(),
        output_chunk_size=10,
        run_row_limit=100,
        merge_fan_in=2,
        auto_validate_conn_output=False,
    )

    assert created_dirs == [target_output_dir]
