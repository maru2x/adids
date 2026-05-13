# ELK Stack 再構築方針

## 目的

このドキュメントは、`adids` リポジトリにおける ELK Stack 再構築の目的、対象範囲、既存プログラムとの関係を整理するためのものである。

今回の第一目標は、**IoT デバイスに対する攻撃観測を可視化するための最小構成を定義すること**である。
最終的には自前ハニーポットで観測した通信を可視化したいが、最初の段階では既存または synthetic の `pcap` から Zeek の `conn.log` を生成し、それを Elasticsearch / Kibana で確認できる状態を目指す。

## 背景

このリポジトリにはすでに次の要素が存在する。

- `src/util/FeatureExtract/Zeek/`
  - `pcap -> Zeek log -> csv` の前処理導線
- `src/util/ElasticSearch/es_utils.py`
  - Elasticsearch 接続と簡単な集計補助
- `docker-compose.yml`
  - Elastic Stack 一式の起動定義
- `logstash.conf`
  - Logstash pipeline の雛形

ただし、これらは現時点で `adids` の日常導線として一貫した構成にはなっていない。
特に `logstash.conf` は現在の Zeek `conn.log` 投入を前提にした内容ではなく、`docker-compose.yml` とも接続先や想定データが揃っていない。

そのため、今回の再構築ではまず

- 何を可視化したいのか
- 既存のどの導線を再利用するのか
- `adids` 本体と ELK 側をどこで分離するのか

を明文化する必要がある。

## 今回のスコープ

今回のスコープは次の通りとする。

- `pcap` を入力として扱う
- Zeek の `conn.log` を可視化用の一次データとする
- Elasticsearch に `conn.log` 相当データを投入する
- Kibana で通信量や送信元傾向を観測できるようにする
- synthetic または既存 dataset を使った再現可能なローカル検証手順を用意する

## 今回の対象外

以下は今回の対象外とする。

- `adids` runtime の推論結果を ELK に載せること
- 本番運用を前提にした常時収集・長期保存設計
- 外部公開ハニーポットの構築と保守
- 世界中の攻撃 telemetry を外部 feed から統合すること
- `pcap` を直接 Elasticsearch に保存すること

これらは将来拡張候補ではあるが、最初の実装段階では切り離す。

## 基本方針

### なぜ `pcap` 起点にするか

`adids` にはすでに Zeek ベースの前処理があるため、可視化専用基盤も同じ入口に寄せる方が自然である。

`pcap` 起点にすることで次の利点がある。

- dataset が変わっても同じ Zeek 前処理を再利用できる
- 将来自前ハニーポットで採取した通信も同じ導線に載せやすい
- 可視化対象を `conn.log` に絞ることで、CSV 変換や runtime と独立に進められる

### なぜ `conn.log` ベースにするか

最初の可視化では、セッション単位の接続情報が見えれば十分である。
`conn.log` には少なくとも次のような可視化に必要な情報が含まれる。

- 発生時刻 `ts`
- 送信元 / 宛先 IP
- 送信元 / 宛先ポート
- `proto`
- `service`
- `duration`
- `orig_bytes`, `resp_bytes`
- `conn_state`

このため、最初から `csv` や runtime へ寄せるより、`conn.log` を ELK へ投入する方が簡潔である。

## 想定アーキテクチャ

```text
pcap
  -> src/util/FeatureExtract/Zeek/pcap_to_log_extractor.py
  -> data/logs/zeek/<dataset>/<batch>/conn.log
  -> ELK 用 ingest 設定
  -> Elasticsearch index
  -> Kibana dashboard
```

必要に応じて、既存の CSV / runtime 導線は並行して維持する。

```text
pcap
  -> pcap_to_log_extractor.py
  -> conn.log
  -> log_to_csv_extractor.py
  -> leaf CSV dir
  -> make run
```

この 2 本の導線は、**`conn.log` を分岐点として並列に存在する**想定である。

## 既存プログラムとの関係

### 1. `src/util/FeatureExtract/Zeek/pcap_to_log_extractor.py`

このスクリプトは `pcap` から Zeek ログ群を生成する入口である。

- 入力:
  - `src/util/FeatureExtract/Zeek/settings.json` の `PcapToLog.INPUT_DIR_PATH`
- 出力:
  - `PcapToLog.OUTPUT_ROOT_DIR_PATH/<input_dir_name>/<timestamp>/...`
- 役割:
  - ELK 可視化系と runtime 系の共通上流

ELK 再構築では、この出力ディレクトリ以下の `conn.log` を ingest 対象として扱う。

### 2. `src/util/FeatureExtract/Zeek/log_to_csv_extractor.py`

このスクリプトは Zeek ログを runtime 用 CSV に変換する。

- 入力:
  - `LogToCsv.INPUT_DIR_PATH`
- 出力:
  - `LogToCsv.OUTPUT_ROOT_DIR_PATH/<target_log_name>/<batch_name>/...csv`
