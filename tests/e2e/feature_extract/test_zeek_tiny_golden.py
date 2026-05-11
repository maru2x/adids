import shutil
from pathlib import Path

import pytest

from tests.e2e.feature_extract._golden_helpers import (
    DEFAULT_NETWORK_CONF,
    FIXTURE_DIR,
    assert_csv_matches_expected_subset,
    run_full_pipeline_main,
)


TINY_GOLDEN_CASES = (
    pytest.param(
        {
            "pcap_name": "zeek_udp_roundtrip.pcap",
            "expected_name": "zeek_udp_roundtrip.csv",
            "network_conf": DEFAULT_NETWORK_CONF,
        },
        id="roundtrip",
    ),
    pytest.param(
        {
            "pcap_name": "zeek_udp_malicious_roundtrip.pcap",
            "expected_name": "zeek_udp_malicious_roundtrip.csv",
            "network_conf": {
                "BENIGN": ["192.168.0.0/24"],
                "MALICIOUS": ["10.0.0.0/24"],
                "EXCEPTION": [],
            },
        },
        id="malicious-roundtrip",
    ),
    pytest.param(
        {
            "pcap_name": "zeek_udp_two_roundtrips.pcap",
            "expected_name": "zeek_udp_two_roundtrips.csv",
            "network_conf": DEFAULT_NETWORK_CONF,
        },
        id="two-roundtrips",
    ),
    pytest.param(
        {
            "pcap_name": "zeek_udp_exception_roundtrip.pcap",
            "expected_name": "zeek_udp_exception_roundtrip.csv",
            "network_conf": {
                "BENIGN": ["192.168.0.0/24"],
                "MALICIOUS": [],
                "EXCEPTION": ["8.8.8.8/32"],
            },
        },
        id="exception-roundtrip",
    ),
    pytest.param(
        {
            "pcap_name": "zeek_udp_interleaved.pcap",
            "expected_name": "zeek_udp_interleaved.csv",
            "network_conf": DEFAULT_NETWORK_CONF,
        },
        id="interleaved",
    ),
    pytest.param(
        {
            "pcap_name": "zeek_udp_one_way.pcap",
            "expected_name": "zeek_udp_one_way.csv",
            "network_conf": DEFAULT_NETWORK_CONF,
        },
        id="one-way",
    ),
)


# Input:
# - tiny UDP fixture 1 件
# - expected_csv の正解 subset
# - pcap_to_log_extractor.main() と log_to_csv_extractor.main() を通す実導線
# Expectation:
# - 最終 conn.csv が expected_csv と一致する
# - runtime に渡すケースでは conn.csv の最低契約も満たす
# - exception fixture では header-only CSV が生成される
# Target scripts:
# - pcap_to_log_extractor.main()
# - log_to_csv_extractor.main()
# Overview:
# - 最小論点ごとの tiny fixture に対して、conn.log -> conn.csv の golden 比較を行う。
@pytest.mark.e2e
@pytest.mark.skipif(shutil.which("zeek") is None, reason="zeek command is required for e2e feature extraction tests")
@pytest.mark.parametrize("case", TINY_GOLDEN_CASES)
def test_full_pipeline_main_matches_tiny_golden_csv(tmp_path, monkeypatch, case):
    input_dir, _, csv_output_root = run_full_pipeline_main(
        monkeypatch,
        tmp_path,
        case["pcap_name"],
        target_logs=["conn.log"],
        network_conf=case["network_conf"],
    )
    csv_dir = csv_output_root / input_dir.name / "conn"
    csv_files = sorted(csv_dir.glob("*.csv"))
    assert len(csv_files) == 1

    expected_path = FIXTURE_DIR / "expected_csv" / case["expected_name"]
    expect_runtime_contract = "exception" not in case["pcap_name"]
    assert_csv_matches_expected_subset(
        csv_files[0],
        expected_path,
        expect_runtime_contract=expect_runtime_contract,
    )
