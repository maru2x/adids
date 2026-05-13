# ELK ingest設計メモ

## 目的

このメモは、[ELK再構築方針.md](./ELK再構築方針.md) を受けて、Zeek `conn.log` を Elasticsearch に投入する最小構成を具体化するための設計メモである。

ここで整理するのは次の 3 点である。

- Logstash と Filebeat のどちらを主軸にするか
- 既存ファイルをどう整理するか
- どのフィールドを最初に Elasticsearch へ載せるか

## 結論

最初の実装では、**Filebeat 主軸、Logstash は使わないか任意** とする。

理由は次の通り。

- Zeek `conn.log` は JSON Lines であり、Filebeat で素直に取り込める
- 最初の段階では複雑な変換が不要である
- Logstash を入れない方がローカル構成が軽く、切り分けも簡単である
- 既存の `logstash.conf` は現状 `conn.log` 用ではなく、流用より整理が先である

したがって、Phase 1 の最小構成は次を想定する。

```text
pcap
  -> pcap_to_log_extractor.py
  -> conn.log
  -> Filebeat
  -> Elasticsearch
  -> Kibana
```

## コンポーネントごとの役割

### Zeek 前処理

- 担当:
  - `src/util/FeatureExtract/Zeek/pcap_to_log_extractor.py`
- 役割:
  - `pcap` から Zeek ログ群を作る
- ELK 側との接点:
  - 出力された `conn.log`

### Filebeat

- 担当:
  - 将来的には `filebeat/conn_log.yml` のような専用設定
- 役割:
  - `conn.log` を監視し、各行を Elasticsearch に送る
- この段階でやること:
  - `@timestamp` を `ts` から作る
  - index 名を分ける
  - 必要最低限のフィールド整形を行う

### Elasticsearch

- 担当:
  - `docker-compose.yml` 上の `es01`
- 役割:
  - `conn.log` 由来レコードの保存
  - Kibana からの集計対象

### Kibana

- 担当:
  - `docker-compose.yml` 上の `kibana`
- 役割:
  - `conn.log` データの可視化
  - index pattern / data view の作成

### Logstash

- 初期段階の扱い:
  - 必須ではない
- 将来的な役割:
  - GeoIP 付与
  - 複雑な rename / enrichment
  - 複数データ源の正規化

## なぜ Logstash ではなく Filebeat から始めるか

### 1. `conn.log` はすでに構造化されている

`conn.log` は Zeek により JSON として出力される。
そのため、CSV のような列定義や delimiter 解釈を後段で行う必要がない。

### 2. 変換量が少ない

最初に必要なのは主に次の程度である。

- `ts` を時刻として解釈する
- index 名を分ける
- 必要に応じて dataset 名や batch 名を補助フィールドとして持つ

この程度なら Logstash を必須にする理由は薄い。

### 3. 既存 `logstash.conf` が別用途である

現状の [logstash.conf](/home/lemon/adids/logstash.conf) は CSV サンプル投入用であり、Zeek `conn.log` を前提にしていない。
最初からこれを改造すると、旧用途の名残と新用途が混ざりやすい。

## 既存ファイルとの関係

### `docker-compose.yml`

現状の compose は Elastic Stack 一式を起動するための土台として残せる。
ただし、最小構成に絞るなら次の観点で整理する必要がある。

- `es01`
- `kibana`
- `filebeat01`

少なくとも最初はこの 3 つで十分である。
`metricbeat01` と `logstash01` は後回しでもよい。

### `filebeat.yml`

現状の [filebeat.yml](/home/lemon/adids/filebeat.yml) は汎用 `filestream` 設定である。
最初の実装では、これを直接上書きするよりも、Zeek `conn.log` 用として分離した方がよい。

候補:

- `filebeat/conn_log.yml`
- `filebeat/zeek_conn.yml`

分離する理由は次の通り。

