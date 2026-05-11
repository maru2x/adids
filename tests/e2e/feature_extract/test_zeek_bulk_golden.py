import shutil

import pytest

from tests.e2e.feature_extract._golden_helpers import (
    FIXTURE_DIR,
    assert_csv_matches_expected_subset,
    run_full_pipeline_main,
)


BULK_NETWORK_CONF = {
    "BENIGN": ["192.168.0.0/24"],
    "MALICIOUS": ["10.0.0.0/24"],
    "EXCEPTION": [],
}
BULK_PCAPS = [
    "bulk_dataset/bulk_udp_mix_a.pcap",
    "bulk_dataset/bulk_dns_mix_b.pcap",
    "bulk_dataset/bulk_https_mix_c.pcap",
]
BULK_EXPECTED = {
    "conn": {
        "20220101091000.csv": "bulk_udp_mix_conn.csv",
        "20220101091100.csv": "bulk_dns_mix_conn.csv",
        "20220101091200.csv": "bulk_https_mix_conn.csv",
    },
    "dns": {
        "20220101091100.csv": "bulk_dns_mix_dns.csv",
    },
    "ssl": {
        "20220101091200.csv": "bulk_https_mix_ssl.csv",
    },
}


# Input:
# - 複数 pcap を同一 batch にまとめた中サイズデータセット
# - TARGET_LOGS=["conn.log", "dns.log", "ssl.log"]
# - 各 timestamp / target_log ごとに対応する expected_csv
# Expectation:
# - 複数 pcap を通したときも target_log ごとの leaf CSV dir が正しく並ぶ
# - 生成された各 CSV が対応する expected_csv と一致する
# - conn.csv 群は runtime 最低契約を満たす
# Target scripts:
# - pcap_to_log_extractor.main()
# - log_to_csv_extractor.main()
# Overview:
# - tiny fixture より大きい batch 入力を使い、複数 protocol をまたぐ bulk golden を確認する。
@pytest.mark.e2e
@pytest.mark.skipif(shutil.which("zeek") is None, reason="zeek command is required for e2e feature extraction tests")
def test_full_pipeline_main_matches_bulk_golden_csv(tmp_path, monkeypatch):
    input_dir, _, csv_output_root = run_full_pipeline_main(
        monkeypatch,
        tmp_path,
        BULK_PCAPS,
        target_logs=["conn.log", "dns.log", "ssl.log"],
        network_conf=BULK_NETWORK_CONF,
    )
    for output_dir_name, expected_files in BULK_EXPECTED.items():
        actual_dir = csv_output_root / output_dir_name / input_dir.name
        actual_files = sorted(path.name for path in actual_dir.glob("*.csv"))
        assert actual_files == sorted(expected_files.keys())
        for actual_name, expected_name in expected_files.items():
            actual_path = actual_dir / actual_name
            expected_path = FIXTURE_DIR / "expected_csv" / expected_name
            assert_csv_matches_expected_subset(
                actual_path,
                expected_path,
                expect_runtime_contract=output_dir_name == "conn",
            )
