# ELK構成とデータフロー

## 目的

このドキュメントは、`adids` リポジトリで ELK 可視化をどう実現しているかを整理するためのものである。
対象は、`pcap -> Zeek conn.log -> Filebeat -> Elasticsearch -> Kibana` の最小導線、`Cowrie JSON log -> Filebeat -> Elasticsearch -> Kibana` の攻撃行動導線、`Cowrie 宛 traffic -> Zeek live conn.log -> Filebeat -> Elasticsearch -> Kibana` の flow 監視導線である。

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

metadata 付きの Simulation 向け並行 ingest を使う場合は、次の経路も使える。

```text
pcap
  -> src/util/FeatureExtract/Zeek/pcap_to_log_extractor.py
  -> data/logs/zeek/<dataset>/<batch>/conn.log
  -> filebeat/simulation_conn_log.yml
  -> Elasticsearch index: zeek-pcap-simulation-*
  -> Kibana
```

Cowrie アプリケーションログを ELK に入れる場合は、次の経路を使う。

```text
Cowrie
  -> cowrie/var/log/cowrie/cowrie.json
  -> filebeat/cowrie_json.yml
  -> Elasticsearch index: cowrie-app-*
  -> Kibana
```

Cowrie 宛 traffic を Zeek live capture で ELK に入れる場合は、次の経路を使う。

