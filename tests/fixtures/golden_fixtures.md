# `golden` fixture 詳細

このドキュメントでは、主に `test_zeek_tiny_golden.py` が使う `pcap` fixture と `expected_csv` fixture の対応をまとめる。

前提:

- `raw pcap` の表は Wireshark に近い列構成で、`No. / Time / Source / Destination / Protocol / Length / Info` を示す
- `Time` はここでは JST 表記で記している
- `expected csv` は `golden` テストが比較する列 subset を示す
- `uid` のような Zeek 固有の列で比較しづらいものは、`expected csv` には含めない

fixture 設計メモ:

- 最小の `golden` fixture では、packet 数を小さく保ちやすい UDP を優先している
- ただし `udp/53` のような well-known port は analyzer に強い意味付けをされやすい
- そのため、`53` 番 port を使う fixture は payload も DNS として妥当である方が安定する
- protocol 固有の意味を持たせたくない stable fixture では、高番 port の単純 UDP 往復へ寄せる方がよい

## `zeek_udp_roundtrip.pcap`

想定している論点:

- 最小の往復あり UDP 通信

raw pcap:

| No. | Time | Source | Destination | Protocol | Length | Info |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | `2022-01-01 09:00:00.000` | `192.168.0.10:40000` | `8.8.8.8:40001` | `UDP` | `43` | `40000 -> 40001 Len=1` |
| 2 | `2022-01-01 09:00:01.000` | `8.8.8.8:40001` | `192.168.0.10:40000` | `UDP` | `43` | `40001 -> 40000 Len=1` |

expected csv:

| No. | daytime | label | proto | id.orig_h | id.orig_p | id.resp_h | id.resp_p | conn_state | duration | orig_bytes | resp_bytes | orig_pkts | resp_pkts | orig_ip_bytes | resp_ip_bytes | missed_bytes | local_orig | local_resp |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | `2022-01-01 09:00:01` | `0` | `udp` | `192.168.0.10` | `40000` | `8.8.8.8` | `40001` | `SF` | `1.0` | `1` | `1` | `1` | `1` | `29` | `29` | `0` | `True` | `False` |

現在の扱い:

- `golden` の通常ケース

## `zeek_udp_malicious_roundtrip.pcap`

想定している論点:

- `label=1` になる malicious 通信

raw pcap:

| No. | Time | Source | Destination | Protocol | Length | Info |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | `2022-01-01 09:01:00.000` | `192.168.0.10:41000` | `10.0.0.5:41001` | `UDP` | `43` | `41000 -> 41001 Len=1` |
| 2 | `2022-01-01 09:01:02.000` | `10.0.0.5:41001` | `192.168.0.10:41000` | `UDP` | `43` | `41001 -> 41000 Len=1` |

expected csv:

| No. | daytime | label | proto | id.orig_h | id.orig_p | id.resp_h | id.resp_p | conn_state | duration | orig_bytes | resp_bytes | orig_pkts | resp_pkts | orig_ip_bytes | resp_ip_bytes | missed_bytes | local_orig | local_resp |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | `2022-01-01 09:01:02` | `1` | `udp` | `192.168.0.10` | `41000` | `10.0.0.5` | `41001` | `SF` | `2.0` | `1` | `1` | `1` | `1` | `29` | `29` | `0` | `True` | `True` |

現在の扱い:

- `golden` の通常ケース

## `zeek_udp_two_roundtrips.pcap`

想定している論点:

- 安定して通る複数行 `golden`

raw pcap:

| No. | Time | Source | Destination | Protocol | Length | Info |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | `2022-01-01 09:02:00.000` | `192.168.0.20:42000` | `8.8.8.8:42001` | `UDP` | `43` | `42000 -> 42001 Len=1` |
| 2 | `2022-01-01 09:02:01.000` | `8.8.8.8:42001` | `192.168.0.20:42000` | `UDP` | `43` | `42001 -> 42000 Len=1` |
| 3 | `2022-01-01 09:02:10.000` | `192.168.0.21:43000` | `1.1.1.1:43001` | `UDP` | `43` | `43000 -> 43001 Len=1` |
| 4 | `2022-01-01 09:02:12.000` | `1.1.1.1:43001` | `192.168.0.21:43000` | `UDP` | `43` | `43001 -> 43000 Len=1` |

expected csv:

