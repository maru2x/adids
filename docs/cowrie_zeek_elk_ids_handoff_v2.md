# タスク引継ぎドキュメント: Cowrie + Zeek + ELK + IDS学習基盤

## 1. 背景

本タスクでは、IoT機器を狙う外部攻撃通信を観測し、監視・分析・IDS学習に利用するための基盤を設計・実装する。

当初は T-Pot の利用を検討していたが、T-Pot は複数ハニーポット、ELK、Attack Map を含む全部入り基盤であり、本研究の中心である「Zeek特徴量への変換」と「IDSの再学習」に対しては過剰であると判断した。

最終方針は、T-Pot をそのまま採用するのではなく、次を組み合わせる構成である。

- Cowrie: SSH/Telnet 型攻撃通信を観測するハニーポット
- Zeek: 既存 pcap と将来の live traffic の両方を解析するトラフィック解析ツール
- ELK Stack: Zeek ログおよび Cowrie ログを監視・検索・可視化する分析基盤
- Simulation runtime: 既存 pcap から生成した CSV を読み、推論・評価・再学習を行う既存 `make run` 導線
- feature exporter: Zeek ログを Simulation runtime 互換 CSV または将来の feature store へ変換する処理

## 2. このドキュメントの位置づけ

このドキュメントは、repo の現状と将来実装の両方を扱う。

重要なのは、ここで書く内容がすべて「すでに実装済み」を意味するわけではない点である。

この文書では、常に次の優先順位を取る。

1. 現在の code と既存 docs が示す実装事実
2. それを壊さない範囲での拡張計画
3. 外部環境依存の運用手順

repo 現状と食い違う記述があった場合は、次の docs / code を優先する。

- `README.md`
- `docs/設定ファイルの各種パラメータ.md`
- `docs/CSVスキーマ仕様.md`
- `docs/ELK構成とデータフロー.md`
- `docs/ELKでデータを可視化する手順.md`
- `docs/ELKの使い方.md`
- `src/util/FeatureExtract/Zeek/`
- `src/main/`

特に用語として、repo 現状に合わせて次を採用する。

- `Simulation`
  - 既存 pcap から生成した leaf CSV を `make run` へ渡して擬似リアルタイム実験を行う経路
- `Live`
  - 将来追加するリアルタイム観測・投入経路

したがって、以前この文書で `offline` と呼んでいたもののうち、`pcap -> csv -> make run` の実験導線は本書では `Simulation` と呼ぶ。

## 3. 現在のリポジトリ前提

現時点の repo 事実を先に固定する。

| 項目 | 現在の canonical な事実 |
|---|---|
| 実行本体 | `make run` は実質的に `Simulation` runtime であり、`Live` runtime は未実装 |
| 安定した前処理 | `make pcap-to-log` -> `make log-to-csv` -> `make run` |
| 省略導線 | `make pcap-to-csv` は上記 2 段をまとめて実行する |
| runtime 入力契約 | `DATASETS_DIR_PATH` は CSV ファイルだけが並ぶ leaf ディレクトリである必要がある |
| Zeek CSV 変換 | `src/util/FeatureExtract/Zeek/log_to_csv_extractor.py` が `daytime` / `label` 付与を含めた Simulation 向け変換を担う |
| 現在の ELK 最小導線 | `pcap -> conn.log -> filebeat/conn_log.yml -> Elasticsearch -> Kibana` |
| 現在の Simulation metadata ingest | `pcap -> conn.log -> filebeat/simulation_conn_log.yml -> zeek-pcap-simulation-*` |
| 現在の Cowrie 単体基盤 | `docker-compose.cowrie.yml` と `make cowrie-up` / `make cowrie-down` / `make cowrie-ps`。`cowrie/var/log/cowrie/cowrie.json` への最小出力までは確認済み |
| 現在の Cowrie app ingest | `cowrie/var/log/cowrie/cowrie.json -> filebeat/cowrie_json.yml -> cowrie-app-*` |
| 現在の Cowrie live flow ingest | `zeek -i eth0 -> data/logs/zeek/live/cowrie/current/conn.log -> filebeat/cowrie_live_conn_log.yml -> zeek-cowrie-live-*` |
| 現在の Cowrie live enrich | `filebeat/cowrie_live_enrich_pipeline.json` と `make es-put-cowrie-live-enrich-pipeline` により、`source.ip`, `source.geo.*`, `source.as.*` を live index に付与できる |
| 現在の generalized feature export | `feature_exporter.py` で Zeek `conn.log` を runtime 互換 leaf CSV に出力できる |
| 現在の realtime dashboard | `docs/kibana_saved_objects/cowrie_live_attack_monitoring.ndjson` と `make kibana-import-cowrie-live-dashboard` により、GeoIP/ASN/map を含む `zeek-cowrie-live-*` ベースの `Cowrie Live Attack Monitoring` を再現できる |
| ELK の canonical 設定 | `docker-compose.yml` と `filebeat/conn_log.yml` が現在の標準経路 |
| 非 canonical な設定 | root の `filebeat.yml` と `logstash.conf` は、現状の Zeek `conn.log` 可視化の標準構成ではない |