```text
Cowrie-bound traffic
  -> zeek-cowrie-live
  -> data/logs/zeek/live/cowrie/current/conn.log
  -> filebeat/cowrie_live_conn_log.yml
  -> Elasticsearch index: zeek-cowrie-live-*
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
- 現在の canonical な ELK ingest 設定

### `filebeat/simulation_conn_log.yml`

- 役割: Zeek `conn.log` を metadata 付きで `zeek-pcap-simulation-*` に投入する
- `log.file.path` から `dataset_id` と `batch_name` を取り出す
- `source_type=simulation_pcap` と `sensor_id=pcap-importer-01` を付ける
- 既存の `adids-zeek-conn` 最小導線とは parallel に動かす

### `filebeat/cowrie_json.yml`

- 役割: Cowrie `cowrie.json` を `cowrie-app-*` に投入する
- `timestamp` から `@timestamp` を作る
- `source_type=cowrie_app` と `sensor_id=cowrie-honeypot-01` を付ける
- `event.dataset=cowrie.app` を付ける

### `filebeat/cowrie_live_conn_log.yml`

- 役割: Cowrie 宛 traffic の Zeek live `conn.log` を `zeek-cowrie-live-*` に投入する
- `ts` から `@timestamp` を作る
- `source_type=cowrie_live` と `sensor_id=zeek-cowrie-live-01` を付ける
- `capture_id` として現在は `current` を path から取り出す
- `output.elasticsearch.pipeline = zeek-cowrie-live-enrich-v1` を通す
- pipeline では `source.ip`, `destination.ip`, `destination.port`, `source.geo.*`, `source.as.*` を付ける

### `docker-compose.yml`

- 役割: ローカルの ELK 起動基盤
- 最小構成で主に使う service:
  - `setup`
  - `es01`
  - `kibana`
  - `filebeat01`
- 通常は `make elk-up` / `make elk-down` / `make elk-ps` から使う
- metadata 付き Simulation ingest も含める場合は `make elk-up-simulation` を使う
- Cowrie アプリケーションログ ingest を含める場合は `make elk-up-cowrie` を使う
- Cowrie app log と Zeek live flow の両方を含める場合は `make elk-up-cowrie-live` を使う

### `docker-compose.cowrie.yml`

- 役割: Cowrie 単体基盤と Zeek live sidecar の起動基盤
- `cowrie` 単体だけを起動することもできる
- `zeek-cowrie-live` は `network_mode: service:cowrie` で同じ network namespace を共有し、`eth0` を `zeek -i` で監視する

### `src/util/ElasticSearch/es_utils.py`

- 役割: Elasticsearch 上のデータに対する分析補助
- ingest 処理そのものは担わない

## Filebeat 主軸の理由

最初の実装では Logstash を使わず、Filebeat 主軸とする。

理由:

- `conn.log` は JSON Lines で、そのまま読みやすい
- 最初に必要な変換が `ts -> @timestamp` 程度である
- `cowrie.json` も JSON Lines で、そのまま読みやすい
- live 側もまず `conn.log` に絞れば設定を増やしすぎずに flow-level 可視化を始められる
- Logstash を挟まない方がローカル構成が軽い
- 既存 `logstash.conf` は Zeek `conn.log` 前提ではない

補足:

- repo 直下の `filebeat.yml` は current path では使っていない
- repo 直下の `logstash.conf` は旧検証用サンプルであり、現行の `conn.log` ingest の canonical path ではない

## 監視 path と mount

Filebeat は次のレイアウトを前提にする。

```text
data/logs/zeek/<dataset>/<batch>/conn.log
```

`docker-compose.yml` では、主に次の mount を使う。

- `./data/logs/zeek/:/usr/share/filebeat/ingest_data/`
- `./filebeat/conn_log.yml:/usr/share/filebeat/filebeat.yml:ro`

Cowrie app ingest では、次のレイアウトを前提にする。

```text
cowrie/var/log/cowrie/cowrie.json
```

対応する主な mount は次である。

- `./cowrie/var/log/cowrie/:/usr/share/filebeat/ingest_data/:ro`
- `./filebeat/cowrie_json.yml:/usr/share/filebeat/filebeat.yml:ro`

Cowrie live Zeek ingest では、次のレイアウトを前提にする。

```text
data/logs/zeek/live/cowrie/current/conn.log
```

対応する主な mount は次である。

- `./data/logs/zeek/live/cowrie/:/usr/share/filebeat/ingest_data/:ro`
- `./filebeat/cowrie_live_conn_log.yml:/usr/share/filebeat/filebeat.yml:ro`

## `ts -> @timestamp`

Phase 1 では Elasticsearch ingest pipeline ではなく、Filebeat の `timestamp` processor で `ts` を `@timestamp` に変換する。

理由:

- 追加の pipeline 登録手順が不要
- `docker compose up` 後の手作業が少ない
- 最小構成の検証には十分

## index と data view

確認用の入口としては `adids-zeek-conn` を使う。
既存データが混ざる場合は、scenario 単位で別 index に切り出して見る。

dataset 単位の metadata を明示的に持たせたい場合は、次の data view を使う。

- index pattern: `zeek-pcap-simulation-*`
- 主な追加 field:
  - `dataset_id`
  - `batch_name`
  - `source_type`
  - `sensor_id`

Cowrie の攻撃者行動を見る場合は、次の data view を使う。

- index pattern: `cowrie-app-*`
- 主な field:
  - `eventid`
  - `src_ip`
  - `session`
  - `source_type`
  - `sensor_id`

Cowrie 宛 traffic の flow を見る場合は、次の data view を使う。

- index pattern: `zeek-cowrie-live-*`
- 主な field:
  - `id.orig_h`
  - `id.resp_h`
  - `id.resp_p`
  - `conn_state`
  - `source_type`
  - `sensor_id`

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
- Cowrie live 側の `ssh.log` / `notice.log` / `weird.log` ingest 追加
- GeoIP enrich
- `adids` runtime 結果の別 index 追加
- `zeek-pcap-simulation-*` や比較系 dashboard の追加
- Logstash 導入

現在の Saved Objects export は次で管理する。

- [cowrie_live_attack_monitoring.ndjson](/home/mnl/adids/docs/kibana_saved_objects/cowrie_live_attack_monitoring.ndjson)

import の canonical な入口は次である。

- `make kibana-import-cowrie-live-dashboard`

live GeoIP/ASN pipeline の canonical な入口は次である。

- `make es-put-cowrie-live-enrich-pipeline`

## 関連ドキュメント

- 可視化手順: [ELKでデータを可視化する手順.md](./ELKでデータを可視化する手順.md)
- Kibana の使い方: [ELKの使い方.md](./ELKの使い方.md)
