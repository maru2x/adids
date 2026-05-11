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


# Input:
# - fixture unordered_conn.log
# Expectation:
# - CSV の daytime は入力順ではなく flow end time 順になる
# Target method:
# - convert_log_dir()
# Overview:
# - 指定 log dir の target log を読み込み、CSV header 構築、並び替え、書き出しまでを行う。
# Note:
# - resolve_flow_end_ts() と sort_records_by_flow_end_time() をまとめて見ている。
def test_convert_log_dir_sorts_by_flow_end_time(tmp_path):
    root = Path(tmp_path)
    log_dir = root / "logs" / "20220101000000"
    log_dir.mkdir(parents=True)
    destination = root / "csv" / "20220101000000.csv"

    (log_dir / "conn.log").write_text(
        (FIXTURE_DIR / "unordered_conn.log").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    extractor.convert_log_dir(log_dir, destination, network_conf(), ["conn.log"])

    rows = read_csv_rows(destination)
    assert [row["daytime"] for row in rows] == [
        "2022-01-01 09:00:06",
        "2022-01-01 09:10:00",
    ]


# Input:
# - fixture zero_duration_conn.log
# Expectation:
# - duration = 0 は欠損ではなく有効値として扱われる
# - daytime は ts と同じ時刻になる
# Target method:
# - convert_log_dir()
# Overview:
# - 指定 log dir の target log を読み込み、CSV header 構築、並び替え、書き出しまでを行う。
def test_convert_log_dir_keeps_zero_duration_as_valid_end_time(tmp_path):
    root = Path(tmp_path)
    log_dir = root / "logs" / "20220101000000"
    log_dir.mkdir(parents=True)
    destination = root / "csv" / "20220101000000.csv"

    (log_dir / "conn.log").write_text(
        (FIXTURE_DIR / "zero_duration_conn.log").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    extractor.convert_log_dir(log_dir, destination, network_conf(), ["conn.log"])

    rows = read_csv_rows(destination)
    assert rows[0]["daytime"] == "2022-01-01 09:00:00"


# Input:
# - fixture duration_fallback_conn.log
# Expectation:
# - duration 欠損/不正値では ts にフォールバックする
# Target method:
# - convert_log_dir()
# Overview:
# - 指定 log dir の target log を読み込み、CSV header 構築、並び替え、書き出しまでを行う。
# Note:
# - runtime contract の daytime 生成ルールの基礎。
def test_convert_log_dir_falls_back_to_start_time_when_duration_is_missing_or_invalid(tmp_path):
    root = Path(tmp_path)
    log_dir = root / "logs" / "20220101000000"
    log_dir.mkdir(parents=True)
    destination = root / "csv" / "20220101000000.csv"

    (log_dir / "conn.log").write_text(
        (FIXTURE_DIR / "duration_fallback_conn.log").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    extractor.convert_log_dir(log_dir, destination, network_conf(), ["conn.log"])

    rows = read_csv_rows(destination)
    assert [row["daytime"] for row in rows] == [
        "2022-01-01 09:00:00",
        "2022-01-01 09:00:10",
    ]


# Input:
# - benign -> external の keep record
# - unlabeled record
# - exception record
# - list/dict を含む nested value
# Expectation:
# - keep record だけ CSV に残る
# - label は 0
# - nested value は JSON 文字列化される
# Target method:
# - convert_log_dir()
# Overview:
# - 指定 log dir の target log を読み込み、CSV header 構築、並び替え、書き出しまでを行う。
# Note:
# - write_csv() の filtering と serialization をまとめて確認する integration 寄りのテスト。
def test_convert_log_dir_filters_unknown_and_exception_records_and_serializes_nested_values(tmp_path):
    root = Path(tmp_path)
    log_dir = root / "logs" / "20220101000000"
    log_dir.mkdir(parents=True)
    destination = root / "csv" / "20220101000000.csv"
    records = [
        {
            "ts": 1640995200,
            "duration": 2,
            "uid": "keep",
            "id.orig_h": "192.168.0.10",
            "id.resp_h": "8.8.8.8",
            "history": ["Sh", "AD"],
            "meta": {"proto": "udp"},
        },
        {
            "ts": 1640995201,
            "duration": 1,
            "uid": "skip-unlabeled",
            "id.orig_h": "8.8.8.8",
            "id.resp_h": "1.1.1.1",
        },
        {
            "ts": 1640995202,
            "duration": 1,
            "uid": "skip-exception",
            "id.orig_h": "192.168.0.200",
            "id.resp_h": "8.8.4.4",
        },
    ]
    (log_dir / "conn.log").write_text(
        "\n".join(json.dumps(record) for record in records) + "\n",
        encoding="utf-8",
    )

    extractor.convert_log_dir(log_dir, destination, network_conf(), ["conn.log"])

    rows = read_csv_rows(destination)
    assert len(rows) == 1
    assert rows[0]["uid"] == "keep"
    assert rows[0]["label"] == "0"
    assert rows[0]["daytime"] == "2022-01-01 09:00:02"
    assert json.loads(rows[0]["history"]) == ["Sh", "AD"]
    assert json.loads(rows[0]["meta"]) == {"proto": "udp"}


# Input:
# - 1 つの log_dir に conn.log と dns.log の両方を置く
# Expectation:
# - 両ファイルの record が 1 本の CSV に入る
# - 存在しない key は空文字で埋まる
# Target method:
# - convert_log_dir()
# Overview:
# - 指定 log dir の target log を読み込み、CSV header 構築、並び替え、書き出しまでを行う。
# Note:
# - convert_log_dir(..., target_logs=[...]) の複数ファイル読込を確認する。
def test_convert_log_dir_reads_multiple_target_log_files(tmp_path):
    root = Path(tmp_path)
    log_dir = root / "logs" / "20220101000000"
    log_dir.mkdir(parents=True)
    destination = root / "csv" / "20220101000000.csv"

    (log_dir / "conn.log").write_text(
        json.dumps(
            {
                "ts": 1640995200,
                "duration": 0,
                "uid": "conn-row",
                "id.orig_h": "192.168.0.10",
                "id.resp_h": "8.8.8.8",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (log_dir / "dns.log").write_text(
        json.dumps(
            {
                "ts": 1640995205,
                "duration": 0,
                "uid": "dns-row",
                "query": "example.com",
                "id.orig_h": "192.168.0.20",
                "id.resp_h": "1.1.1.1",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    extractor.convert_log_dir(log_dir, destination, network_conf(), ["conn.log", "dns.log"])

    rows = read_csv_rows(destination)
    assert [row["uid"] for row in rows] == ["conn-row", "dns-row"]
    assert rows[0]["query"] == ""
    assert rows[1]["query"] == "example.com"


# Input:
# - duration / orig_bytes / resp_bytes を持たない one-way 相当の conn.log record
# Expectation:
# - CSV header には conn.log 必須列が残る
# - duration は 0 で補完される
# - orig_bytes / resp_bytes は空文字のまま書かれる
# Target method:
# - convert_log_dir()
# Overview:
# - sparse な conn.log record を runtime 契約に沿う CSV へ正規化する。
def test_convert_log_dir_keeps_conn_required_columns_and_sets_zero_duration_for_one_way_record(tmp_path):
    root = Path(tmp_path)
    log_dir = root / "logs" / "20220101000000"
    log_dir.mkdir(parents=True)
    destination = root / "csv" / "20220101000000.csv"

    (log_dir / "conn.log").write_text(
        json.dumps(
            {
                "ts": 1640995200,
                "uid": "one-way",
                "id.orig_h": "192.168.0.10",
                "id.orig_p": 47000,
                "id.resp_h": "9.9.9.9",
                "id.resp_p": 47001,
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
        )
        + "\n",
        encoding="utf-8",
    )

    extractor.convert_log_dir(log_dir, destination, network_conf(), ["conn.log"])

    rows = read_csv_rows(destination)
    assert len(rows) == 1
    row = rows[0]
    for column in extractor.CONN_REQUIRED_COLUMNS:
        assert column in row
    assert row["duration"] == "0"
    assert row["orig_bytes"] == ""
    assert row["resp_bytes"] == ""