ここで特に重要なのは、現在の repo にはすでに「Zeek ログを 2 方向へ分岐する」発想が存在していることだ。

```text
pcap
  -> pcap_to_log_extractor.py
  -> data/logs/zeek/<dataset>/<batch>/conn.log
      -> ELK ingest
      -> log_to_csv_extractor.py
      -> data/csv/zeek/conn/<batch>/*.csv
      -> make run
```

この分岐構造は、今後も壊さない方針で進める。

## 4. 目的

この基盤の目的は大きく 4 つである。

1. 既存 pcap を Zeek で解析し、ELK 上で監視・分析できるようにする
2. 将来的に Cowrie に到達する攻撃通信をリアルタイムに監視できるようにする
3. Zeek 由来データを Simulation runtime と整合する形で特徴量化する
4. 将来的に Cowrie 由来の悪性通信と GW 由来の良性通信を、同一の特徴量空間へ寄せて再学習実験に利用できるようにする

## 5. 主要な設計方針

### 5.1 Zeek を中心にする

pcap と live traffic は入口が異なるが、どちらも Zeek で解析できる。

- 既存 pcap: `zeek -r file.pcap`
- live traffic: `zeek -i <interface>`

したがって、入力を無理に統一するのではなく、Zeek 出力を共通化する。

### 5.2 ELK と IDS runtime は分離する

Elasticsearch に入れたログをそのまま `make run` に食べさせる構成にはしない。

理由は次の通り。

- ELK は人間が見る監視・検索・可視化基盤である
- Simulation runtime は leaf CSV 契約に強く依存している
- 現在の `src/main/` は Elasticsearch reader を持っていない

したがって、Zeek ログの出力先は今後も並列に保つ。

- ELK 側: 監視・検索・可視化用
- Simulation 側: CSV / feature buffer / 再学習入力用

### 5.3 Simulation 導線を既存の基準線として扱う

この repo では、現在動いている IDS 側の主導線は `Simulation` である。

つまり、`pcap -> Zeek log -> CSV -> make run` が現在の基準線であり、将来の拡張はこの基準線を維持する形で積む。

ここは「慎重に触る」のではなく、原則として変更対象にしない。
将来の ELK / Cowrie 拡張においては、まず既存基盤として固定寄りに扱い、周辺へ sidecar 的に機能を追加する。

したがって、次は通常の拡張対象ではない。

- `src/main/` の既存 runtime 導線
- `make run` の leaf CSV 契約
- `pcap -> csv` の既存 batch / output layout

これらに手を入れてよいのは、次のような blocker が明確にある場合だけとする。

- 現行導線そのものに実バグがある
- 新しい metadata や export を載せるために、互換性を維持した最小変更が必要
- 既存処理を再利用するために、挙動を変えない安全な分離が必要

- `DATASETS_DIR_PATH` の leaf CSV 契約を壊さない
- 既存 `FeatureSchema` の期待列を壊さない
- `pcap_to_log_extractor.py` / `log_to_csv_extractor.py` のレイアウト契約を簡単には変えない

### 5.4 Cowrie ログは主特徴量ではなく補助情報とする

Cowrie ログには以下のような情報が含まれる。

- username
- password
- login success / failure
- executed command
- download URL
- session id

これらは攻撃行動の理解には有用だが、家庭 GW 側の良性通信には存在しない。
そのため、IDS の主特徴量に直接入れるとデータリークや過適合の原因になる。

主特徴量は Zeek 由来のフロー特徴量を中心にし、Cowrie ログはラベル補強や attack context 付与の補助として扱う。

