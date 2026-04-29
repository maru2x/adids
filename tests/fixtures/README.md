# Test Fixtures

このディレクトリには、自動テストで使う固定入力と期待値を置く。

- `pcap/`
  - Zeek の E2E で使う極小 PCAP
- `expected_csv/`
  - E2E の期待結果
- `zeek_logs/`
  - `log -> csv` 系テストで使う固定ログ置き場

現在の主な fixture:
- `pcap/zeek_udp_roundtrip.pcap`
- `pcap/zeek_udp_interleaved.pcap`
- `pcap/zeek_udp_one_way.pcap`
- `expected_csv/zeek_udp_roundtrip.csv`
- `expected_csv/zeek_udp_interleaved.csv`
- `expected_csv/zeek_udp_one_way.csv`
- `zeek_logs/unordered_conn.log`
- `zeek_logs/zero_duration_conn.log`
- `zeek_logs/duration_fallback_conn.log`

方針:
- fixture はできるだけ小さくする
- 1 fixture 1 論点に寄せる
- 実データと混ざらないように `tests/fixtures/` 配下に限定する
