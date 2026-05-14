# Codex実装引継ぎドキュメント

## 1. 目的

本デモでは、以下の2点を示す。

1. AWS上でCowrieハニーポットを稼働させ、インターネットから到達する攻撃通信を収集し、手元PC上のElasticsearch/Kibanaで監視・分析する。
2. 手元PC上にIoT擬似環境とIDS実行系を構築し、AWS上のCowrieで収集した悪性通信データを用いて学習したIDSが、同一ネットワーク上の別マシンから仕掛けられる疑似攻撃を検出できることを示す。

重要な補足として、疑似攻撃はDockerコンテナ内のattackerからではなく、**同一LAN上の別物理マシン**から実行する予定である。したがって、ローカルIDSデモ環境は、外部の同一LAN端末からIoT擬似デバイスへ到達できる設計にする。

---

## 2. 全体アーキテクチャ

```text
┌──────────────────────────────────────────────────────────────┐
│ AWS Sensor Node                                               │
│ 実インターネット上の攻撃通信を観測する                         │
│                                                              │
│ Internet                                                     │
│   ↓                                                          │
│ EC2                                                          │
│   ├─ Cowrie Honeypot                                          │
│   │    └─ SSH/Telnet型攻撃を収集                               │
│   ├─ Zeek live capture                                        │
│   │    └─ Cowrie宛通信をZeek JSON log化                         │
│   └─ Filebeat / Log forwarder                                 │
│        └─ ログを手元PCへ転送                                   │
└───────────────────────┬──────────────────────────────────────┘
                        │ Tailscale / WireGuard / SSH tunnel
                        ▼
┌──────────────────────────────────────────────────────────────┐
│ Local PC                                                      │
│ 監視・分析・IDS学習・IDS実行・IoT擬似環境を担う                  │
│                                                              │
│   ├─ Logstash                                                 │
│   ├─ Elasticsearch                                            │
│   ├─ Kibana                                                   │
│   ├─ Python normalizer                                        │
│   │    └─ Zeek log -> CSV / common feature schema              │
│   ├─ IDS training pipeline                                    │
│   ├─ IDS runtime                                              │
│   └─ IoT demo environment                                     │
│        └─ fake_iot_device                                     │
│                                                              │
│ 同一LAN上の別マシン                                            │
│   └─ attacker                                                  │
│        └─ fake_iot_deviceへ疑似攻撃を実行                       │
└──────────────────────────────────────────────────────────────┘
```

---

## 3. デモで見せたい内容

### 3.1 デモ1: AWS Cowrie攻撃監視

AWS上のEC2でCowrieを動かし、実際に収集された攻撃通信を手元PC上のKibanaで表示する。

表示したい内容は以下である。

- 攻撃イベントの時系列
- 攻撃元IP
- 宛先ポート
- Zeek conn.log由来の通信特徴
- Cowrie app log由来のusername/password
- Cowrie session一覧
- 実行されたコマンド
- `wget` / `curl` などのマルウェア取得風コマンド

### 3.2 デモ2: AWS由来悪性データを前提にしたローカル疑似攻撃検知

AWS Cowrieで収集した通信をZeek特徴量に変換し、悪性データ由来の学習済みモデルを使う。

ローカルでは、手元PC上に SSH を受ける IoT 擬似デバイスを立てる。今回は、まず「攻撃時に alert が出る」ことを優先し、通常通信 generator は必須にしない。

疑似攻撃は、同一LAN上の別物理マシンから Hydra などで実行する。IDS は、手元PC上で Zeek により観測された通信を `feature-export live` で特徴量化し、学習済みモデルで推論し、攻撃らしい通信に対して console alert を出す。

---

## 4. AWS側の構成

### 4.1 役割

AWS EC2は外部公開センサーとして使う。

```text
AWS EC2
  ├─ Cowrie
  ├─ Zeek
  └─ Filebeat or log forwarder
```

### 4.2 公開ポート

最初は安全のため、Cowrieは `2222/tcp` で公開する。

