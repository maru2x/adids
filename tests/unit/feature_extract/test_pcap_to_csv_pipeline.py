from pathlib import Path
from types import SimpleNamespace

from src.util.FeatureExtract.Zeek import pcap_to_csv_pipeline as pipeline


def test_pcap_to_csv_pipeline_uses_fresh_batch_dir_for_log_to_csv(monkeypatch, tmp_path):
    root = Path(tmp_path)
    pcap_input_dir = root / "pcap" / "batch_a"
    log_output_root = root / "logs"
    fresh_batch_dir = log_output_root / pcap_input_dir.name
    csv_output_root = root / "csv"

    monkeypatch.setattr(pipeline, "parse_args", lambda: SimpleNamespace(existing_batch_dir_action=None))
    monkeypatch.setattr(pipeline.pcap_extractor, "load_settings", lambda: {"dummy": True})
    monkeypatch.setattr(
        pipeline.pcap_extractor,
        "resolve_config",
        lambda _settings: (pcap_input_dir, log_output_root),
    )
    monkeypatch.setattr(
        pipeline.csv_extractor,
        "resolve_config",
        lambda _settings: (
            root / "logs" / "stale_batch",
            csv_output_root,
            ["conn.log"],
            {"BENIGN": ["192.168.0.0/24"], "MALICIOUS": [], "EXCEPTION": []},
            3000,
            100000,
            256,
            True,
        ),
    )
    monkeypatch.setattr(
        pipeline.pcap_extractor,
        "convert_pcap_dir_to_logs",
        lambda *_args, **_kwargs: type(
            "Result",
            (),
            {"batch_dir": fresh_batch_dir, "batch_dir_action": "create"},
        )(),
    )

    captured = {}

    def fake_convert_logs_to_csv(
        input_path,
        output_root,
        target_logs,
        network_conf,
        output_chunk_size,
        run_row_limit,
        merge_fan_in,
        auto_validate_conn_output,
    ):
        captured["input_path"] = input_path
        captured["output_root"] = output_root
        captured["target_logs"] = target_logs
        captured["network_conf"] = network_conf
        captured["output_chunk_size"] = output_chunk_size
        captured["run_row_limit"] = run_row_limit
        captured["merge_fan_in"] = merge_fan_in
        captured["auto_validate_conn_output"] = auto_validate_conn_output
        return [csv_output_root / "conn" / pcap_input_dir.name]

    monkeypatch.setattr(pipeline.csv_extractor, "convert_logs_to_csv", fake_convert_logs_to_csv)

    pipeline.main()

    assert captured["input_path"] == fresh_batch_dir
    assert captured["output_root"] == csv_output_root
    assert captured["target_logs"] == ["conn.log"]
    assert captured["auto_validate_conn_output"] is True


def test_pcap_to_csv_pipeline_passes_existing_batch_dir_action_to_pcap_to_log(monkeypatch, tmp_path):
    root = Path(tmp_path)
    pcap_input_dir = root / "pcap" / "batch_a"
    log_output_root = root / "logs"
    fresh_batch_dir = log_output_root / pcap_input_dir.name
    csv_output_root = root / "csv"

    monkeypatch.setattr(
        pipeline,
        "parse_args",
        lambda: SimpleNamespace(existing_batch_dir_action="replace"),
    )
    monkeypatch.setattr(pipeline.pcap_extractor, "load_settings", lambda: {"dummy": True})
    monkeypatch.setattr(
        pipeline.pcap_extractor,
        "resolve_config",
        lambda _settings: (pcap_input_dir, log_output_root),
    )
    monkeypatch.setattr(
        pipeline.csv_extractor,
        "resolve_config",
        lambda _settings: (
            fresh_batch_dir,
            csv_output_root,
            ["conn.log"],
            {"BENIGN": ["192.168.0.0/24"], "MALICIOUS": [], "EXCEPTION": []},
            3000,
            100000,
            256,
            True,
        ),
    )

    captured = {}

    def fake_convert_pcap_dir_to_logs(input_path, output_root, *, existing_batch_dir_action=None):
        captured["existing_batch_dir_action"] = existing_batch_dir_action
        return type(
            "Result",
            (),
            {"batch_dir": fresh_batch_dir, "batch_dir_action": "create"},
        )()

    monkeypatch.setattr(
        pipeline.pcap_extractor,
        "convert_pcap_dir_to_logs",
        fake_convert_pcap_dir_to_logs,
    )
    monkeypatch.setattr(
        pipeline.csv_extractor,
        "convert_logs_to_csv",
        lambda *_args, **_kwargs: [csv_output_root / "conn" / pcap_input_dir.name],
    )

    pipeline.main()

    assert captured["existing_batch_dir_action"] == "replace"
