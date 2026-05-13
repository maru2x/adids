# ELK構成とデータフロー

## 目的

このドキュメントは、`adids` リポジトリで ELK 可視化をどう実現しているかを整理するためのものである。
対象は、`pcap -> Zeek conn.log -> Filebeat -> Elasticsearch -> Kibana` の最小導線である。

## 全体像

最小構成のデータフローは次の通り。

```text
pcap
  -> src/util/FeatureExtract/Zeek/pcap_to_log_extractor.py
  -> data/logs/zeek/<dataset>/<batch>/conn.log
  -> filebeat/conn_log.yml
  -> Elasticsearch
  -> Kibana
```

`adids` 本体 runtime の CSV 導線とは、`conn.log` を分岐点として切り分ける。

```text
pcap
  -> pcap_to_log_extractor.py
  -> conn.log
  -> log_to_csv_extractor.py
  -> data/csv/...
  -> make run
```

## なぜ `conn.log` を使うか

最初の可視化では、セッション単位の接続情報が見えれば十分である。
`conn.log` には次のような情報が入っている。

- `ts`
- `id.orig_h`, `id.orig_p`
- `id.resp_h`, `id.resp_p`
- `proto`
- `service`
- `duration`
- `orig_bytes`, `resp_bytes`
- `conn_state`

このため、CSV 変換や runtime に寄せず、`conn.log` を直接 ELK に入れる方が構成が単純である。

## 主なコンポーネント

### `src/util/FeatureExtract/Zeek/pcap_to_log_extractor.py`

- 役割: `pcap -> Zeek log`
- 入力: `PcapToLog.INPUT_DIR_PATH`
- 出力: `PcapToLog.OUTPUT_ROOT_DIR_PATH/<input_dir_name>/<timestamp>/...`
- ELK 側との接続点: `conn.log`

### `src/util/FeatureExtract/Zeek/log_to_csv_extractor.py`

- 役割: `conn.log -> runtime 用 CSV`
- ELK 可視化の最小構成では必須ではない
- `adids` 本体実験を並行して行うときに使う

### `filebeat/conn_log.yml`

- 役割: Zeek `conn.log` の監視と Elasticsearch への投入
- `filestream` + `ndjson` parser を使う
- `ts` から `@timestamp` を作る
- `event.dataset=zeek.conn` を付ける

### `docker-compose.yml`

- 役割: ローカルの ELK 起動基盤
- 最小構成で主に使う service:
  - `setup`
  - `es01`
  - `kibana`
  - `filebeat01`

### `src/util/ElasticSearch/es_utils.py`

- 役割: Elasticsearch 上のデータに対する分析補助
- ingest 処理そのものは担わない

## Filebeat 主軸の理由

最初の実装では Logstash を使わず、Filebeat 主軸とする。

理由:

- `conn.log` は JSON Lines で、そのまま読みやすい
- 最初に必要な変換が `ts -> @timestamp` 程度である
- Logstash を挟まない方がローカル構成が軽い
- 既存 `logstash.conf` は Zeek `conn.log` 前提ではない

## 監視 path と mount

Filebeat は次のレイアウトを前提にする。

```text
data/logs/zeek/<dataset>/<batch>/conn.log
```

`docker-compose.yml` では、主に次の mount を使う。

- `./data/logs/zeek/:/usr/share/filebeat/ingest_data/`
- `./filebeat/conn_log.yml:/usr/share/filebeat/filebeat.yml:ro`

## `ts -> @timestamp`

Phase 1 では Elasticsearch ingest pipeline ではなく、Filebeat の `timestamp` processor で `ts` を `@timestamp` に変換する。

理由:

- 追加の pipeline 登録手順が不要
- `docker compose up` 後の手作業が少ない
- 最小構成の検証には十分

## index と data view

確認用の入口としては `adids-zeek-conn` を使う。
既存データが混ざる場合は、scenario 単位で別 index に切り出して見る。

この session では、IoT-23 Mirai 34 の clean index として次を使った。

- index: `iot23-mirai34-clean`
- data view: `iot23-mirai34-clean`

## 既存プログラムとの関係

この構成では、ELK 専用ロジックを `src/` 配下へ深く持ち込まないことを優先する。

- 前処理は `src/util/FeatureExtract/Zeek/`
- ingest 設定は `filebeat/`
- 起動基盤は `docker-compose.yml`
- 可視化手順は docs

つまり、`adids` 本体に ELK の責務を混ぜすぎず、ファイル境界でつなぐ設計である。

## 今後の拡張候補

- `dns.log`, `http.log`, `ssl.log` の追加
- GeoIP enrich
- `adids` runtime 結果の別 index 追加
- Saved Objects の export ファイル管理
- Logstash 導入

## 関連ドキュメント

- 可視化手順: [ELKでデータを可視化する手順.md](./ELKでデータを可視化する手順.md)
- Kibana の使い方: [ELKの使い方.md](./ELKの使い方.md)