```text
Inbound Security Group:
  allow TCP 2222 from 0.0.0.0/0    # Cowrie SSH
  allow TCP 22 from 自分のIPのみ      # 管理SSH
  deny  TCP 5601                    # Kibanaは公開しない
  deny  TCP 9200                    # Elasticsearchは公開しない
  deny  TCP 5044                    # Logstashは公開しない
```

攻撃収集量を増やす段階では、Cowrieを `22/tcp` で公開することも検討する。ただし、その場合、本物の管理SSHとは必ず分離する。

### 4.3 Zeekの役割

Cowrieのアプリケーションログだけではなく、Cowrie宛の通信をZeekでフロー化する。

```text
Internet
  ↓
Cowrie
  ↓
Zeek live capture
  ↓
Zeek JSON logs
```

出力対象は最低限以下。

- `conn.log`
- `ssh.log`
- `notice.log`
- `weird.log`

### 4.4 AWSから手元PCへのログ転送

推奨はTailscaleまたはWireGuardである。

```text
AWS Filebeat
  ↓ Tailscale / WireGuard
Local Logstash
  ↓
Local Elasticsearch
  ↓
Local Kibana
```

---

## 5. 手元PC側の構成

### 5.1 役割

手元PCは分析・学習・デモ実行基盤である。

```text
Local PC
  ├─ Elasticsearch
  ├─ Kibana
  ├─ Logstash
  ├─ pcap offline importer
  ├─ Python normalizer
  ├─ IDS training pipeline
  ├─ IDS runtime
  └─ fake_iot_device
```

### 5.2 Elasticsearch index案

現時点でデモで確実に使うのは既存の AWS 側 live 監視用 index 群である。

```text
zeek-cowrie-live-*      # AWS Cowrie宛通信のZeekログ
cowrie-app-*            # Cowrieアプリケーションログ
```

ローカル Live IDS PoC は、現時点では Elasticsearch へ alert を投入せず、console alert を最小出力とする。

### 5.3 Kibana Data View案

```text
zeek-cowrie-live
  index pattern: zeek-cowrie-live-*
  time field: @timestamp

cowrie-app
  index pattern: cowrie-app-*
  time field: @timestamp
```

### 5.4 Kibana Dashboard案

#### Dashboard 1: AWS Cowrie Attack Monitoring

- 攻撃件数の時系列
- 攻撃元IPランキング
- 宛先ポートランキング
- Zeek `conn_state` 分布
- usernameランキング
- passwordランキング
- Cowrie session一覧
- 実行コマンド一覧

#### Dashboard 2: Local IoT IDS Demo

現時点の PoC では dashboard 化していない。ローカル IDS alert は console 出力で確認する。

---

## 6. ローカルIoT擬似環境

### 6.1 重要な前提

疑似攻撃は、Docker内のattackerコンテナからではなく、**同一LAN上の別物理マシン**から実行する。

そのため、fake_iot_deviceは同一LAN上の別マシンから到達可能でなければならない。

### 6.2 推奨構成

最初は、fake_iot_device だけを Docker コンテナとして手元PC上に立てる。HTTP は持たせず、SSH 接続試行を受ける最小サービスにする。

```text
同一LAN

[Attacker Machine]
  └─ 疑似攻撃を実行
       ↓
[Local PC]
  ├─ fake_iot_device
  ├─ Zeek sensor
  ├─ IDS runtime
  └─ Elasticsearch/Kibana
```

### 6.3 ネットワーク設計の注意

別物理マシンから攻撃するため、Docker bridge内だけに閉じたサービスでは到達できない。

次のいずれかにする。

#### 採用案: fake_iot_device のポートをホストに publish する

Docker Compose で以下のようにする。

```yaml
services:
  fake_iot_device:
    ports:
      - "2223:2222"
```

別マシンからは以下に接続する。

```text
ssh -p 2223 iot@<LOCAL_PC_LAN_IP>
```

`2222` は Cowrie と競合しやすいため、ローカル fake_iot_device 側は `2223` を使う。

---

## 7. ローカル疑似攻撃の設計

### 7.1 通常通信

