# `filebeat/conn_log.yml` 設計メモ

## 目的

このドキュメントは、Zeek `conn.log` を Elasticsearch へ送るための `filebeat/conn_log.yml` の設計方針をまとめるものである。

ここで定義したいのは次の点である。

- どのファイルを監視するか
- `conn.log` の各行をどう解釈するか
- どの index へ送るか
- 既存の `pcap_to_log_extractor.py` 出力とどう接続するか

## 前提

Zeek の `pcap -> log` 導線は既に存在する。

- 入口:
  - [pcap_to_log_extractor.py](/home/lemon/adids/src/util/FeatureExtract/Zeek/pcap_to_log_extractor.py)
- 設定:
  - [settings.json](/home/lemon/adids/src/util/FeatureExtract/Zeek/settings.json)
- 出力レイアウト:
  - `PcapToLog.OUTPUT_ROOT_DIR_PATH/<input_dir_name>/<timestamp>/...`

この配下に `conn.log` が生成される想定である。

## 想定する入力

最小構成では、Filebeat は Zeek の `conn.log` だけを読む。

監視対象のイメージ:

```text
data/logs/zeek/<dataset>/<batch>/conn.log
```

例:

```text
data/logs/zeek/synthetic_honeypot/20260513123000/conn.log
```

Phase 1 では `dns.log`, `http.log`, `ssl.log` は対象にしない。

## `filebeat/conn_log.yml` の責務

この設定ファイルの責務は限定する。

- `conn.log` の監視
- 各行 JSON の decode
- 送信先 index の指定
- 最小限の metadata 付与

逆に、次は責務に含めない。

- 複雑な条件分岐
- GeoIP enrich
- 複数ログ種別の正規化
- runtime 用 CSV 契約との整合調整

## 既存ファイルとの関係

### `filebeat.yml`

現状の [filebeat.yml](/home/lemon/adids/filebeat.yml) は、`ingest_data/*.log` を汎用的に読む簡易設定になっている。

今回の Zeek `conn.log` 可視化では、これを直接拡張するより、用途別に分けた方が安全である。

理由:

- 入力 path が Zeek 専用になる
- 将来別の Filebeat 設定と共存しやすい
- 旧来のテスト用途と切り分けられる

そのため、推奨は次のような配置である。

```text
filebeat/
  conn_log.yml
```

### `pcap_to_log_extractor.py`

Filebeat はこの出力を読むだけであり、`pcap_to_log_extractor.py` 自体には ELK 専用ロジックを持ち込まない。

接続はファイルシステム境界で行う。

```text
pcap_to_log_extractor.py -> data/logs/zeek/.../conn.log -> Filebeat
```

### `log_to_csv_extractor.py`

このスクリプトは runtime 導線用として別扱いである。
`filebeat/conn_log.yml` とは直接接続しない。

## 入力 path 設計

最初の設計では、次のような path 監視を想定する。

```yaml
paths:
  - /usr/share/filebeat/ingest_data/*/*/conn.log
```

または、ホスト側の mount 設計によっては次でもよい。

```yaml
paths:
  - /usr/share/filebeat/ingest_data/**/conn.log
```

ただし `**` に頼ると意図しないログまで拾う可能性があるため、最初はディレクトリ階層を明示した方が安全である。

推奨する mount 関係は次の通り。

- ホスト側:
  - `data/logs/zeek/`
- コンテナ側:
  - `/usr/share/filebeat/ingest_data/`

## JSON decode 方針

Zeek `conn.log` は JSON Lines なので、1 行 1 event として decode する。

そのため Filebeat 側では次のような考え方になる。

- line-oriented に読む
- 各行を JSON として decode する
- decode 後のフィールドを event 直下へ展開する

重要なのは `ts` の扱いである。
Zeek の `ts` は UNIX epoch 秒の浮動小数であるため、Kibana の時系列軸としては `@timestamp` が必要になる。

Phase 1 では、**Filebeat の `timestamp` processor で `ts` から `@timestamp` を作る**。

採用理由:

- 追加の ingest pipeline 登録が不要
- `docker compose up` の後に手作業を増やさずに済む
- `conn.log` 単体を最小構成で見るには十分である

Elastic 公式 docs:

- filestream / ndjson
  - https://www.elastic.co/docs/reference/beats/filebeat/filebeat-input-filestream
- timestamp processor
  - https://www.elastic.co/docs/reference/beats/filebeat/processor-timestamp

## フィールド方針

最初にそのまま保持したい主要フィールドは次である。

- `ts`
- `uid`
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

加えて、投入時に補助的に持たせたい metadata は次である。

- `event.dataset`
  - `zeek.conn`
- `labels.dataset_name`
  - `pcap` 入力ディレクトリ名
- `labels.batch_name`
  - Zeek batch ディレクトリ名
- `log.file.path`
  - 元ファイルの path

## dataset 名 / batch 名の扱い

Zeek の出力レイアウトは次のようになっている。

```text
<OUTPUT_ROOT_DIR_PATH>/<input_dir_name>/<timestamp>/conn.log
```

ここで、

- `<input_dir_name>` を dataset 名
- `<timestamp>` を batch 名

として扱うと、人間が見て追いやすい。

ただし Filebeat 単体で path 分解を複雑にやり始めると設定が重くなる。
そのため初期段階では次の 2 択とする。

1. 最初は path 分解をせず、`log.file.path` のみ保持する
2. 余裕があれば dissect processor で `dataset_name`, `batch_name` を切り出す

最小構成では 1 を推奨する。

## index 名

最初の index 名は固定でよい。

候補:

- `adids-zeek-conn`
- `zeek-conn-dev`

この段階では日次分割や data stream 化は必須ではない。
まずは 1 つの index に入れて可視化できることを優先する。

## 推奨する最小構成

`filebeat/conn_log.yml` の考え方は概ね次の通りである。

- `filestream` を使う
- `conn.log` のみ読む
- `ndjson` parser で JSON decode を行う
- `expand_keys` で `id.orig_h` などの dotted key を展開する
- `timestamp` processor で `ts` から `@timestamp` を作る
- `event.dataset=zeek.conn` を付ける
- Elasticsearch へ直接送る
- SSL / 認証は compose 側の既存方式に合わせる

## 避けたいこと

最初の段階では、次は避ける。

- `src/` 配下に Filebeat 設定生成コードを書く
- `pcap_to_log_extractor.py` に ELK 用分岐を入れる
- Logstash 前提で設計を始める
- `conn.log` 以外も同時に ingest しようとする

このあたりをやると、Phase 1 の目的に対して実装が重くなりやすい。

## 将来の拡張余地

後で次の拡張は可能である。

- `dns.log`, `http.log`, `ssl.log` の追加
- GeoIP enrich
- `adids` runtime 結果の別 index 追加
- dataset 名 / batch 名の厳密な field 化
- data stream や ILM への移行

## 次に詰めること

この設計メモの次に決めるべきなのは次の 2 点である。

- `docker-compose.yml` で `filebeat/conn_log.yml` をどう mount するか
- Kibana の Data View 名と初期 dashboard の定義をどうするか
