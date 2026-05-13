# Cowrieを起動する手順

## 目的

この手順は、Cowrie を単体で起動し、SSH ハニーポットとして待ち受け、JSON ログを repo 管理下の path に出せることを確認するためのものである。

この段階ではまだ ELK ingest や Zeek live capture は行わない。

Cowrie ログを ELK に投入する手順は [ELKでデータを可視化する手順.md](./ELKでデータを可視化する手順.md) を参照。
Cowrie 宛通信を Zeek で live 監視する手順は [Cowrie宛通信をZeekで監視する手順.md](./Cowrie宛通信をZeekで監視する手順.md) を参照。

## 前提

- Docker / Docker Compose が使えること
- `make cowrie-up` を実行できること

構成整理は [cowrie_zeek_elk_ids_handoff_v2.md](./cowrie_zeek_elk_ids_handoff_v2.md) を参照。

## 1. Cowrie を起動する

```bash
make cowrie-up
```

このコマンドは次を行う。

- `cowrie/var/log/cowrie/`
- `cowrie/var/lib/cowrie/`

を作成する。

その後、[docker-compose.cowrie.yml](/home/mnl/adids/docker-compose.cowrie.yml:1) を使って、独立した `adids-cowrie` project として Cowrie container を起動する。

## 2. 起動状態を確認する

```bash
make cowrie-ps
```

起動に成功すると、`cowrie` service が `Up` になる。

## 3. 待受ポート

この repo の単体起動では、Cowrie は host の 2222/tcp に公開される。

```text
127.0.0.1:2222
```

実際の port publish は `0.0.0.0:2222->2222/tcp` だが、ローカル確認では `127.0.0.1:2222` を使えばよい。

## 4. ログ保存先

この構成で canonical に確認するログは次である。

```text
cowrie/var/log/cowrie/cowrie.json
```

`cowrie.log` は将来 config を追加した場合の候補ではあるが、現在の Docker 既定構成では常に生成される前提にしない。

補助データや鍵関連は次に出る。

```text
cowrie/var/lib/cowrie/
```

現時点で動作確認済みなのは host key 群と `uuid` の生成までである。

## 5. 最小確認

別 terminal から 2222/tcp に接続を試みる。

例:

```bash
nc 127.0.0.1 2222
```

接続後、1 行だけ SSH client banner を送る。

```text
SSH-2.0-test-client
```

このあと、`cowrie.json` に少なくとも次の event が出ることを確認する。

- `cowrie.session.connect`
- `cowrie.client.version`
- `cowrie.session.closed`

Docker bridge 越しに接続するため、`src_ip` は `127.0.0.1` ではなく `172.x.x.x` の container bridge address として見える。

## 6. 停止する

```bash
make cowrie-down
```

## 想定トラブル

### container が起動しない

- `make cowrie-ps` で status を確認する
- Docker daemon へ接続できるか確認する

### `cowrie.json` が作られない

- `make cowrie-ps` で container が `Up` か確認する
- 2222/tcp に実際に接続したか確認する
- `cowrie/var/log/cowrie/` が container から書き込めるか確認する
- 必要なら `docker compose -p adids-cowrie -f docker-compose.cowrie.yml logs cowrie` で container stdout/stderr を確認する

### port 2222 が使えない

- 既存 process が 2222 を使っていないか確認する
- 必要なら `docker-compose.cowrie.yml` 側の host port を変更する

## 参考

- Cowrie Docker Quick Start: https://docs.cowrie.org/en/stable/docker/README.html
- Cowrie の files of interest と JSON log path: https://docs.cowrie.org/en/stable/README.html
