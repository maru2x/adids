# ELK 最小セットアップ手順

## 目的

この手順は、Zeek `conn.log` を Elasticsearch / Kibana で可視化する最小導線をローカルで確認するためのものである。

対象は次の流れである。

```text
pcap -> Zeek conn.log -> Filebeat -> Elasticsearch -> Kibana
```

## 前提

次が使えることを前提にする。

- Docker / Docker Compose
- `make pcap-to-log`
- `src/util/FeatureExtract/Zeek/settings_iot23_elk.json` を編集できること

Zeek 前処理をローカルで動かす方法は [セットアップ詳細.md](./セットアップ詳細.md) を参照。

ELK の全体方針は [ELK再構築方針.md](./ELK再構築方針.md) を参照。

## 1. 専用設定を確認する

[settings_iot23_elk.json](/home/lemon/adids/src/util/FeatureExtract/Zeek/settings_iot23_elk.json) の `PcapToLog.OUTPUT_ROOT_DIR_PATH` を確認する。

この手順では、compose 側が次を読む前提になっている。

```text
data/logs/zeek/
```

もし別 path を使う場合は、`docker-compose.yml` の filebeat mount も揃えて変更する必要がある。

## 2. `pcap` から `conn.log` を作る

`PcapToLog.INPUT_DIR_PATH` を対象 dataset に合わせて設定し、次を実行する。

```bash
make pcap-to-log PCAP_TO_LOG_ARGS="--settings src/util/FeatureExtract/Zeek/settings_iot23_elk.json"
```

成功すると次のようなレイアウトで Zeek ログが出力される。

```text
data/logs/zeek/<dataset>/<batch>/conn.log
```

## 3. ELK を起動する

`.env` に必要な環境変数が入っていることを確認して、次を実行する。

```bash
docker compose up -d setup es01 kibana filebeat01
```

最初の起動では証明書作成と Kibana の初期化に少し時間がかかる。

## 4. Kibana を開く

Kibana は通常次で開ける。

```text
http://localhost:${KIBANA_PORT}
```

`.env` の `KIBANA_PORT` を見て実際の port を確認する。

## 5. Data View を作る

Kibana で `adids-zeek-conn` を対象に Data View を作成する。

timestamp field は `@timestamp` を選ぶ。

## 5.5 Kibana の最初の使い方

Kibana を開いたあと、最初に覚えるべき画面は `Discover` と `Dashboard` の 2 つだけで十分である。

- `Discover`: 生データを 1 行ずつ確認する画面
- `Dashboard`: 集計済みのグラフをまとめて見る画面

### 5.5.1 まず `Discover` を開く

1. 左メニューから `Discover` を開く
2. data view に `iot23-mirai34-clean` を選ぶ
3. 時間範囲を `2018-12-21` から `2018-12-22` に合わせる
4. `@timestamp`, `id.orig_h`, `id.resp_h`, `id.resp_p`, `proto`, `service`, `conn_state` を列に出す

この画面では、「どの通信が実際に入っているか」を確認する。

- `id.orig_h`: 送信元 IP
- `id.resp_h`: 宛先 IP
- `id.resp_p`: 宛先ポート
- `proto`: プロトコル
- `service`: Zeek が推定したサービス種別
- `conn_state`: 接続状態

画面例:

![Kibana Discover 画面](./images/kibana-discover-iot23-mirai34.png)

### 5.5.2 `Discover` でよく使う検索

KQL に次のような条件を入れると、特定の通信だけを絞り込める。

送信元 IP を見る:

```text
id.orig_h : "192.168.1.195"
```

宛先ポートを絞る:

```text
id.resp_p : 6667
```

サービス名で見る:

```text
service : "irc"
```

接続状態で見る:

```text
conn_state : "S0"
```

### 5.5.3 次に `Dashboard` を開く

1. 左メニューから `Dashboard` を開く
2. `IoT23 Mirai 34 Dashboard` を開く
3. 時間範囲が `2018-12-21` から `2018-12-22` になっていることを確認する

この dashboard には次の 3 つがある。

- `IoT23 Mirai 34 Events Over Time`: いつ通信件数が増えたかを見る
- `IoT23 Mirai 34 Top Source IPs`: どの送信元 IP が多いかを見る
- `IoT23 Mirai 34 Top Destination Ports`: どのポートが多く狙われたかを見る

