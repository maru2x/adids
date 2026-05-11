# `bulk` fixture 詳細

このドキュメントでは、`test_zeek_bulk_golden.py` が使う中サイズ `bulk` fixture をまとめる。

前提:

- `bulk` は 1 個の巨大 `pcap` ではなく、同一 batch に入れる複数 `pcap` の集合である
- `raw pcap` の表は Wireshark に近い列構成で、`No. / Time / Source / Destination / Protocol / Length / Info` を示す
- `Time` はここでは JST 表記で記している
- `expected csv` は `golden` テストが比較する列 subset と、出力先の対応を示す

## 入力構成

`test_zeek_bulk_golden.py` は次の 3 つの `pcap` を同じ input batch に配置して処理する。

- `pcap/bulk_dataset/bulk_udp_mix_a.pcap`
- `pcap/bulk_dataset/bulk_dns_mix_b.pcap`
- `pcap/bulk_dataset/bulk_https_mix_c.pcap`

最終的な `golden` 比較では、次の 5 個の CSV を確認する。

- `conn/20220101091000.csv`
- `conn/20220101091100.csv`
- `conn/20220101091200.csv`
- `dns/20220101091100.csv`
- `ssl/20220101091200.csv`

## `bulk_udp_mix_a.pcap`

想定している論点:

- benign / malicious / one-way を 1 つの `pcap` に混在させても `conn.csv` が崩れないこと

raw pcap:

| No. | Time | Source | Destination | Protocol | Length | Info |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | `2022-01-01 09:10:00.000` | `192.168.0.60:48000` | `8.8.8.8:48001` | `UDP` | `43` | `48000 -> 48001 Len=1` |
| 2 | `2022-01-01 09:10:01.000` | `8.8.8.8:48001` | `192.168.0.60:48000` | `UDP` | `43` | `48001 -> 48000 Len=1` |
| 3 | `2022-01-01 09:10:02.000` | `192.168.0.61:48010` | `10.0.0.7:48011` | `UDP` | `43` | `48010 -> 48011 Len=1` |
| 4 | `2022-01-01 09:10:04.000` | `10.0.0.7:48011` | `192.168.0.61:48010` | `UDP` | `43` | `48011 -> 48010 Len=1` |
| 5 | `2022-01-01 09:10:06.000` | `192.168.0.62:48020` | `9.9.9.9:48021` | `UDP` | `43` | `48020 -> 48021 Len=1` |

expected csv:

- 出力先
  - `conn/20220101091000.csv`
- 期待する行
  - benign roundtrip 1 行
  - malicious roundtrip 1 行
  - one-way 1 行
- 期待する代表結果
  - `09:10:01` の row は `label=0`, `conn_state=SF`
  - `09:10:04` の row は `label=1`, `conn_state=SF`
  - `09:10:06` の row は `label=0`, `conn_state=S0`, `duration=0`

## `bulk_dns_mix_b.pcap`

想定している論点:

- 1 つの `pcap` で複数 DNS query/response を流したときに、`conn.csv` と `dns.csv` の両方が stable に生成されること

raw pcap:

| No. | Time | Source | Destination | Protocol | Length | Info |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | `2022-01-01 09:11:00.000` | `192.168.0.70:53010` | `8.8.8.8:53` | `UDP` | `57` | `Standard query A example.com` |
| 2 | `2022-01-01 09:11:00.300` | `8.8.8.8:53` | `192.168.0.70:53010` | `UDP` | `73` | `Standard query response A example.com A 93.184.216.34` |
| 3 | `2022-01-01 09:11:02.000` | `192.168.0.71:53011` | `1.1.1.1:53` | `UDP` | `56` | `Standard query A openai.com` |
| 4 | `2022-01-01 09:11:02.400` | `1.1.1.1:53` | `192.168.0.71:53011` | `UDP` | `72` | `Standard query response A openai.com A 104.18.33.45` |

expected csv:

- 出力先
  - `conn/20220101091100.csv`
  - `dns/20220101091100.csv`
- 期待する行
  - `conn.csv` に 2 行
  - `dns.csv` に 2 行
- 期待する代表結果
  - `conn.csv` では `service=dns`
  - `dns.csv` では `query=example.com` と `query=openai.com`
  - `dns.csv` の `answers` はそれぞれ `["93.184.216.34"]`, `["104.18.33.45"]`

## `bulk_https_mix_c.pcap`

想定している論点:

- 1 つの TLS-over-TCP セッションから、`conn.csv` と `ssl.csv` が同時に安定して生成されること

raw pcap:

| No. | Time | Source | Destination | Protocol | Length | Info |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | `2022-01-01 09:12:00.000` | `192.168.0.80:54010` | `93.184.216.34:443` | `TCP` | `60` | `54010 -> 443 [SYN]` |
| 2 | `2022-01-01 09:12:00.050` | `93.184.216.34:443` | `192.168.0.80:54010` | `TCP` | `60` | `443 -> 54010 [SYN, ACK]` |
| 3 | `2022-01-01 09:12:00.100` | `192.168.0.80:54010` | `93.184.216.34:443` | `TCP` | `52` | `54010 -> 443 [ACK]` |
| 4 | `2022-01-01 09:12:00.200` | `192.168.0.80:54010` | `93.184.216.34:443` | `TCP` | `569` | `Client Hello` |
| 5 | `2022-01-01 09:12:00.400` | `93.184.216.34:443` | `192.168.0.80:54010` | `TCP` | `1420` | `Server Hello, Certificate, Finished` |
| 6 | `2022-01-01 09:12:00.900` | `192.168.0.80:54010` | `93.184.216.34:443` | `TCP` | `381` | `TLS application data` |
| 7 | `2022-01-01 09:12:01.400` | `93.184.216.34:443` | `192.168.0.80:54010` | `TCP` | `1513` | `TLS application data` |
| 8 | `2022-01-01 09:12:01.700` | `192.168.0.80:54010` | `93.184.216.34:443` | `TCP` | `52` | `54010 -> 443 [FIN, ACK]` |
| 9 | `2022-01-01 09:12:01.750` | `93.184.216.34:443` | `192.168.0.80:54010` | `TCP` | `52` | `443 -> 54010 [FIN, ACK]` |
| 10 | `2022-01-01 09:12:01.800` | `192.168.0.80:54010` | `93.184.216.34:443` | `TCP` | `52` | `54010 -> 443 [ACK]` |

expected csv:

- 出力先
  - `conn/20220101091200.csv`
  - `ssl/20220101091200.csv`
- 期待する行
  - `conn.csv` に 1 行
  - `ssl.csv` に 1 行
- 期待する代表結果
  - `conn.csv` では `proto=tcp`, `service=ssl`, `conn_state=SF`
  - `ssl.csv` では `version=TLSv13`, `server_name=example.com`, `established=True`

## 位置づけ

この `bulk` fixture は、tiny fixture のように 1 論点 1 `pcap` へ極端には寄せていない。
代わりに、次を同時に確認するための中サイズ dataset として使う。

- 複数 `pcap` を同一 batch に入れたときのレイアウト
- `conn` / `dns` / `ssl` の複数出力ディレクトリ
- benign / malicious / one-way / DNS / TLS をまたぐ expected CSV 比較