重要なのは、ここでいう Cowrie ログが `src/main/` runtime へ直接流し込まれる想定ではない点である。

現在の runtime は Zeek `conn.log` 由来の flow 特徴量前提であり、`cowrie.json` のような app log をそのまま学習入力にしない。

したがって、`cowrie.json` の役割は次に留める。

- ELK 上での攻撃者行動監視
- Zeek flow との対応付けに使う補助 context
- 将来必要ならラベル補強や相関分析に使う補助情報

### 5.5 まず sidecar で拡張し、既存 core はむやみに触らない

今後の実装では、次を優先する。

- 新しい ingest 設定
- 新しい helper script
- 新しい feature export 処理
- 新しい docs / tests

逆に、次の core はデフォルトでは変更しない。

- `src/main/` runtime の入出力契約
- `pcap_to_log_extractor.py` の batch layout
- `log_to_csv_extractor.py` の leaf CSV layout

## 6. 現在の安定導線

### 6.1 現在の最小 ELK 導線

現在、repo で動作確認済みなのは次の最小導線である。

```text
pcap
  -> src/util/FeatureExtract/Zeek/pcap_to_log_extractor.py
  -> data/logs/zeek/<dataset>/<batch>/conn.log
  -> filebeat/conn_log.yml
  -> Elasticsearch index: adids-zeek-conn
  -> Kibana
```

起動・停止・状態確認は、現在は次を canonical な入口とする。

```bash
make elk-up
make elk-ps
make elk-down
```

dataset / source metadata を付けた Simulation 向け parallel ingest も、現在は次で起動できる。

```bash
make elk-up-simulation
```

この経路の canonical docs は次である。

- `docs/ELK構成とデータフロー.md`
- `docs/ELKでデータを可視化する手順.md`
- `docs/ELKの使い方.md`

### 6.2 現在の Simulation 導線

同じ `conn.log` を分岐して、既存 runtime へ流す導線がある。

```text
pcap
  -> pcap_to_log_extractor.py
  -> data/logs/zeek/<dataset>/<batch>/conn.log
  -> log_to_csv_extractor.py
  -> data/csv/zeek/conn/<batch>/*.csv
  -> make run
```

この導線では、`log_to_csv_extractor.py` がすでに次を担っている。

- JSON Lines の streaming 読み取り
- `ts + duration` ベースの `daytime` 生成
- `NetworkAddress` による除外と label 付与
- runtime 互換 CSV の chunk 出力

つまり、現時点でも「Zeek ログから Simulation 互換 CSV を作る normalizer 的責務」はすでに一部実装済みである。

## 7. 目標アーキテクチャ

最終的には、`Simulation` 系と `Live` 系を次のように並立させる。

### 7.1 Simulation 系

`Simulation` 系は、既存 pcap を使った研究・再現・評価のための導線である。

```text
既存 pcap
  ↓
Zeek batch解析 (`zeek -r`)
  ↓
Zeek JSON logs
  ├─ ELK ingest
  │    ↓
  │  Kibana で分析
  └─ feature export
       ↓
     Simulation runtime 互換 CSV / 将来の feature store
       ↓
     make run
```

### 7.2 Live 系

`Live` 系は、将来追加するリアルタイム観測のための導線である。

```text
Cowrie traffic / GW traffic
  ↓
Zeek live capture (`zeek -i`)
  ↓
Zeek JSON logs
  ├─ ELK ingest
  │    ↓
  │  Kibana で監視
  └─ generalized feature export
       ↓
     feature buffer / 再学習入力
```

注意:

- `Live` 観測を追加しても、現在の `src/main/` がそのまま live runtime になるわけではない
- `make run` は引き続き `Simulation` runtime として扱う
- `Live` 側で feature を作る場合も、最終的には既存 runtime 契約と接続できる形に寄せる

## 8. コンポーネント一覧

