# `docker-compose.yml` 構成メモ

## 目的

このドキュメントは、ELK 可視化用の `docker-compose.yml` をこのリポジトリ内でどう使うかを整理するためのメモである。

今回の最小目標は、次の導線をローカルで成立させることである。

```text
pcap
  -> pcap_to_log_extractor.py
  -> data/logs/zeek/<dataset>/<batch>/conn.log
  -> filebeat01
  -> es01
  -> kibana
```

## 使うサービス

Phase 1 で必須なのは次の 4 つである。

- `setup`
- `es01`
- `kibana`
- `filebeat01`

`metricbeat01` と `logstash01` は現状の compose に残っているが、Zeek `conn.log` 可視化の最小成立には不要である。

## 各サービスの役割

### `setup`

- CA と証明書を作る
- `kibana_system` の password を設定する

### `es01`

- Filebeat から受けた `conn.log` event を保存する

### `kibana`

- `adids-zeek-conn` index を可視化する

### `filebeat01`

- ホスト側 `data/logs/zeek/` を読む
- `filebeat/conn_log.yml` で `conn.log` を decode する
- Elasticsearch へ直接送る

## mount 設計

`filebeat01` は次の 2 つの mount が重要である。

- `./data/logs/zeek/:/usr/share/filebeat/ingest_data/`
- `./filebeat/conn_log.yml:/usr/share/filebeat/filebeat.yml:ro`

これにより、Zeek 出力と Filebeat 設定の接続をファイルシステム境界で完結させる。

## 既存ファイルとの関係

### `filebeat.yml`

ルートの [filebeat.yml](/home/lemon/adids/filebeat.yml) は旧来の簡易設定として残している。
現在の compose では [filebeat/conn_log.yml](/home/lemon/adids/filebeat/conn_log.yml) を優先して mount する。

### `logstash.conf`

[logstash.conf](/home/lemon/adids/logstash.conf) は現在の Zeek `conn.log` 可視化経路では使わない。
CSV サンプル投入用途の名残として扱う。

## なぜ Filebeat 直結にしたか

- `conn.log` は 1 行 1 JSON object である
- `ts -> @timestamp` も Filebeat processor で処理できる
- Logstash を挟まない方が構成が軽く、故障点も少ない

## `ts -> @timestamp` 方針

Phase 1 では、Elasticsearch ingest pipeline ではなく Filebeat の `timestamp` processor で `ts` を `@timestamp` に変換する。

採用理由:

- 追加の ingest pipeline 作成手順が不要
- `docker-compose up` 後の手作業が少ない
- 最初のローカル検証では十分に単純

## data path 前提

Filebeat が読む path は次を前提にする。

```text
data/logs/zeek/<dataset>/<batch>/conn.log
```

これは [pcap_to_log_extractor.py](/home/lemon/adids/src/util/FeatureExtract/Zeek/pcap_to_log_extractor.py) の現行出力レイアウトに合わせている。

## 今後の整理候補

将来的には次を行う余地がある。

- `metricbeat01` を profile 化する
- `logstash01` を compose から外す、または別 compose に分ける
- Filebeat 用の環境変数を Zeek 可視化用に整理する
- `dns.log` や `http.log` の ingest を別設定として追加する
