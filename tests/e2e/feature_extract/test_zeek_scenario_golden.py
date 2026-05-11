import shutil
from pathlib import Path

import pytest

from tests.e2e.feature_extract._golden_helpers import (
    DEFAULT_NETWORK_CONF,
    FIXTURE_DIR,
    assert_csv_matches_expected_subset,
    run_full_pipeline_main,
)


SCENARIO_GOLDEN_CASES = (
    pytest.param(
        {
            "relative_pcap_path": "protocol_traffic/dns_udp_query_response.pcap",
            "target_logs": ["conn.log", "dns.log"],
            "expected_by_output_dir": {
                "conn": "dns_udp_query_response_conn.csv",
                "dns": "dns_udp_query_response_dns.csv",
            },
            "runtime_output_dirs": {"conn"},
        },
        id="dns-query-response",
    ),
    pytest.param(
        {
            "relative_pcap_path": "protocol_traffic/https_tls_handshake.pcap",
            "target_logs": ["conn.log", "ssl.log"],
            "expected_by_output_dir": {
                "conn": "https_tls_handshake_conn.csv",
                "ssl": "https_tls_handshake_ssl.csv",
            },
            "runtime_output_dirs": {"conn"},
        },
        id="https-tls-handshake",
    ),
)


# Input:
# - protocol-specific pcap fixture 1 件
# - TARGET_LOGS に conn.log と protocol analyzer log を指定
# - 各出力 log 種別に対応する expected_csv
# Expectation:
# - 各 target_log ごとの leaf CSV dir が作られる
# - 代表的な analyzer field を含む CSV subset が expected_csv と一致する
# - conn.csv は runtime 最低契約も満たす
# Target scripts:
# - pcap_to_log_extractor.main()
# - log_to_csv_extractor.main()
# Overview:
# - DNS / TLS のような protocol-specific traffic を、conn.csv だけでなく dns.csv / ssl.csv まで含めて golden 比較する。
@pytest.mark.e2e
@pytest.mark.skipif(shutil.which("zeek") is None, reason="zeek command is required for e2e feature extraction tests")
@pytest.mark.parametrize("case", SCENARIO_GOLDEN_CASES)
def test_full_pipeline_main_matches_scenario_golden_csv(tmp_path, monkeypatch, case):
    input_dir, _, csv_output_root = run_full_pipeline_main(
        monkeypatch,
        tmp_path,
        case["relative_pcap_path"],
        target_logs=case["target_logs"],
        network_conf=DEFAULT_NETWORK_CONF,
    )
    batch_name = input_dir.name

    for output_dir_name, expected_name in case["expected_by_output_dir"].items():
        actual_dir = csv_output_root / batch_name / output_dir_name
        actual_files = sorted(actual_dir.glob("*.csv"))
        assert len(actual_files) == 1
        expected_path = FIXTURE_DIR / "expected_csv" / expected_name
        assert_csv_matches_expected_subset(
            actual_files[0],
            expected_path,
            expect_runtime_contract=output_dir_name in case["runtime_output_dirs"],
        )