- 役割:
  - `make run` 用データセットの作成

ELK の最初の段階では、このスクリプトは必須ではない。
ただし、同一 `pcap` から「可視化」と「runtime 実験」を並行して行いたい場合には重要である。

### 3. `src/util/ElasticSearch/es_utils.py`

このファイルは Elasticsearch 接続補助であり、現状では runtime 本体の主要導線には入っていない。

現時点では次の位置づけとする。

- ingest 処理そのものを担うファイルではない
- Elasticsearch 上に載った `zeek.conn` 系データを分析補助する小物 utility
- 将来、ダッシュボード検証や notebook 連携で再利用する余地がある

### 4. `docker-compose.yml`

このファイルは Elastic Stack のローカル起動定義置き場として扱う。

ただし現状の内容はそのままでは今回の構成に合っていないため、再構築時は次を満たすように整理する必要がある。

- `conn.log` を入力にできること
- Elasticsearch の接続先定義が pipeline 側と一致すること
- ローカル検証に必要な最小サービスだけでも起動できること

### 5. `logstash.conf`

このファイルは、Zeek `conn.log` 用の ingest 定義へ置き換える、または役割を明確化した別ファイルへ分離する候補である。

再構築時の候補は 2 つある。

- `logstash.conf` を Zeek `conn.log` 専用に更新する
- `logstash/conn_log.conf` のように用途別に分割する

後者の方が、既存のサンプル投入系と混ざりにくい。

## 配置方針

最初の実装では、既存構成を大きく崩さず、ELK まわりを次のように置くのが自然である。

```text
adids/
├─ docker-compose.yml
├─ logstash/
│  └─ conn_log.conf
├─ filebeat/
│  └─ conn_log.yml
├─ docs/
│  └─ ELK再構築方針.md
├─ data/
│  └─ logs/zeek/...            # Zeek 出力
└─ src/util/FeatureExtract/Zeek/
   ├─ pcap_to_log_extractor.py
   └─ log_to_csv_extractor.py
```

ポイントは次の通り。

- `src/` 配下には、なるべく ELK 起動専用コードを増やしすぎない
- ingest 設定は `src/` の外に置き、運用設定として扱う
- `FeatureExtract/Zeek` はあくまで前処理担当のまま維持する
- runtime 用 CSV 導線と ELK 用 `conn.log` 導線を分離する

## データフローと接続点

### 現段階の接続

```text
pcap
  -> pcap_to_log_extractor.py
  -> conn.log
  -> Logstash or Filebeat
  -> Elasticsearch
  -> Kibana
```

ここでの接続点は `conn.log` である。

### 将来の接続候補

将来は次のような拡張があり得る。

```text
pcap
  -> pcap_to_log_extractor.py
  -> conn.log
  -> log_to_csv_extractor.py
  -> make run
  -> exp/
  -> Elasticsearch
  -> Kibana
```

ただしこの段階では、runtime の出力と可視化の責務が混ざる。
そのため、最初の実装では **runtime 非依存** を維持する。

## 可視化で最初に見る項目

最初のダッシュボードでは、次の観点を優先する。

- 時系列の接続数
- 送信元 IP 上位
- 宛先ポート上位
- `proto` 分布
- `service` 分布
- `conn_state` 分布
- `orig_bytes`, `resp_bytes`, `duration` の傾向

必要に応じて GeoIP を追加し、送信元国の分布を見る。
ただし GeoIP は追加依存と設定が増えるため、最小構成の必須要件にはしない。

## 段階的な実装計画

### Phase 0: 方針確定

- `conn.log` ベースで進めることを決める
- runtime と ELK を分離した構成にする
- synthetic `pcap` を使った最小検証を前提にする

### Phase 1: ローカル ELK 最小構成

- `docker-compose.yml` を最小構成で見直す
- Zeek `conn.log` 用 ingest 設定を作る
- `conn.log` を Elasticsearch に投入できることを確認する

### Phase 2: ダッシュボード作成

- Kibana で基本可視化を作る
- どの項目が有用かを確認する

### Phase 3: dataset 置換

- synthetic `pcap` から既存ハニーポット dataset へ切り替える
- 観測したい項目が足りるかを確認する

### Phase 4: 自前ハニーポット連携

- 実際のハニーポット観測データを同じ導線へ接続する

## 次の実装 issue 候補

- Zeek `conn.log` 用 ingest 設定を作る
- `docker-compose.yml` を最小構成へ整理する
- synthetic `pcap` から `conn.log` を作る検証 fixture を用意する
- Kibana の最小ダッシュボード観点を定義する
- 必要なら GeoIP 追加を別 issue に分ける

詳細な ingest 方針は [ELK ingest設計メモ.md](./ELK ingest設計メモ.md) を参照。
compose 側の整理は [docker_compose構成メモ.md](./docker_compose構成メモ.md) を参照。
最小起動手順は [ELK最小セットアップ手順.md](./ELK最小セットアップ手順.md) を参照。