| コンポーネント | 現在の状態 | 役割 |
|---|---|---|
| Cowrie | 単体基盤は実装済み | SSH/Telnet 型攻撃通信の観測 |
| Cowrie app ingest | 実装済み | Cowrie JSON log を Elasticsearch に投入する |
| Zeek batch wrapper | 実装済み | 既存 pcap を Zeek JSON log に変換する |
| Zeek live capture | Cowrie 宛 `conn.log` だけ実装済み | live traffic を Zeek log 化する |
| Filebeat `conn.log` ingest | 実装済み | `conn.log` を Elasticsearch に投入する |
| Logstash ingest | 未整理 / 未採用 | 複雑な metadata 付与や routing が必要になった場合の候補 |
| Elasticsearch / Kibana | 最小導線は実装済み | ログ蓄積・検索・可視化 |
| `log_to_csv_extractor.py` | 実装済み | Zeek log を Simulation runtime 互換 CSV に変換する |
| generalized feature exporter | Zeek `conn.log` 向け最小版は実装済み | live / simulation 両方から feature を出す |
| Simulation runtime (`src/main/`) | 実装済み | 推論・評価・再学習 |
| Live runtime | 未実装 | 将来のリアルタイム処理系 |

## 9. ログ形式

### 9.1 Zeek ログ

Zeek ログは JSON 形式で出力する。

理由:

- Filebeat / Elasticsearch で扱いやすい
- field 展開しやすい
- Simulation 系と Live 系で同じ log 形式を維持しやすい

Zeek の JSON 出力自体は現在の batch 経路でも利用済みである。

### 9.2 Cowrie ログ

Cowrie ログも JSON 形式を前提にする。

Cowrie 側は攻撃者行動の context を持つが、Zeek の flow log とは役割が異なる。

- Zeek: フロー要約
- Cowrie: 攻撃行動

## 10. Elasticsearch インデックス設計

### 10.1 現在の最小構成

現在の動作確認済み index は次である。

```text
adids-zeek-conn
```

これは `conn.log` 可視化の最小導線用であり、multi-source 設計をまだ反映していない。

### 10.2 将来の multi-index 設計

将来的には、入力元と用途ごとに index を分ける。

```text
zeek-pcap-simulation-*
zeek-cowrie-live-*
zeek-gw-live-*
cowrie-app-*
ids-features-*
```

ここで重要なのは、以前の `zeek-pcap-offline-*` ではなく `zeek-pcap-simulation-*` を採用する点である。

理由:

- repo 全体の用語は `Simulation` で統一されている
- この経路は単なる「オフライン解析」ではなく、最終的に `make run` へ接続される実験導線だからである

### 10.3 移行方針

ただちに `adids-zeek-conn` を捨てるのではなく、移行は段階的に行う。

1. まず現行 `adids-zeek-conn` 導線を壊さない
2. pcap 系 metadata 付き ingest を別 index として増やす
3. Kibana data view / saved object を整理する
4. 必要なら alias を用いて旧導線と新導線を共存させる

## 11. メタデータ設計

将来的に raw log / feature の両方へ、次の metadata を付与する。

```text
source_type
sensor_id
dataset_id
event_time
ingest_time
```

### 11.1 `source_type`

例:

```text
simulation_pcap
cowrie_live
gw_live
```

### 11.2 `sensor_id`

例:

```text
pcap-importer-01
cowrie-01
gw-01
```

### 11.3 `dataset_id`

例:

```text
iot23-mirai34
2201AusEast
cowrie-live-2026-05-13
gw-live-2026-05-13
```

### 11.4 `event_time` と `ingest_time`

- `event_time`
  - 通信や Zeek ログ上の時刻
- `ingest_time`
  - Elasticsearch に投入した時刻

既存 pcap をあとから投入する場合、pcap 内時刻と投入時刻は一致しない。
したがって、両者は常に分ける。

### 11.5 runtime との関係

現在の `make run` はこれら metadata を必須としていない。

ただし、次の条件を守れば追加列として同居できる。

- `daytime`
- `label`
- `LABEL_FEATURES`
- `VECTOR_FEATURES`

が従来どおり存在すること。

つまり、metadata 列を足すこと自体は可能だが、既存 feature 定義を壊してはならない。

## 12. Simulation 系の pcap 解析経路

### 12.1 現在の canonical な流れ

現在の stable workflow は次である。

1. `src/util/FeatureExtract/Zeek/settings.json` を編集する
2. `make pcap-to-log`
3. `make log-to-csv`
4. `src/main/settings.json` の `DATASETS_DIR_PATH` を leaf CSV dir に合わせる
5. `make run`

この流れは、repo 全体の基準線として維持する。

### 12.2 ELK 連携の位置づけ

Simulation 系の ELK 連携は、現在すでに `conn.log` を分岐点として実現されている。

今後 metadata 付き ingest を拡張する場合も、まずは既存 layout を使う。

