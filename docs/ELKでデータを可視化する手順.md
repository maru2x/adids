# ELKでデータを可視化する手順

## 目的

この手順は、Zeek `conn.log` を Elasticsearch / Kibana で可視化する最小導線をローカルで確認するためのものである。

## 前提

- Docker / Docker Compose
- Zeek 前処理が実行できること
- `src/util/FeatureExtract/Zeek/settings_iot23_elk.json` を編集できること

前提となる構成は [ELK構成とデータフロー.md](./ELK構成とデータフロー.md) を参照。

## 1. 専用設定を確認する

[settings_iot23_elk.json](/home/lemon/adids/src/util/FeatureExtract/Zeek/settings_iot23_elk.json) の `PcapToLog.OUTPUT_ROOT_DIR_PATH` を確認する。

この手順では、`docker-compose.yml` 側が次を読む前提になっている。

```text
data/logs/zeek/
```

## 2. `pcap` から `conn.log` を作る

`PcapToLog.INPUT_DIR_PATH` を対象 dataset に合わせて設定し、次を実行する。

```bash
make pcap-to-log PCAP_TO_LOG_ARGS="--settings src/util/FeatureExtract/Zeek/settings_iot23_elk.json"
```

成功すると次のレイアウトで Zeek ログが出力される。

```text
data/logs/zeek/<dataset>/<batch>/conn.log
```

## 3. ELK を起動する

`.env` に必要な環境変数が入っていることを確認して、次を実行する。

```bash
docker compose up -d setup es01 kibana filebeat01
```

## 4. Kibana を開く

```text
http://localhost:${KIBANA_PORT}
```

通常は `elastic` ユーザーでログインする。

## 5. Data View を作る

まずは ingest 確認用として `adids-zeek-conn` の Data View を作る。

- Name: `adids-zeek-conn`
- Index pattern: `adids-zeek-conn`
- Timestamp field: `@timestamp`

## 6. 実データを clean に切り出す

既存データが混ざる場合は、scenario 単位で別 index を作る。
この session では IoT-23 Mirai 34 用に次を使った。

- index: `iot23-mirai34-clean`
- data view: `iot23-mirai34-clean`

以後の可視化はこの clean data view を使うと分かりやすい。

## 7. 最初の dashboard 3 枚

最初の可視化は次の 3 枚で十分である。

- `IoT23 Mirai 34 Events Over Time`
- `IoT23 Mirai 34 Top Source IPs`
- `IoT23 Mirai 34 Top Destination Ports`

これらをまとめた dashboard として、次を使う。

- `IoT23 Mirai 34 Dashboard`

## 8. Saved Objects を保存する

Kibana 上で作った data view / saved search / visualization / dashboard は、repo に自動保存されない。
再利用したい場合は `Saved Objects` から export する。

### export

1. `Stack Management -> Saved Objects`
2. 対象 object を選択する
3. `Export`
4. `Include related objects` を有効にする
5. `.ndjson` を保存する

### import

1. `Stack Management -> Saved Objects`
2. `Import`
3. `.ndjson` を指定する
4. 必要なら `Automatically overwrite conflicts` を有効にする

## 9. 実データ投入時の最低確認

```bash
tail -n 5 data/logs/zeek/<dataset>/<batch>/conn.log
```

確認したいこと:

- 空行が混ざっていない
- 各行が 1 個の JSON object である
- `ts` が入っている

## 想定トラブル

### `conn.log` が見つからない

- `make pcap-to-log` が成功しているか確認する
- `data/logs/zeek/<dataset>/<batch>/conn.log` が存在するか確認する
- `docker-compose.yml` の mount path が出力先と一致しているか確認する

### Kibana に document が出ない

- `filebeat01` が起動しているか確認する
- `es01` が healthy か確認する
- `conn.log` が 1 行 1 JSON 形式であることを確認する

### `@timestamp` が空になる

- `ts` が入っているか確認する
- `filebeat/conn_log.yml` の `timestamp` processor が有効か確認する

### `error.type=json` の event しか出ない

- `conn.log` に空行が混ざっていないか確認する
- `conn.log` が 1 行 1 JSON object になっているか確認する
- 新しい batch ディレクトリを切って Filebeat に新規ファイルとして読ませる

## 関連ドキュメント

- 構成とフロー: [ELK構成とデータフロー.md](./ELK構成とデータフロー.md)
- Kibana の使い方: [ELKの使い方.md](./ELKの使い方.md)