| No. | daytime | label | proto | id.orig_h | id.orig_p | id.resp_h | id.resp_p | conn_state | duration | orig_bytes | resp_bytes | orig_pkts | resp_pkts | orig_ip_bytes | resp_ip_bytes | missed_bytes | local_orig | local_resp |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | `2022-01-01 09:02:01` | `0` | `udp` | `192.168.0.20` | `42000` | `8.8.8.8` | `42001` | `SF` | `1.0` | `1` | `1` | `1` | `1` | `29` | `29` | `0` | `True` | `False` |
| 2 | `2022-01-01 09:02:12` | `0` | `udp` | `192.168.0.21` | `43000` | `1.1.1.1` | `43001` | `SF` | `2.0` | `1` | `1` | `1` | `1` | `29` | `29` | `0` | `True` | `False` |

現在の扱い:

- `golden` の通常ケース

## `zeek_udp_exception_roundtrip.pcap`

想定している論点:

- `EXCEPTION` により record が除外されること

raw pcap:

| No. | Time | Source | Destination | Protocol | Length | Info |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | `2022-01-01 09:03:00.000` | `192.168.0.30:44000` | `8.8.8.8:44001` | `UDP` | `43` | `44000 -> 44001 Len=1` |
| 2 | `2022-01-01 09:03:01.000` | `8.8.8.8:44001` | `192.168.0.30:44000` | `UDP` | `43` | `44001 -> 44000 Len=1` |

expected csv:

- header-only CSV
- data row は 0 行

現在の扱い:

- `golden` の通常ケース

## `zeek_udp_interleaved.pcap`

想定している論点:

- 複数の UDP flow が時間的に前後しながら並ぶケース

raw pcap:

| No. | Time | Source | Destination | Protocol | Length | Info |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | `2022-01-01 09:00:00.000` | `192.168.0.10:45000` | `8.8.8.8:45001` | `UDP` | `43` | `45000 -> 45001 Len=1` |
| 2 | `2022-01-01 09:00:05.000` | `192.168.0.11:46000` | `1.1.1.1:46001` | `UDP` | `43` | `46000 -> 46001 Len=1` |
| 3 | `2022-01-01 09:00:06.000` | `1.1.1.1:46001` | `192.168.0.11:46000` | `UDP` | `43` | `46001 -> 46000 Len=1` |
| 4 | `2022-01-01 09:00:10.000` | `8.8.8.8:45001` | `192.168.0.10:45000` | `UDP` | `43` | `45001 -> 45000 Len=1` |

expected csv:

| No. | daytime | label | proto | id.orig_h | id.orig_p | id.resp_h | id.resp_p | conn_state | duration | orig_bytes | resp_bytes | orig_pkts | resp_pkts | orig_ip_bytes | resp_ip_bytes | missed_bytes | local_orig | local_resp |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | `2022-01-01 09:00:06` | `0` | `udp` | `192.168.0.11` | `46000` | `1.1.1.1` | `46001` | `SF` | `1.0` | `1` | `1` | `1` | `1` | `29` | `29` | `0` | `True` | `False` |
| 2 | `2022-01-01 09:00:10` | `0` | `udp` | `192.168.0.10` | `45000` | `8.8.8.8` | `45001` | `SF` | `10.0` | `1` | `1` | `1` | `1` | `29` | `29` | `0` | `True` | `False` |

現在の扱い:

- `golden` の通常ケース
- 以前は `udp/53` と 1 byte payload の組み合わせで DNS analyzer を刺激し、ローカル Zeek 7.0.10 で追加 row が出ていた
- 現在は高番 port に変更し、protocol 固有 analyzer の影響を避けている

## `zeek_udp_one_way.pcap`

想定している論点:

- 片方向にしか見えない UDP 通信

raw pcap:

| No. | Time | Source | Destination | Protocol | Length | Info |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | `2022-01-01 09:00:00.000` | `192.168.0.12:47000` | `9.9.9.9:47001` | `UDP` | `43` | `47000 -> 47001 Len=1` |

expected csv:

| No. | daytime | label | proto | id.orig_h | id.orig_p | id.resp_h | id.resp_p | conn_state | duration | orig_bytes | resp_bytes | orig_pkts | resp_pkts | orig_ip_bytes | resp_ip_bytes | missed_bytes | local_orig | local_resp |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | `2022-01-01 09:00:00` | `0` | `udp` | `192.168.0.12` | `47000` | `9.9.9.9` | `47001` | `S0` | `0` | `` | `` | `1` | `0` | `29` | `0` | `0` | `True` | `False` |

現在の扱い:

- `golden` の通常ケース
- `duration` は one-way row でも `0` を出す
- `orig_bytes` と `resp_bytes` は Zeek JSON に無ければ空文字のまま残す
