# AWSセンサーノード準備手順

## 目的

この手順は、AWS EC2 上に Cowrie + Zeek live capture を置き、local PC 側の Kibana で `Cowrie Live Attack Monitoring` を使うための準備項目を固定する。

この文書で扱うのは次である。

- EC2 側で Cowrie と Zeek live capture を起動する
- local PC 側で ELK と dashboard を起動する
- どこまでが repo 実装済みで、どこからが運用準備かを分ける

## 1. 先に結論

repo 側で実装済みなのは次である。

- EC2 上で使える `docker-compose.cowrie.yml`
- `make cowrie-live-up`
- local PC 側の `make elk-up-cowrie-live`
- `make kibana-import-cowrie-live-dashboard`

まだ運用で決める必要があるのは次である。

- EC2 と local PC のログ転送方法
- EC2 の公開 IP / DNS
- Security Group
- local PC から Kibana を見る時間帯と time range
- secret をどのノードに置くか

## 2. EC2 側の前提

推奨:

- Ubuntu 22.04 以上
- Docker / Docker Compose plugin 導入済み
- repo を clone 済み

必要 port:

- `2222/tcp`
  - Cowrie SSH
- `22/tcp`
  - 管理 SSH

開けないもの:

- `5601/tcp`
- `9200/tcp`
- `5044/tcp`

secret 配置の原則:

- Cowrie センサ専用 EC2 には、不要な ELK 用 `.env` を置かない
- `docker-compose.cowrie.yml` だけで足りるなら、`ELASTIC_PASSWORD` や `ENCRYPTION_KEY` は local PC 側だけに置く
- local ELK 用 secret の扱いは [シークレット管理.md](./シークレット管理.md) を参照

## 3. Security Group

最小構成:

```text
allow TCP 2222 from 0.0.0.0/0
allow TCP 22 from 管理元IPのみ
deny  TCP 5601
deny  TCP 9200
deny  TCP 5044
```

## 4. EC2 側で repo を起動する

EC2 側の repo root:

```bash
make cowrie-live-up
make cowrie-ps
```

期待する service:

- `cowrie`
- `zeek-cowrie-live`

## 5. EC2 側の確認

Cowrie に対して外から接続試行が来ると、少なくとも次が増える。

```text
cowrie/var/log/cowrie/cowrie.json
data/logs/zeek/live/cowrie/current/conn.log
```

簡単な確認:

```bash
ls -l cowrie/var/log/cowrie/cowrie.json
ls -l data/logs/zeek/live/cowrie/current/conn.log
tail -n 5 data/logs/zeek/live/cowrie/current/conn.log
```

## 6. local PC 側の起動

local PC 側 repo root:

```bash
make elk-up-cowrie-live
make kibana-import-cowrie-live-dashboard
make elk-ps
```

Kibana で開くもの:

- `Cowrie Live Attack Monitoring`

## 7. ログ転送について

現在の repo は、EC2 側センサーと local PC 側 ELK を別ノードに置く構成を前提にしているが、転送そのものを自動化する deployment script まではまだ持っていない。

現実的な候補:

- Tailscale 上で rsync / scp
- Tailscale 上で bind mount / SSHFS
- Filebeat を EC2 側で直接 local Elasticsearch に送る

当日直前に新規実装するより、まずは Tailscale 経由の安定したファイル転送で `cowrie.json` と `conn.log` を local 側へ届けるのが安全である。

## 8. 発表前チェックリスト

- EC2 で `make cowrie-ps` が `Up`
- `cowrie.json` が更新されている
- `data/logs/zeek/live/cowrie/current/conn.log` が更新されている
- local PC で `make elk-ps` が `Up`
- Kibana の `Cowrie Live Attack Monitoring` が開ける
- `zeek-cowrie-live-*` と `cowrie-app-*` に document がある

## 9. 当日トラブル時の優先順位

1. local Demo2 は単独で成立させる
2. AWS 側は pre-collected logs と dashboard を使って説明する
3. EC2 から live traffic が見えていれば十分で、転送導線の完璧さは後回しにする