```text
data/logs/zeek/<dataset>/<batch>/...
data/csv/zeek/<target_log>/<batch>/...
```

この layout を壊して parallel な `pcap-importer/` を別建てするのは最後の手段とする。

### 12.3 拡張時の方針

Simulation 系の追加実装では、次を優先する。

- `pcap_to_log_extractor.py` の出力をそのまま ingest に使う
- `log_to_csv_extractor.py` の CSV 契約を維持する
- 必要な metadata 付与や index routing は sidecar script か ingest 設定で担う

## 13. Cowrie リアルタイム監視経路

### 13.1 repo で管理する範囲

Cowrie / live 観測で repo が持つべきものは次である。

- ingest 設定
- parser / correlation script
- sample config
- docs
- tests / fixture

逆に、外部環境依存として扱うものは次である。

- 実際の interface 名
- ホスト固有の IP / firewall
- systemd / docker の machine 固有設定
- secret / password / certificate の実値

### 13.2 Zeek live capture の目標経路

```text
Cowrie 宛 traffic
  ↓
Zeek live capture
  ↓
conn.log / ssh.log / notice.log / weird.log
  ↓
ELK ingest
  ↓
zeek-cowrie-live-*
  ↓
Kibana
```

これは通信レベルの監視に使う。

### 13.3 Cowrie アプリケーションログの目標経路

```text
Cowrie JSON logs
  ↓
ELK ingest
  ↓
cowrie-app-*
  ↓
Kibana
```

これは攻撃者行動の監視に使う。

### 13.4 GW live の扱い

GW live は最終目標には含むが、Cowrie 系の基盤が安定する前に同時実装しない。

順序としては次を優先する。

1. Simulation pcap + ELK の整備
2. Cowrie app log ingest
3. Cowrie 宛 traffic の Zeek live capture
4. その後に GW live

## 14. Zeek ログと Cowrie ログの対応付け

Zeek ログはフロー情報、Cowrie ログは攻撃行動情報である。

両者は最終的に次の軸で対応付ける。

```text
src_ip
dst_ip
src_port
dst_port
timestamp
```

完全一致ではなく、時間窓を使う。

例:

```text
same src_ip
same dst_port
event_time difference <= 5〜30 秒
```

ただし、これは current repo の必須経路ではない。
まず raw ingest を安定させ、その後に追加する correlation 機能として扱う。

## 15. 2段階スキーマ設計

この基盤では、最終的に 2 段階の schema を持つ。

### 15.1 raw / analysis schema

ELK 可視化や correlation に向く schema。

候補:

```text
event_time
ingest_time
uid
src_ip
src_port
dst_ip
dst_port
proto
service
duration
orig_bytes
resp_bytes
orig_pkts
resp_pkts
conn_state
history
missed_bytes
source_type
sensor_id
dataset_id
label
```

### 15.2 Simulation runtime 互換 schema

現在の `make run` に安全につなぐための schema。

最低限必要なのは、現在の docs と同じく次である。

- `daytime`
- `label`
- `LABEL_FEATURES` に含まれる列
- `VECTOR_FEATURES` に含まれる列

既定値なら少なくとも次を含む。

```text
daytime
label
conn_state
duration
orig_bytes
resp_bytes
orig_pkts
resp_pkts
orig_ip_bytes
resp_ip_bytes
missed_bytes
local_orig
local_resp
```

### 15.3 既存実装との関係

現在の `log_to_csv_extractor.py` は、すでに Simulation runtime 互換 schema を作っている。

したがって、将来の generalized feature export は「いきなり別 schema を導入する」のではなく、少なくとも次のどちらかを満たす必要がある。

1. 既存 runtime 互換 CSV をそのまま出せる
2. 既存 runtime 互換 CSV へ落とし込む adapter を別途持つ

### 15.4 学習入力に使う候補

現在の runtime と整合しやすい候補は次である。

```text
duration
orig_bytes
resp_bytes
orig_pkts
resp_pkts
orig_ip_bytes
resp_ip_bytes
missed_bytes
local_orig
local_resp
```

`conn_state` は現在 `LABEL_FEATURES` 側で model split key として使われる。

### 15.5 将来候補だが注意が必要な列

次は raw schema には持っていてよいが、現状の runtime にそのまま入れない。

```text
service
history
source_type
sensor_id
dataset_id
src_ip
dst_ip
uid
event_time
ingest_time
```

