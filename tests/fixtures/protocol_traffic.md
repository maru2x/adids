# Protocol-specific Traffic Fixtures

このドキュメントでは、`tests/fixtures/pcap/protocol_traffic/` に置く protocol-specific fixture をまとめる。

ここに置く fixture は、`golden` の安定比較用 fixture とは役割が異なる。

- `golden` fixture
  - `conn.log` から最終 CSV を安定して比較したい
  - そのため、できるだけ protocol analyzer の影響を受けにくい tiny traffic を優先する
- `protocol-specific` fixture
  - DNS や HTTPS のように、Zeek が protocol analyzer をどう動かすかを見たい
  - そのため、payload もその protocol として妥当な形にする

## 方針

- protocol 固有の log を見たいときは、このディレクトリに fixture を足す
- ここに置く traffic は、最小であっても **その protocol として自然** であることを優先する
- `udp/53` を使うなら DNS query/response を入れる
- `tcp/443` を使うなら TCP handshake と TLS handshake を入れる

## 一覧

### `dns_udp_query_response.pcap`

目的:

- 正しい DNS over UDP traffic を持つ最小 fixture

想定している traffic:

- client `192.168.0.40:53000 -> 8.8.8.8:53`
- query `A example.com`
- server `8.8.8.8:53 -> 192.168.0.40:53000`
- answer `93.184.216.34`

Zeek で期待する主な出力:

- `conn.log`
  - `proto=udp`
  - `service=dns`
  - `conn_state=SF`
- `dns.log`
  - `query=example.com`
  - `qtype_name=A`
  - `answers=["93.184.216.34"]`

用途:

- `dns.log` を対象にした `log-to-csv` 拡張や E2E の土台
- analyzer にとって自然な DNS traffic の最小例

### `https_tls_handshake.pcap`

目的:

- HTTPS/TLS traffic を持つ最小 fixture

想定している traffic:

- client `192.168.0.50:54000 -> 93.184.216.34:443`
- TCP 3-way handshake
- TLS handshake
- TLS 上での最小 HTTP request / response
- TCP close

Zeek で期待する主な出力:

- `conn.log`
  - `proto=tcp`
  - `service=ssl`
  - `conn_state=SF`
- `ssl.log`
  - `server_name=example.com`
  - `established=true`

ローカル確認時の代表値:

- `service=ssl`
- `version=TLSv13`
- `server_name=example.com`
- `ssl_history=CsiI`

用途:

- `ssl.log` を対象にした解析・CSV化の検討
- TCP/TLS analyzer を通す fixture のたたき台

## 補足

これらの fixture は、現時点では tiny `golden` ではなく scenario `golden` の比較対象にしている。

理由は次の通り。

- tiny `golden` はまず `conn.log -> csv` の stable contract を守るのが主目的
- protocol-specific fixture は、`dns.log` や `ssl.log` をどう扱うかという別の論点を含む
- そのため、scenario `golden` として分けた方が整理しやすい

関連:

- [tests/fixtures/README.md](./README.md)
- [tests/fixtures/golden_fixtures.md](./golden_fixtures.md)
- [tests/e2e/feature_extract/test_zeek_scenario_golden.py](../e2e/feature_extract/test_zeek_scenario_golden.py)
- [docs/Zeekログの読み方.md](../docs/Zeekログの読み方.md)