画面例:

![Kibana Dashboard 画面](./images/kibana-dashboard-iot23-mirai34.png)

### 5.5.4 最初に見る観点

最初の読み方としては、次の順で十分である。

1. `Events Over Time` で攻撃が増えた時間帯を見る
2. `Top Destination Ports` で狙われているポートを見る
3. `Top Source IPs` で目立つ送信元 IP を見る
4. 気になる IP や port を `Discover` に戻って詳細確認する

### 5.5.5 ハマりやすい点

- 時間範囲が現在時刻のままだと、IoT-23 の 2018 年データは空に見える
- data view を `adids-zeek-conn` にすると旧データが混ざることがある
- 今回の実データ確認では `iot23-mirai34-clean` を使う方が分かりやすい

## 6. 最初に確認する項目

最初の確認では次が見えれば十分である。

- 時系列の document 数
- `id.orig_h` 上位
- `id.resp_p` 上位
- `proto` 分布
- `service` 分布
- `conn_state` 分布
- `orig_bytes`, `resp_bytes` の分布

## 7. 最初の dashboard 3 枚

最初の可視化は、次の 3 枚で十分である。

- 時系列の接続数
- 送信元 IP 上位
- 宛先ポート上位

作成時の前提 KQL は次を推奨する。

```text
event.dataset : "zeek.conn" and not error.type : json
```

### 7-1. 時系列の接続数

- `Visualize Library` または `Lens` で新規作成する
- data view は `adids-zeek-conn` を選ぶ
- metric は `Count of records`
- X 軸は `@timestamp`
- 名前は `Zeek Conn Events Over Time` とする

### 7-2. 送信元 IP 上位

- `Lens` で新規作成する
- data view は `adids-zeek-conn` を選ぶ
- metric は `Count of records`
- bucket は `Top values of id.orig_h`
- 名前は `Top Source IPs` とする

### 7-3. 宛先ポート上位

- `Lens` で新規作成する
- data view は `adids-zeek-conn` を選ぶ
- metric は `Count of records`
- bucket は `Top values of id.resp_p`
- 名前は `Top Destination Ports` とする

この 3 つを 1 つの dashboard に並べれば、最初の観測用途としては十分である。

必要に応じて、次を追加する。

- `service` 上位
- `conn_state` 上位
- `orig_bytes` / `resp_bytes` の分布

## 7.5 Discover / Saved Search

dashboard を作る前に、`Discover` 側で最小の saved search を 1 つ作っておくと確認がしやすい。

推奨する条件:

```text
event.dataset : "zeek.conn" and not error.type : json
```

最初に見る列の例:

- `@timestamp`
- `id.orig_h`
- `id.resp_h`
- `id.resp_p`
- `proto`
- `service`
- `conn_state`

saved search 名の例:

- `Zeek Conn Clean Events`

これを作っておくと、dashboard 側で同じ条件を流用しやすい。

## 7.6 Saved Objects の保存

Kibana 上で作った data view / saved search / visualization / dashboard は、repo のファイルとしては自動保存されない。
再利用したい場合は、saved objects として export して管理する。

この session で作成した主な object 名:

- data view: `iot23-mirai34-clean`
- saved search: `IoT23 Mirai 34 Clean Events`
- visualization: `IoT23 Mirai 34 Events Over Time`
- visualization: `IoT23 Mirai 34 Top Source IPs`
- visualization: `IoT23 Mirai 34 Top Destination Ports`
- dashboard: `IoT23 Mirai 34 Dashboard`

### UI から export する

1. `Stack Management -> Saved Objects`
2. 上記 object を選択する
3. `Export`
4. `Include related objects` を有効にする
5. `.ndjson` を保存する

### UI から import する

1. `Stack Management -> Saved Objects`
2. `Import`
3. 事前に export した `.ndjson` を指定する
4. 必要なら `Automatically overwrite conflicts` を有効にする

### 注意

- dashboard や saved search は参照先 data view に依存する
- この session では `iot23-mirai34-clean` data view を前提にしている
- import 先に同名 index がない場合は、先に `iot23-mirai34-clean` を作る必要がある
- `adids-zeek-conn` ではなく clean index 側を使うと、旧データ混在を避けやすい

## 8. synthetic から実データ `pcap` へ差し替える

