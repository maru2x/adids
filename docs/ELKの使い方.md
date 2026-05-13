# ELKの使い方

## 目的

このドキュメントは、Kibana を使って ELK 上の Zeek `conn.log` データをどう読むかをまとめるものである。
対象は、IoT-23 Mirai 34 を `iot23-mirai34-clean` data view で見るケースである。

## 最初に覚える画面

最初に覚えるべき画面は 2 つだけで十分である。

- `Discover`: 生データを 1 行ずつ確認する
- `Dashboard`: 集計済みのグラフをまとめて見る

## `Discover` の使い方

### 最初にやること

1. 左メニューから `Discover` を開く
2. data view に `iot23-mirai34-clean` を選ぶ
3. 時間範囲を `2018-12-21` から `2018-12-22` に合わせる
4. `@timestamp`, `id.orig_h`, `id.resp_h`, `id.resp_p`, `proto`, `service`, `conn_state` を列に出す

画面例:

![Kibana Discover 画面](./images/kibana-discover-iot23-mirai34.png)

### 各 field の見方

- `id.orig_h`: 送信元 IP
- `id.resp_h`: 宛先 IP
- `id.resp_p`: 宛先ポート
- `proto`: プロトコル
- `service`: Zeek が推定したサービス種別
- `conn_state`: 接続状態

### よく使う検索

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

## `Dashboard` の使い方

### 最初にやること

1. 左メニューから `Dashboard` を開く
2. `IoT23 Mirai 34 Dashboard` を開く
3. 時間範囲が `2018-12-21` から `2018-12-22` になっていることを確認する

画面例:

![Kibana Dashboard 画面](./images/kibana-dashboard-iot23-mirai34.png)

### 各パネルの意味

- `IoT23 Mirai 34 Events Over Time`
  - いつ通信件数が増えたかを見る
- `IoT23 Mirai 34 Top Source IPs`
  - どの送信元 IP が多いかを見る
- `IoT23 Mirai 34 Top Destination Ports`
  - どのポートが多く狙われたかを見る

### 最初に見る観点

1. `Events Over Time` で攻撃が増えた時間帯を見る
2. `Top Destination Ports` で狙われているポートを見る
3. `Top Source IPs` で目立つ送信元 IP を見る
4. 気になる IP や port を `Discover` に戻って詳細確認する

## ハマりやすい点

- 時間範囲が現在時刻のままだと、IoT-23 の 2018 年データは空に見える
- `adids-zeek-conn` を使うと旧データが混ざることがある
- 実データ確認では `iot23-mirai34-clean` を使う方が分かりやすい

## この session で作った object 名

- data view: `iot23-mirai34-clean`
- saved search: `IoT23 Mirai 34 Clean Events`
- visualization: `IoT23 Mirai 34 Events Over Time`
- visualization: `IoT23 Mirai 34 Top Source IPs`
- visualization: `IoT23 Mirai 34 Top Destination Ports`
- dashboard: `IoT23 Mirai 34 Dashboard`

## 関連ドキュメント

- 構成とフロー: [ELK構成とデータフロー.md](./ELK構成とデータフロー.md)
- 可視化手順: [ELKでデータを可視化する手順.md](./ELKでデータを可視化する手順.md)