理由:

- `service` と `history` は現 runtime では数値 vector として扱えない
- `source_type` / `sensor_id` / `dataset_id` はリーク源になりやすい
- `src_ip` / `dst_ip` は環境依存で過適合しやすい
- `event_time` / `ingest_time` は学習特徴量ではなく metadata である

## 16. ラベル設計

### 16.1 現在の label 付与

現在の Simulation 経路では、`log_to_csv_extractor.py` が `NetworkAddress` を使って数値 `label` を付与する。

- `0`: benign
- `1`: malicious

### 16.2 将来の最小ラベル

live 経路を入れたときの最小ラベル方針は次とする。

```text
GW 由来 -> benign
Cowrie 由来 -> malicious
```

### 16.3 将来の拡張ラベル

必要なら補助ラベルとして次を追加する。

```text
attack_category:
  scan
  brute_force
  login_success
  command_execution
  malware_download
  unknown
```

ただし、まずは binary label を安定させる。

## 17. IDS 用バッファと再学習

現在の `src/main/` には再学習モード自体は存在する。

- `nt`
- `st`
- `dy`

ただし、これは既存 CSV stream を読む `Simulation` runtime での話であり、live buffer 基盤とは別物である。

将来 live 系を追加する場合は、次の順で進める。

1. feature export を安定させる
2. benign / malicious staging buffer を分ける
3. 既存 runtime に接続できる input 形式を定める
4. その後に再学習 trigger を検討する

概念としては次を想定する。

```text
benign_buffer:
  source = gw_live
  label = 0

malicious_buffer:
  source = cowrie_live
  label = 1
```

ただし、ここは current repo の既存 retraining 実装よりも upstream のデータ供給層として作るべきであり、最初から `src/main/` の深部を書き換えて入れるべきではない。

## 17.5 Phase 6 の入力範囲に関する明示

`Phase 6: generalized feature export` が最初に対象とするのは、Zeek `conn.log` 系だけである。

具体的には次を扱う。

- `Simulation` 側の `pcap -> conn.log`
- `Cowrie live` 側の `zeek-cowrie-live -> conn.log`

逆に、次は Phase 6 の最初の feature source に含めない。

- `cowrie.json`
- Cowrie app log にしか存在しない `eventid`, `message`, `session`, `version`

理由は、既存 runtime が現在期待しているのが Zeek flow 特徴量であり、Cowrie app log はそのスキーマと役割が異なるためである。

## 17.6 runtime 向け CSV スキーマ維持方針

Phase 6 では、runtime に渡す CSV の既存スキーマを原則として変更しない。

つまり、`make run` に渡す最終 CSV では、現在の Simulation 互換列を維持する。

- `daytime`
- `label`
- `conn_state`
- `duration`
- `orig_bytes`
- `resp_bytes`
- `orig_pkts`
- `resp_pkts`
- `orig_ip_bytes`
- `resp_ip_bytes`
- `missed_bytes`
- `local_orig`
- `local_resp`

`source_type` や `sensor_id` のような provenance 情報は、必要になってもまずは runtime 入力 CSV の列として足さず、次で管理する方針を優先する。

- ディレクトリ名
- ファイル名
- sidecar manifest
- ELK 側 index / document metadata

技術的には runtime は余分な列を無視できるが、この段階では「入れられる」ことと「入れるべき」ことを分けて考える。
Phase 6 の第一段階では、runtime 入力 CSV へ追加 metadata 列を持ち込まない方針を取る。

## 18. Kibana ダッシュボード要件

### 18.1 現在すでにある最小ダッシュボード

現状の repo では、`adids-zeek-conn` あるいは scenario 切り出し index を使った最小ダッシュボード運用が可能である。

これは引き続き current path の確認用として残す。

### 18.2 現在実装済みの realtime dashboard

現在 repo に保存済みの reusable dashboard は次である。

- saved objects: `docs/kibana_saved_objects/cowrie_live_attack_monitoring.ndjson`
- dashboard: `Cowrie Live Attack Monitoring`

対象:

```text
zeek-cowrie-live-*
```

目的:

- 今 Cowrie に届いている SSH traffic をリアルタイムに監視する

補足:

- 現行 scope では `cowrie-app-*` は dashboard に含めない
- `source_type : "cowrie_live" and id.resp_p : 2222 and proto : "tcp"` を前提にした panel 構成である
- static analysis 用 dashboard は今後別途詳細検討する

