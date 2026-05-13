# ELKでデータを可視化する手順

## 目的

この手順は、Zeek `conn.log`、Cowrie `cowrie.json`、Cowrie 宛 traffic の Zeek live `conn.log` を Elasticsearch / Kibana で可視化する導線をローカルで確認するためのものである。

## 前提

- Docker / Docker Compose
- Zeek 前処理が実行できること
- `src/util/FeatureExtract/Zeek/settings_iot23_elk.json` を編集できること

前提となる構成は [ELK構成とデータフロー.md](./ELK構成とデータフロー.md) を参照。

## 1. 専用設定を確認する

[settings_iot23_elk.json](/home/mnl/adids/src/util/FeatureExtract/Zeek/settings_iot23_elk.json) の `PcapToLog.OUTPUT_ROOT_DIR_PATH` を確認する。

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
make elk-up
```

`make elk-up` は現在の canonical な最小構成として、`setup`, `es01`, `kibana`, `filebeat01` だけを起動する。
Zeek `conn.log` ingest には `filebeat/conn_log.yml` が使われる。

停止や状態確認には次を使う。

```bash
make elk-ps
make elk-down
```

`dataset_id` などの metadata を付けた Simulation 向け parallel ingest も起動したい場合は、代わりに次を使う。

```bash
make elk-up-simulation
```

Cowrie アプリケーションログ ingest を起動したい場合は、次を使う。

```bash
make elk-up-cowrie
```

この target は `setup`, `es01`, `kibana`, `filebeat-cowrie01` を起動し、`cowrie/var/log/cowrie/cowrie.json` を `cowrie-app-*` に投入する。

Cowrie app log と Zeek live flow の両方を扱いたい場合は、次を使う。

```bash
make elk-up-cowrie-live
```

この target は次を行う。

- `filebeat-cowrie01` を起動する
- `filebeat/cowrie_live_enrich_pipeline.json` を `zeek-cowrie-live-enrich-v1` として Elasticsearch に登録する
- その後で `filebeat-cowrie-live01` を起動する

GeoIP/ASN pipeline だけを再投入したい場合は、次を使う。

```bash
make es-put-cowrie-live-enrich-pipeline
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

Simulation metadata ingest を見る場合は、次の Data View も使える。

- Name: `zeek-pcap-simulation`
- Index pattern: `zeek-pcap-simulation-*`
- Timestamp field: `@timestamp`

Cowrie アプリケーションログを見る場合は、次の Data View を使う。

- Name: `cowrie-app`
- Index pattern: `cowrie-app-*`
- Timestamp field: `@timestamp`

Cowrie 宛 traffic の flow を見る場合は、次の Data View を使う。

- Name: `zeek-cowrie-live`
- Index pattern: `zeek-cowrie-live-*`
- Timestamp field: `@timestamp`

## 6. 実データを clean に切り出す

既存データが混ざる場合は、scenario 単位で別 index を作る。
この session では IoT-23 Mirai 34 用に次を使った。

- index: `iot23-mirai34-clean`
- data view: `iot23-mirai34-clean`

以後の可視化はこの clean data view を使うと分かりやすい。

metadata ingest を使う場合は、Kibana 側で `dataset_id` や `source_type` を列や filter に追加すると、複数 dataset を同じ index pattern で扱いやすい。

Cowrie app ingest を使う場合は、`eventid`, `src_ip`, `session`, `message`, `source_type` を列に追加すると読みやすい。

Cowrie live flow ingest を使う場合は、`id.orig_h`, `id.resp_h`, `id.resp_p`, `proto`, `conn_state`, `source_type` を列に追加すると読みやすい。
GeoIP/ASN enrich 後は、`source.ip`, `source.geo.country_name`, `source.as.organization.name` を列に追加すると realtime 監視に向く。

## 7. realtime Attack Monitoring dashboard を import する

現時点で repo に保存済みの reusable dashboard は次である。

- file: [cowrie_live_attack_monitoring.ndjson](/home/mnl/adids/docs/kibana_saved_objects/cowrie_live_attack_monitoring.ndjson)
- dashboard: `Cowrie Live Attack Monitoring`
- make target: `make kibana-import-cowrie-live-dashboard`

この dashboard は `zeek-cowrie-live-*` だけを対象にし、各 panel で次の条件を前提にしている。

```text
source_type : "cowrie_live" and id.resp_p : 2222 and proto : "tcp"
```

つまり、Cowrie 宛 SSH traffic の realtime 監視に絞った画面である。
現在の scope では `cowrie-app-*` は dashboard に含めない。

### canonical import

Kibana を起動した状態で、まず次を実行する。

```bash
make kibana-import-cowrie-live-dashboard
```

この target は `.env` の `ELASTIC_PASSWORD` と `KIBANA_PORT` を使い、repo 管理された `.ndjson` を Kibana API に `overwrite=true` で import する。

### 手動 import

1. `Stack Management -> Saved Objects`
2. `Import`
3. [cowrie_live_attack_monitoring.ndjson](/home/mnl/adids/docs/kibana_saved_objects/cowrie_live_attack_monitoring.ndjson) を指定する
4. 必要なら `Automatically overwrite conflicts` を有効にする

import 後に使える object は次である。

- data view: `zeek-cowrie-live`
- saved search: `Cowrie Live Recent Connections`
- visualization: `Cowrie Live SSH Hit Count`
- visualization: `Cowrie Live Unique Attackers`
- visualization: `Cowrie Live Top Countries`
- visualization: `Cowrie Live Top ASNs`
- visualization: `Cowrie Live Events Over Time`
- visualization: `Cowrie Live Top Source IPs`
- map: `Cowrie Live Attack Map`
- dashboard: `Cowrie Live Attack Monitoring`

補足:

- `source.ip`, `source.geo.*`, `source.as.*` は `zeek-cowrie-live-enrich-v1` で付与する
- localhost からの手動接続では `source.ip` が Docker bridge の private address になるため、GeoIP country / ASN / map は空でも正常である
- public source IP が入ってきたときに `Top Countries`, `Top ASNs`, `Cowrie Live Attack Map` が効いてくる

## 8. 参考: static analysis 用の最初の dashboard 3 枚

static analysis の詳細仕様は今後詰める前提だが、IoT-23 のような既存 dataset を見る最小例としては次の 3 枚で十分である。

- `IoT23 Mirai 34 Events Over Time`
- `IoT23 Mirai 34 Top Source IPs`
- `IoT23 Mirai 34 Top Destination Ports`

これらをまとめた dashboard として、次を使う。

- `IoT23 Mirai 34 Dashboard`

## 9. Saved Objects を保存する

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

## 10. 実データ投入時の最低確認

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
- `filebeat/conn_log.yml` が `docker-compose.yml` から mount されていることを確認する

### `cowrie-app-*` に document が出ない

- `make cowrie-ps` で Cowrie container が `Up` か確認する
- `cowrie/var/log/cowrie/cowrie.json` が存在するか確認する
- `make elk-up-cowrie` で `filebeat-cowrie01` を起動したか確認する
- Cowrie に実際に接続して event を発生させたか確認する

### `zeek-cowrie-live-*` に document が出ない

- `make cowrie-live-up` で `zeek-cowrie-live` を起動したか確認する
- `data/logs/zeek/live/cowrie/current/conn.log` が存在するか確認する
- `make elk-up-cowrie-live` で `filebeat-cowrie-live01` を起動したか確認する
- Cowrie に実際に接続して traffic を発生させたか確認する

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
