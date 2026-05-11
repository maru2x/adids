# Test Fixtures

このディレクトリには、自動テストで使う固定入力と期待値を置く。

- `pcap/`
  - Zeek の E2E で使う極小 PCAP
  - `pcap/bulk_dataset/` に中サイズ bulk dataset 用の PCAP を置く
  - `pcap/protocol_traffic/` に protocol-specific な PCAP を置く
- `data_modified/`
  - `DataModified` の golden E2E で使う固定入力 CSV と expected CSV
- `validate/`
  - CSV dataset validator の fixture
- `expected_csv/`
  - E2E の期待結果
- `zeek_logs/`
  - `log -> csv` 系テストで使う固定ログ置き場

現在の主な fixture:
- `pcap/zeek_udp_roundtrip.pcap`
- `pcap/zeek_udp_malicious_roundtrip.pcap`
- `pcap/zeek_udp_two_roundtrips.pcap`
- `pcap/zeek_udp_exception_roundtrip.pcap`
- `pcap/zeek_udp_interleaved.pcap`
- `pcap/zeek_udp_one_way.pcap`
- `pcap/protocol_traffic/dns_udp_query_response.pcap`
- `pcap/protocol_traffic/https_tls_handshake.pcap`
- `pcap/bulk_dataset/bulk_udp_mix_a.pcap`
- `pcap/bulk_dataset/bulk_dns_mix_b.pcap`
- `pcap/bulk_dataset/bulk_https_mix_c.pcap`
- `data_modified/combine_case/`
- `data_modified/daytime_override_case/`
- `data_modified/align_mix_case/`
- `validate/valid_zeek_leaf/`
- `validate/invalid_time_order_leaf/`
- `expected_csv/zeek_udp_roundtrip.csv`
- `expected_csv/zeek_udp_malicious_roundtrip.csv`
- `expected_csv/zeek_udp_two_roundtrips.csv`
- `expected_csv/zeek_udp_exception_roundtrip.csv`
- `expected_csv/zeek_udp_interleaved.csv`
- `expected_csv/zeek_udp_one_way.csv`
- `expected_csv/dns_udp_query_response_conn.csv`
- `expected_csv/dns_udp_query_response_dns.csv`
- `expected_csv/https_tls_handshake_conn.csv`
- `expected_csv/https_tls_handshake_ssl.csv`
- `expected_csv/bulk_udp_mix_conn.csv`
- `expected_csv/bulk_dns_mix_conn.csv`
- `expected_csv/bulk_dns_mix_dns.csv`
- `expected_csv/bulk_https_mix_conn.csv`
- `expected_csv/bulk_https_mix_ssl.csv`
- `zeek_logs/unordered_conn.log`
- `zeek_logs/zero_duration_conn.log`
- `zeek_logs/duration_fallback_conn.log`
- `golden_fixtures.md`
- `bulk_fixtures.md`
- `protocol_traffic.md`

方針:
- fixture はできるだけ小さくする
- 1 fixture 1 論点に寄せる
- 実データと混ざらないように `tests/fixtures/` 配下に限定する

traffic 設計メモ:
- `pcap -> log -> csv` の最小 fixture では、まず UDP を優先する
- 理由は、TCP より packet 数を少なく保ちやすく、fixture の意図を説明しやすいから
- ただし `udp/53` のような well-known port を使う場合は、その protocol として自然な payload を入れる
- たとえば `udp/53` を使うなら、Zeek が DNS analyzer を動かしやすいので、payload も DNS として妥当な形にした方がよい
- protocol 固有の意味を持たせたくない最小 fixture では、高番 port の単純 UDP を優先する
- DNS や HTTPS のような protocol-specific fixture は、stable golden とは分けて管理する
- 現在は `tiny / scenario / bulk` の 3 種類の golden に分けて使う
- `bulk` は 1 個の巨大 `pcap` ではなく、複数 `pcap` を同一 batch にまとめる dataset として管理する