### 18.3 将来のダッシュボード群

最終的には次の 4 系統を目標にする。

#### Dashboard 1: Cowrie Attack Monitoring

対象:

```text
zeek-cowrie-live-*
cowrie-app-*
```

目的:

- 今 Cowrie にどのような攻撃が来ているかを監視する

#### Dashboard 2: Simulation PCAP Analysis Viewer

対象:

```text
zeek-pcap-simulation-*
```

目的:

- 既存 pcap を Zeek で解析した結果を Kibana 上で確認する

#### Dashboard 3: Live vs Simulation Comparison

対象:

```text
zeek-cowrie-live-*
zeek-pcap-simulation-*
```

目的:

- live 攻撃通信と Simulation 用 pcap の特徴差を比較する

#### Dashboard 4: IDS Feature Quality

対象:

```text
ids-features-*
```

目的:

- 学習に投入される feature の品質、偏り、ドリフト、再学習イベントを監視する

## 19. 実装フェーズ

この repo の現状に合わせるなら、実装順は次が妥当である。

### Phase 0: docs 整合

目的:

- repo 事実と拡張計画を同じ文書に正しく乗せる

成果物:

- 本ドキュメント

### Phase 1: 現在の ELK 最小導線を canonical 化する

目的:

- `conn.log` 可視化の現行導線を基準線として固定する

成果物:

- `docker-compose.yml`
- `filebeat/conn_log.yml`
- current path に一致した docs

補足:

- root `filebeat.yml` / `logstash.conf` を current path と混同しない整理が必要

### Phase 2: Simulation pcap ingest を metadata 付きで拡張する

目的:

- 既存 pcap を ELK 上で dataset 単位に整理しやすくする

成果物:

- `zeek-pcap-simulation-*` ingest 設定
- `source_type=simulation_pcap` などの metadata 付与
- Kibana data view

注意:

- 既存 `adids-zeek-conn` を壊さない
- 既存 `pcap -> csv -> make run` 導線を壊さない

### Phase 3: Cowrie 単体基盤を用意する

目的:

- Cowrie ログ取得基盤を整える

成果物:

- `docker-compose.cowrie.yml`
- `make cowrie-up` / `make cowrie-down` / `make cowrie-ps`
- `docs/Cowrieを起動する手順.md`
- `cowrie.json` に最小接続 event が出ることの確認

### Phase 4: Cowrie アプリケーションログを ELK に投入する

目的:

- 攻撃者行動を Kibana で見られるようにする

成果物:

- `filebeat/cowrie_json.yml`
- `docker-compose.yml` の `filebeat-cowrie01`
- `make elk-up-cowrie`
- `cowrie-app-*` index pattern
- `cowrie-app` data view 手順

### Phase 5: Cowrie 宛 traffic の Zeek live capture を追加する

目的:

- Cowrie 宛通信を flow レベルで見られるようにする

成果物:

- `docker-compose.cowrie.yml` の `zeek-cowrie-live`
- `filebeat/cowrie_live_conn_log.yml`
- `make cowrie-live-up`
- `make elk-up-cowrie-live`
- `zeek-cowrie-live-*` index pattern
- `zeek-cowrie-live` data view 手順

### Phase 6: generalized feature export の最小版を作る

目的:

- Zeek `conn.log` を対象に、Simulation 系と Live 系の両方から runtime 互換 feature を出せるようにする

成果物:

- `src/util/FeatureExtract/Zeek/feature_exporter.py`
- `make feature-export`
- `batch` / `live` の 2 mode
- runtime 互換 leaf CSV の出力
- provenance 情報の別管理方針

### Phase 7: Kibana ダッシュボードを整備する

目的:

- まず `zeek-cowrie-live-*` ベースの realtime attack monitoring 画面を固定する

成果物:

- `docs/kibana_saved_objects/cowrie_live_attack_monitoring.ndjson`
- `Cowrie Live Attack Monitoring`
- import 手順を含む docs

補足:

- `cowrie-app-*` を混ぜた dashboard は将来拡張として残す
- static analysis dashboard は current scope 外とする

### Phase 7.5: dashboard の運用固定化

目的:

- repo に保存した Saved Objects を、手動 UI 操作に依存せず再投入できるようにする

成果物:

