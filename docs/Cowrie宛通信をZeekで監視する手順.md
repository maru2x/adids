# Cowrie宛通信をZeekで監視する手順

## 目的

この手順は、Cowrie に届く SSH 通信を Zeek live capture で観測し、`conn.log` を repo 管理下の path に出しつつ、ELK へ投入できることを確認するためのものである。

この段階では、まず `conn.log` の flow-level 監視だけを対象にする。
`ssh.log` や `notice.log` などは Zeek 側で生成されうるが、現在の ELK ingest は `conn.log` のみを扱う。

## 前提

- Docker / Docker Compose が使えること
- `make cowrie-up` が動作済み、または Cowrie 単体基盤の意味を理解していること
- `make elk-up-cowrie` が動作済み、または Cowrie app ingest の意味を理解していること

Cowrie 単体起動は [Cowrieを起動する手順.md](./Cowrieを起動する手順.md) を参照。

## 1. Cowrie + Zeek live capture を起動する

```bash
make cowrie-live-up
```

このコマンドは次を行う。

- `cowrie`
- `zeek-cowrie-live`

`zeek-cowrie-live` は `cowrie` と同じ network namespace を共有し、`eth0` を `zeek -i` で監視する。

## 2. 起動状態を確認する

```bash
make cowrie-ps
```

起動に成功すると、少なくとも次の 2 service が `Up` になる。

- `cowrie`
- `zeek-cowrie-live`

## 3. Zeek live log の保存先

現在の live log 出力先は次である。

```text
data/logs/zeek/live/cowrie/current/
```

最初の確認で重要なのは次の file である。

```text
data/logs/zeek/live/cowrie/current/conn.log
```

## 4. ELK 側を起動する

```bash
make elk-up-cowrie-live
```

この target は、Cowrie app log 用 `filebeat-cowrie01` を起動し、`filebeat/cowrie_live_enrich_pipeline.json` を Elasticsearch に登録したうえで、Zeek live `conn.log` 用 `filebeat-cowrie-live01` を起動する。

GeoIP/ASN pipeline だけを再投入したい場合は、次を使う。

```bash
make es-put-cowrie-live-enrich-pipeline
```

## 5. 最小確認

Cowrie へ接続を試みる。

```bash
nc 127.0.0.1 2222
```

接続後、1 行だけ SSH client banner を送る。

```text
SSH-2.0-test-client
```

このあと、次の 2 系統が増えることを確認する。

- `cowrie/var/log/cowrie/cowrie.json`
- `data/logs/zeek/live/cowrie/current/conn.log`

さらに Elasticsearch では、次の 2 index pattern が増える。

- `cowrie-app-*`
- `zeek-cowrie-live-*`

## 6. Data View

Kibana では次の Data View を使う。

- `cowrie-app`
  - 攻撃者行動を見る
- `zeek-cowrie-live`
  - flow 情報を見る

`zeek-cowrie-live` の定義は次でよい。

- Name: `zeek-cowrie-live`
- Index pattern: `zeek-cowrie-live-*`
- Timestamp field: `@timestamp`

現在 repo に保存済みの realtime dashboard は、[cowrie_live_attack_monitoring.ndjson](/home/mnl/adids/docs/kibana_saved_objects/cowrie_live_attack_monitoring.ndjson) を import して使う。
この dashboard は `zeek-cowrie-live-*` だけを対象にし、`cowrie-app-*` は含めない。
また、GeoIP/ASN enrich が有効なら `source.ip`, `source.geo.country_name`, `source.as.organization.name` を使った panel と map が有効になる。

Kibana 起動後の canonical な import は次で行う。

```bash
make kibana-import-cowrie-live-dashboard
```

## 7. 停止する

Cowrie / Zeek live sidecar の停止:

```bash
make cowrie-down
```

ELK 側の停止:

```bash
make elk-down
```

## 想定トラブル

### `conn.log` が出ない

- `make cowrie-ps` で `zeek-cowrie-live` が `Up` か確認する
- `data/logs/zeek/live/cowrie/current/` が作られているか確認する
- Cowrie に実際に接続したか確認する

### `zeek-cowrie-live-*` に document が出ない

- `make elk-up-cowrie-live` で `filebeat-cowrie-live01` を起動したか確認する
- `data/logs/zeek/live/cowrie/current/conn.log` が JSON Lines になっているか確認する
- `@timestamp` 用の `ts` field が入っているか確認する

### `src_ip` が localhost にならない

- Cowrie と Zeek は Docker network namespace 上で通信を見ているため、`src_ip` は host の `127.0.0.1` ではなく bridge 側 address になる

### country / ASN / map が空のまま

- localhost からの検証では `source.ip` が private address になるため、GeoIP enrich は空でも正常である
- public source IP が観測されたときに `source.geo.*` と `source.as.*` が入る

## 関連ドキュメント

- Cowrie 単体起動: [Cowrieを起動する手順.md](./Cowrieを起動する手順.md)
- ELK 全体構成: [ELK構成とデータフロー.md](./ELK構成とデータフロー.md)
- handoff: [cowrie_zeek_elk_ids_handoff_v2.md](./cowrie_zeek_elk_ids_handoff_v2.md)