synthetic で導線確認ができたら、次は honeypot 系の実データ `pcap` へ差し替える。

流れは変えず、入力 dataset だけ置き換える。

1. honeypot 系 `pcap` dataset を用意する
2. [settings_iot23_elk.json](/home/lemon/adids/src/util/FeatureExtract/Zeek/settings_iot23_elk.json) の `PcapToLog.INPUT_DIR_PATH` をその dataset に向ける
3. `PcapToLog.OUTPUT_ROOT_DIR_PATH` は `data/logs/zeek/` のままにする
4. `make pcap-to-log PCAP_TO_LOG_ARGS="--settings src/util/FeatureExtract/Zeek/settings_iot23_elk.json"` を実行する
5. `data/logs/zeek/<dataset>/<batch>/conn.log` が出力される
6. Filebeat がその `conn.log` を読み、Kibana では同じ `adids-zeek-conn` data view を使う

最低限の確認として、実データ投入時は次を見る。

```bash
tail -n 5 data/logs/zeek/<dataset>/<batch>/conn.log
```

確認したいこと:

- 空行が混ざっていないこと
- 各行が 1 個の JSON object であること
- `ts` が入っていること

空行や壊れた行があると、Kibana 側で `error.type=json` の event が混ざる。
最初の観測では、必要に応じて次の KQL で除外する。

```text
event.dataset : "zeek.conn" and not error.type : json
```

## 9. 実データ候補の選び方

最初の実データ候補は、次の条件を満たすものを優先する。

- `pcap` が配布されている
- Zeek `conn.log` と対応づけやすい
- honeypot / IoT 攻撃観測として説明しやすい
- 小さめの scenario 単位で試せる

現時点では、**IoT-23** を第一候補にするのが扱いやすい。

理由:

- Stratosphere IPS の公開 dataset で、IoT マルウェアと benign traffic が両方ある
- `pcap` を含む full dataset が配布されている
- 各 scenario ごとに分かれており、段階的に試しやすい
- Zeek `conn.log.labeled` も併せて提供されており、`pcap -> Zeek` の結果比較もしやすい

公式ページ:

- https://www.stratosphereips.org/datasets-iot23

公式ページには、full download と scenario ごとの配布、および `conn.log.labeled` が案内されている。

### まず試すとよい進め方

1. IoT-23 の 1 scenario を選ぶ
2. その scenario の `pcap` を `PcapToLog.INPUT_DIR_PATH` に向ける
3. `make pcap-to-log` を実行する
4. `conn.log` が ELK に入ることを確認する
5. 既存の 3 可視化で傾向を見る

### 候補を増やすときの観点

- `telnet`, `ssh`, `irc`, `dns`, `http` など、見たい protocol が含まれるか
- 攻撃ラベルの有無
- 1 scenario のサイズが大きすぎないか
- 実験ごとに dataset を切り替えやすい directory layout か

## 想定トラブル

### `conn.log` が見つからない

- `make pcap-to-log` が成功しているか確認する
- `data/logs/zeek/<dataset>/<batch>/conn.log` が存在するか確認する
- `docker-compose.yml` の mount path が出力先と一致しているか確認する

### Kibana に document が出ない

- `filebeat01` が起動しているか確認する
- `es01` が healthy か確認する
- `conn.log` が 1 行 1 JSON 形式であることを確認する

### 特定 scenario だけを clean に見たい

- まず `adids-zeek-conn` で ingest を確認する
- 既存データが混ざる場合は、IoT-23 scenario 単位で別 index へ `_reindex` する
- この session では `iot23-mirai34-clean` を clean index として使った
- dashboard もその clean index 用 data view に切り替えて作る

### `@timestamp` が空になる

- `ts` が入っているか確認する
- `filebeat/conn_log.yml` の `timestamp` processor が有効か確認する

### `error.type=json` の event しか出ない

- `conn.log` に空行が混ざっていないか確認する
- `conn.log` が 1 行 1 JSON object になっているか確認する
- 新しい batch ディレクトリを切って Filebeat に新規ファイルとして読ませる

## 今回やっていないこと

この最小手順では次はまだ扱わない。

- GeoIP enrich
- `dns.log`, `http.log`, `ssl.log` の ingest
- `adids` runtime 結果の ELK 連携
- Logstash を用いた変換