今回の PoC では、通常通信 generator は必須にしない。必要なら、発表者の操作端末から `ssh -p 2223 iot@<LOCAL_PC_LAN_IP>` のような正常接続を補助的に見せればよい。

### 7.2 疑似攻撃

疑似攻撃は同一LAN上の別マシンから実行する。

安全な疑似攻撃例として、SSH ブルートフォース風の接続試行を使う。

```bash
hydra -l iot -P /path/to/passwords.txt ssh://<LOCAL_PC_LAN_IP>:2223 -t 4 -f
```

または、簡易的には次のような接続失敗の繰り返しでもよい。

```bash
for i in $(seq 1 30); do ssh -o PreferredAuthentications=password -o PubkeyAuthentication=no -p 2223 iot@<LOCAL_PC_LAN_IP>; done
```

実マルウェアや外部に被害を出す攻撃コードは使わない。

---

## 8. Zeekの観測設計

### 8.1 AWS側

EC2の外部インターフェース、またはCowrieに到達する通信が見えるインターフェースをZeekで監視する。

目標:

```text
source.ip = 攻撃元グローバルIP
destination.port = Cowrie公開ポート
conn_state = S0 / S1 / SF / REJ / RSTO など
```

Docker内部だけを見て、`source.ip = 172.x.x.x` になる状態は避けたい。

### 8.2 ローカル側

同一LAN上の別マシンから手元PCへの通信を観測する必要がある。

Zeekは、手元PCのLANインターフェースを監視する。

例:

```bash
ip addr
zeek -i <LAN_INTERFACE>
```

目標:

```text
source.ip = 攻撃者マシンのLAN IP
destination.ip = 手元PCのLAN IP
destination.port = fake_iot_device公開ポート
```

Docker bridge内部だけを見てしまうと、別マシンからの通信が意図通り見えない場合がある。

---

## 9. IDS用特徴量生成

### 9.1 悪性データ

AWS Cowrie宛通信をZeekで解析したログから生成する。

```text
AWS Cowrie traffic
  ↓
Zeek JSON logs
  ↓
Python normalizer
  ↓
malicious_features.csv
```

ラベル:

```text
label = malicious
source_type = aws_cowrie
```

### 9.2 良性データ

今回の live PoC では、発表時にその場で `benign_features.csv` を再生成しない。必要なら、既存の leaf CSV や事前生成済み benign データを使う。

### 9.3 共通特徴量スキーマ

最低限、以下を CSV に出す。

```text
daytime
duration
proto
orig_bytes
resp_bytes
orig_pkts
resp_pkts
orig_ip_bytes
resp_ip_bytes
missed_bytes
local_orig
local_resp
conn_state
label
```

学習に使う候補:

```text
duration
proto
orig_bytes
resp_bytes
orig_pkts
resp_pkts
orig_ip_bytes
resp_ip_bytes
missed_bytes
local_orig
local_resp
conn_state
```

学習に使わない管理情報:

```text
source_type
src_ip
dst_ip
```

理由: `source_type` やIPを使うと、モデルが「AWS由来なら悪性」「ローカル由来なら良性」のようなショートカットを学習する危険がある。

---

## 10. IDS実行系

### 10.1 学習

今回の live PoC は、再学習なしで既存学習済みモデルを使う。

```text
FOUNDATION_MODEL_PATH
  ↓
make prepare-live-demo-model   # 不足時のみ demo 用 model を生成
  ↓
src/main/Live/run.py
```

現行の実用サポートは次を前提にする。

- `MODEL_CODE 0`: DNN
- `MODEL_CODE 4`: Logistic Regression

既定では `MODEL_CODE 4` を使う。

### 10.2 推論

ローカル Zeek `conn.log` を監視し、約 1 秒間隔で特徴量化して推論する。

```text
Zeek live conn.log
  ↓
feature-export live
  ↓
new CSV rows only
  ↓
model.predict_proba()
  ↓
alert if score > threshold
```

出力先:

```text
console output
```

例:

```text
[ALERT] event_time=2026-05-14T10:00:01+09:00 src_ip=192.168.1.50 dst_ip=192.168.1.20 dst_port=2223 proto=tcp conn_state=S0 score=0.93 label_key=S0 source_type=local_iot_demo
```

