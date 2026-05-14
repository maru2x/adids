import json
from pathlib import Path

from src.util.FeatureExtract.Zeek.feature_exporter import LiveExportState, iter_new_live_records


def test_iter_new_live_records_defers_partial_trailing_json_until_next_poll(tmp_path):
    conn_log_path = Path(tmp_path) / "conn.log"
    valid_record = {
        "ts": 1710000000.0,
        "uid": "Cvalid1",
        "id.orig_h": "192.168.10.50",
        "id.orig_p": 42310,
        "id.resp_h": "192.168.10.10",
        "id.resp_p": 2223,
        "proto": "tcp",
        "conn_state": "OTH",
        "local_orig": True,
        "local_resp": True,
        "missed_bytes": 0,
        "orig_pkts": 1,
        "orig_ip_bytes": 40,
        "resp_pkts": 0,
        "resp_ip_bytes": 0,
        "duration": 0.02,
    }
    partial_prefix = '{"ts":1710000001.0,"uid":"Cpartial1"'
    conn_log_path.write_text(json.dumps(valid_record) + "\n" + partial_prefix, encoding="utf-8")

    state = LiveExportState()
    records, new_offset = iter_new_live_records(conn_log_path, state)

    assert len(records) == 1
    assert records[0]["uid"] == "Cvalid1"

    with conn_log_path.open("a", encoding="utf-8") as fh:
        fh.write(
            ',"id.orig_h":"192.168.10.51","id.orig_p":42311,"id.resp_h":"192.168.10.10",'
            '"id.resp_p":2223,"proto":"tcp","conn_state":"OTH","local_orig":true,'
            '"local_resp":true,"missed_bytes":0,"orig_pkts":1,"orig_ip_bytes":40,'
            '"resp_pkts":0,"resp_ip_bytes":0,"duration":0.02}\n'
        )

    state.offset = new_offset
    records, new_offset = iter_new_live_records(conn_log_path, state)

    assert len(records) == 1
    assert records[0]["uid"] == "Cpartial1"
    assert new_offset == conn_log_path.stat().st_size