- `make kibana-import-cowrie-live-dashboard`
- import 導線を反映した docs

### Phase 7.6: GeoIP / ASN enrich と map panel

目的:

- T-Pot 風の realtime monitoring として、送信元の国・ASN・地理分布を見られるようにする

成果物:

- `filebeat/cowrie_live_enrich_pipeline.json`
- `make es-put-cowrie-live-enrich-pipeline`
- `source.ip`, `source.geo.*`, `source.as.*`
- `Cowrie Live Top Countries`
- `Cowrie Live Top ASNs`
- `Cowrie Live Attack Map`

注意:

- localhost 検証では `source.ip` が private address になるため GeoIP/ASN/map は空でも正常

### Phase 8: 再学習向けバッファ接続を検討する

目的:

- live 系 feature を将来の再学習入力へ接続できるようにする

成果物:

- staging buffer 設計
- retraining との接続方針

### Phase 9: GW live を追加する

目的:

- 良性 live traffic を同じ基盤で扱えるようにする

成果物:

- `zeek-gw-live-*`
- benign 側 feature 供給

## 20. repo 管理範囲と配置方針

### 20.1 repo が管理するもの

- Zeek / ELK / Cowrie 連携設定
- feature export / correlation のコード
- docs
- test / fixture
- Kibana saved object の export ファイル

### 20.2 repo 外で管理するもの

- host 固有の interface 名
- machine 固有の service 管理
- secret / password / certificate の実値
- 実運用上の firewall や network 配置

### 20.3 配置方針

この repo では、すでに次の canonical な置き場がある。

- ELK 起動基盤: `docker-compose.yml`
- Filebeat 設定: `filebeat/`
- Zeek 前処理: `src/util/FeatureExtract/Zeek/`
- 既存 ELK docs: `docs/ELK*.md`

したがって、将来の実装でもまずはこの構造を尊重する。

特に、以前の案にあったような大規模な parallel top-level directory 追加は、最初から前提にしない。

現時点での妥当な追加先は次のようなイメージである。

```text
filebeat/
  conn_log.yml
  cowrie_app.yml           # future

logstash/
  pipelines/               # Logstash を本当に使う段階になったら追加

kibana/
  saved_objects/           # future

src/util/FeatureExtract/Zeek/
  pcap_to_log_extractor.py
  log_to_csv_extractor.py
  feature_exporter.py      # future

src/util/FeatureExtract/Cowrie/
  ...                      # Cowrie 側の補助が必要になったら future
```

## 21. 注意点と最終ゴール

### 21.1 注意点

- Cowrie 由来の攻撃通信は、実 IoT 機器への攻撃そのものではなく近似データとして扱う
- `source_type` を学習特徴量に入れない
- `sensor_id` / `dataset_id` を学習特徴量に入れない
- `src_ip` / `dst_ip` を学習特徴量に入れない
- `service` / `history` を使うなら、先に encoding 戦略と runtime 互換性を整理する
- pcap の `event_time` と `ingest_time` を分ける
- 既存 `Simulation` leaf CSV 契約を壊さない
- 現在の `adids-zeek-conn` 最小導線が壊れないよう、multi-index 化は段階移行する

### 21.2 最終ゴール

本タスクの最終ゴールは次である。

```text
既存 pcap と将来の Cowrie / GW live traffic を Zeek で共通ログ形式へ寄せ、
ELK で監視・分析できるようにする。

同時に、Zeek 由来データを Simulation runtime と整合する特徴量形式へ変換し、
将来的に良性・悪性データを同一特徴量空間上で扱えるようにする。
```

この構成により、次が可能になる。

- 既存 pcap の Zeek 解析結果の可視化
- 現在の `Simulation` 実験導線の維持
- Cowrie への攻撃通信のリアルタイム監視
- live traffic と Simulation 用 pcap の比較
- Cowrie ログと Zeek ログの対応付け
- 再学習用 feature 供給の拡張

## 参考資料

- Cowrie documentation: https://docs.cowrie.org/en/latest/README.html
- Zeek JSON logs: https://docs.zeek.org/en/lts/scripts/policy/tuning/json-logs.zeek.html
- Zeek log formats: https://docs.zeek.org/en/current/log-formats.html
- Elastic Zeek integration: https://www.elastic.co/docs/reference/integrations/zeek
- Filebeat overview: https://www.elastic.co/beats/filebeat