---

## 11. 実装フェーズ

### Phase 1: Simulation / Live 分離

- 既存 runtime を `src/main/Simulation/` に移設
- `make run` は Simulation を起動
- `src/main/Live/` を新設
- 旧 `src/main/*` 参照には薄い互換層を残す

### Phase 2: Live PoC 実装

- `feature-export live` を内部利用する `make run-live` を追加
- `FOUNDATION_MODEL_PATH` を読む live runtime を追加
- 不足時のみ demo 用 model を作る `make prepare-live-demo-model` を追加
- matching flow ごとに console alert を出力

### Phase 3: ローカル IoT 擬似環境

- `docker-compose.demo.yml` を追加
- `fake_iot_device` として SSH サービスコンテナを追加
- host port `2223` を publish
- Zeek live capture 用ログ出力ディレクトリを追加

### Phase 4: 発表用安定化

- Hydra 実行手順を `docs/Liveデモ実行手順.md` に整理
- `make demo-live-reset` と `make demo-live-inject-alert` を追加
- 事前生成済み model / CSV / AWS logs を fallback として使える前提にする
- 既存の `Cowrie Live Attack Monitoring` を Demo1 の可視化に使う

---

## 12. 成果物

今回の実装で最低限そろえた成果物は以下である。

```text
src/main/Simulation/
src/main/Live/
src/main/settings.json                  # compatibility mirror
docker-compose.demo.yml
demo/fake_iot_device/
docs/Liveデモ実行手順.md
docs/デモ当日完全手順.md
docs/AWSセンサーノード準備手順.md
data/models/live_demo_model.pickle      # prepare-live-demo-model 実行後
```

---

## 13. デモ当日の流れ

1. KibanaでAWS Cowrie Attack Monitoring dashboardを開く。
2. AWS上のCowrieに実際の攻撃ログが蓄積されていることを示す。
3. 学習済みモデルが AWS Cowrie 由来悪性通信を前提にしていることを簡単に説明する。
4. ローカルIoT擬似環境を起動する。
5. IDS runtimeを起動する。
6. 同一LAN上の別マシンから Hydra で疑似攻撃を実行する。
7. IDS runtime が console alert を出す。

---

## 14. 注意点

- AWS上のKibana/Elasticsearchは公開しない。
- 攻撃を受けるのはCowrieだけにする。
- ローカルIoT擬似環境は同一LAN内だけで使う。
- 疑似攻撃は自分の管理下の端末・サービスにのみ実行する。
- 本物のマルウェアや外部に被害を出す攻撃コードは使わない。
- Zeekの観測点を誤ると、Docker内部IPしか見えなくなるため注意する。
- fake_iot_device は host port `2223` を使う。
- IDS評価では、AWS由来悪性とローカル由来良性のsource_typeを学習特徴量に入れない。
- 発表中に実攻撃が来ない可能性があるため、事前収集済みログを必ず用意する。

---

## 15. 今回の実装到達点

今回 Codex 側で優先実装した範囲は以下である。

1. `src/main/Simulation/` と `src/main/Live/` の分離
2. `make run-live` と `make prepare-live-demo-model` の追加
3. Zeek `conn.log` を増分 feature 化して新規 row だけ推論する live runtime
4. console alert によるローカル疑似攻撃検知
5. `docker-compose.demo.yml` と `fake_iot_device` による SSH デモ環境
6. `docs/Liveデモ実行手順.md` を含む実行手順の整備

---

## 16. 今回のデモの主張

本デモの主張は以下である。

```text
AWS上のハニーポットで実攻撃を観測し、
その通信をZeek特徴量として抽出し、
手元PC上のIDS学習に利用する。
さらに、手元のIoT擬似環境に対して同一LAN上の別マシンから疑似攻撃を行い、
学習済みIDSが攻撃通信を検出する流れを示す。
```

ただし、Cowrie由来の悪性通信はSSH/Telnet型攻撃の近似であり、すべてのIoT攻撃を代表するものではない。この限界は発表時に明示する。