- 入力対象が明確になる
- 旧来の試験設定と混ざらない
- 将来 `dns.log`, `http.log`, `ssl.log` を追加しやすい

### `logstash.conf`

現状の [logstash.conf](/home/lemon/adids/logstash.conf) は archive 的な位置づけに近い。

扱いの候補:

- そのまま残して Zeek 用は別ファイルにする
- Zeek 再構築後に不要なら整理対象とする

最初の段階では、無理にこれへ寄せない方が安全である。

### `src/util/ElasticSearch/es_utils.py`

このファイルは ingest 設定ではなく、Elasticsearch に載った後の分析補助として扱う。
たとえば、Kibana 以外に Python から minute 集計を取りたい場合に再利用可能である。

## 推奨配置

```text
adids/
├─ docker-compose.yml
├─ filebeat/
│  └─ conn_log.yml
├─ docs/
│  ├─ ELK再構築方針.md
│  └─ ELK ingest設計メモ.md
├─ data/
│  └─ logs/zeek/<dataset>/<batch>/conn.log
├─ src/util/FeatureExtract/Zeek/
│  ├─ settings.json
│  └─ pcap_to_log_extractor.py
└─ src/util/ElasticSearch/
   └─ es_utils.py
```

## `ts -> @timestamp` 方針

Phase 1 では Elasticsearch ingest pipeline ではなく、Filebeat の `timestamp` processor を使う。

この判断は Elastic の公式 docs にある次の仕様に基づく。

- `filestream` は `ndjson` parser で 1 行 1 JSON object を decode できる
- `timestamp` processor は source field を解析して既定で `@timestamp` に書ける
- `layouts` に `UNIX` を指定できる

公式 docs:

- filestream / ndjson
  - https://www.elastic.co/docs/reference/beats/filebeat/filebeat-input-filestream
- timestamp processor
  - https://www.elastic.co/docs/reference/beats/filebeat/processor-timestamp

この方針により、追加の ingest pipeline 登録手順を省ける。

## 最初に載せるフィールド

最初の可視化に必要なフィールドは次で十分である。

- `@timestamp`
- `ts`
- `id.orig_h`
- `id.orig_p`
- `id.resp_h`
- `id.resp_p`
- `proto`
- `service`
- `duration`
- `orig_bytes`
- `resp_bytes`
- `conn_state`
- `local_orig`
- `local_resp`

必要なら次を後で追加する。

- dataset 名
- batch 名
- 入力元ファイル名
- GeoIP 由来の国情報

## index 設計の初期案

最初の実装では、単一用途で分かりやすい index 名にする。

候補:

- `zeek-conn-dev`
- `zeek-conn-lab`
- `adids-zeek-conn`

この段階では日次 roll over や ILM は必須ではない。
まずは small dataset で見えることを優先する。

## Kibana で最初に作る可視化

- 時系列の flow 数
- 送信元 IP 上位
- 宛先ポート上位
- `proto` 分布
- `service` 分布
- `conn_state` 分布
- `orig_bytes` / `resp_bytes` の分布

GeoIP を入れる場合は、送信元国分布を追加する。

## 将来 Logstash を足す条件

次のいずれかが必要になったら Logstash を追加する。

- GeoIP を pipeline 側で付与したい
- 複数種の Zeek log を同時正規化したい
- 文字列 rename や条件分岐が増える
- 外部 feed との join に近い enrichment が必要になる

この条件に達するまでは、Filebeat のみで進める。

## 次の実装 issue 候補

- `filebeat/conn_log.yml` の新設
- `docker-compose.yml` を最小構成で起動できるよう整理
- `conn.log` の index 名と data view 名の決定
- synthetic `pcap` を使った ingest 手順書の作成

`filebeat/conn_log.yml` 単体の設計は [filebeat_conn_log設計.md](./filebeat_conn_log設計.md) を参照。
compose 側の考え方は [docker_compose構成メモ.md](./docker_compose構成メモ.md) を参照。
