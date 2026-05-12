#!/usr/bin/env python3
"""Run the stable Zeek preprocessing pipeline from PCAP to CSV."""

from __future__ import annotations

import argparse

try:
    from . import log_to_csv_extractor as csv_extractor
    from . import pcap_to_log_extractor as pcap_extractor
except ImportError:
    import log_to_csv_extractor as csv_extractor
    import pcap_to_log_extractor as pcap_extractor


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run pcap-to-log and log-to-csv in one command using Zeek settings.json."
    )
    pcap_extractor.add_existing_batch_dir_args(parser)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    settings = pcap_extractor.load_settings()
    pcap_input_path, log_output_root = pcap_extractor.resolve_config(settings)
    (
        _configured_log_input_path,
        csv_output_root,
        target_logs,
        network_conf,
        output_chunk_size,
        run_row_limit,
        merge_fan_in,
        auto_validate_conn_output,
    ) = csv_extractor.resolve_config(settings)

    print("[pcap-to-csv] pcap -> log 開始")
    pcap_result = pcap_extractor.convert_pcap_dir_to_logs(
        pcap_input_path,
        log_output_root,
        existing_batch_dir_action=getattr(args, "existing_batch_dir_action", None),
    )
    if pcap_result.batch_dir_action == "reuse":
        pcap_extractor.print_reuse_warning(
            pcap_result.batch_dir,
            caller_tag="[pcap-to-csv]",
        )

    print("[pcap-to-csv] log -> csv 開始")
    created_output_dirs = csv_extractor.convert_logs_to_csv(
        pcap_result.batch_dir,
        csv_output_root,
        target_logs,
        network_conf,
        output_chunk_size,
        run_row_limit,
        merge_fan_in,
        auto_validate_conn_output=auto_validate_conn_output,
    )

    print("[pcap-to-csv] 完了")
    for created_output_dir in created_output_dirs:
        print(created_output_dir)


if __name__ == "__main__":
    main()
