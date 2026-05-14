# Liveデモ実行手順

## 概要

この手順は、ローカルの fake IoT SSH サービスに対して、同一LAN上の別マシンから Hydra で接続試行を行い、`make run-live` の console alert を確認するためのものである。

## 前提

- Docker / Docker Compose が使えること
- `.venv` があり、依存が入っていること
- 外部マシンから手元PCの LAN IP に到達できること

## 1. 既存 state を掃除する

再実演前に、前回の `conn.log` / CSV / state を消しておく。

```bash
make demo-live-down
make demo-live-reset
```

## 2. demo model を用意する

既定では `make run-live` 側でも不足時に自動生成するが、先に作っておくなら次でよい。

```bash
make prepare-live-demo-model
```

既定の出力先:

```text
data/models/live_demo_model.pickle
```

## 3. ローカル live capture と fake_iot_device を起動する

既定では、`zeek-local-live` が host 側 NIC を自動検出する。

```bash
make demo-live-up
```

NIC を自分で固定したい場合だけ、次のように上書きする。

```bash
ZEEK_LIVE_INTERFACE=<LAN_INTERFACE> make demo-live-up
```

起動確認:

```bash
make demo-live-ps
```

期待する service:

- `fake_iot_device`
- `zeek-local-live`

補足:

- Zeek 側は checksum offload の影響を避けるため `-C` で起動する
- 起動ログに `[zeek-local-live] interface=...` が出る

## 4. live IDS PoC を起動する

```bash
make run-live
```

既定では次を前提にする。

- 入力 Zeek log: `data/logs/zeek/live/local_iot/current/conn.log`
- 中間 leaf CSV: `data/csv/live/local_iot_demo`
- 対象 protocol: `tcp`
- 対象 dst port: `2223`
- threshold: `0.5`
- poll 間隔: `1.0` 秒

補足:

- `run-live` は内部で `feature-export live` を呼ぶ
- 初期位置は `end` なので、起動前に溜まっていた `conn.log` の既存行は alert 対象にしない
- live CSV の `label` は placeholder で、alert 判定自体には使わない

## 5. 外部マシンから疑似攻撃を実行する

同一LAN上の別マシンから、次のように実行する。

```bash
hydra -l iot -P passwords.txt ssh://<LOCAL_PC_LAN_IP>:2223 -t 4 -f
```

初回確認だけなら、存在しない password を少数だけ入れた `passwords.txt` で十分である。

例:

```text
admin
password
raspberry
letmein
```

## 6. 期待する出力

`make run-live` 側で次のような console alert が出る。

```text
[ALERT] event_time=... src_ip=... dst_ip=... dst_port=2223 proto=tcp conn_state=... score=... label_key=... source_type=local_iot_demo
```

## 7. 緊急 fallback

外部マシンや Hydra が使えないときは、synthetic な `2223/tcp` 行を `conn.log` に 1 件だけ入れて alert 導線を確認できる。

```bash
make demo-live-inject-alert
```

注意:

- これは emergency fallback であり、通常デモの第一選択ではない
- concurrent write を避けるため、この target は `zeek-local-live` を停止してから行を追加する
- fallback 後に live capture を再開したい場合は `make demo-live-up` を再実行する

## 8. よくある詰まりどころ

- `make run-live` より前に `conn.log` が大量に溜まっている
  - 既定の `INITIAL_POSITION = "end"` なので、新着行だけを監視する
- `fake_iot_device` の port を誤る
  - host 側は `2223/tcp`
  - container 内は `2222/tcp`
- `data/csv/live/local_iot_demo` に古い CSV が残り、state file が無い
  - paired state が無いまま CSV だけ残ると、安全のため `run-live` は停止する
- 外部マシンから SSH を打っているのに alert が出ない
  - `data/logs/zeek/live/local_iot/current/conn.log` に `id.resp_p=2223` の行があるか確認する
  - 無ければ capture 側の問題なので `make demo-live-ps` と `docker compose -p adids-demo -f docker-compose.demo.yml logs --tail=20 zeek-local-live` を確認する
  - 有るのに alert が出ないなら `make demo-live-down && make demo-live-reset && make demo-live-up` で state を掃除してやり直す

## 9. 停止する

live IDS PoC は `Ctrl-C` で止める。

demo compose 側は次で停止する。

```bash
make demo-live-down
```
