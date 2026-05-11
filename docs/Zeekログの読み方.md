# Zeekログの読み方

このドキュメントは、`pcap -> log -> csv` 導線で Zeek が出力するログを読むための最小ガイドである。

特に本プロジェクトでは、次の疑問が頻出する。

- `conn.log` の 1 行は何を表しているのか
- `conn_state=SF` や `conn_state=S0` は何を意味するのか
- `weird.log` はエラーなのか
- `ts` や `duration` が最終 CSV の `daytime` にどう変換されるのか

なお、Zeek の正式な定義は公式ドキュメントに従う。
このドキュメントでは、そのうち本プロジェクトでよく使う部分だけを整理する。

## 1. このプロジェクトでよく見る Zeek ログ

`make pcap-to-log` を実行すると、通常は次のようなログが出る。

- `conn.log`
  - もっとも重要なログ
  - 誰が誰と、いつ、どのくらい、どのプロトコルで通信したかを要約する
- `weird.log`
  - Zeek の analyzer が「プロトコルとして読むと何か変だ」と判断した内容を出す
- `packet_filter.log`
  - Zeek がどのパケットフィルタで動いたかを記録する

本プロジェクトでは、通常 `TARGET_LOGS = ["conn.log"]` を使い、最終的な CSV も `conn.log` 由来のものを前提にしている。

## 2. `conn.log` の 1 行は何か

Zeek の `conn.log` は、TCP だけでなく UDP や ICMP も含めて、「通信のまとまり」を 1 行で表すログである。

Zeek 公式では、UDP や ICMP についても `connection` という名前を使うが、実際には **flow semantics** で追跡すると説明している。
つまり、UDP の `conn.log` を読むときは、TCP の完全なセッションと同じものだと思わず、**Zeek が 1 つの flow とみなした要約行**として読む方が安全である。

本プロジェクトの Zeek JSON では、典型的に次のような行が出る。

```json
{
  "ts": 1640995200.0,
  "uid": "CMdzit1AMNsmfAIiQc",
  "id.orig_h": "192.168.0.10",
  "id.orig_p": 12345,
  "id.resp_h": "8.8.8.8",
  "id.resp_p": 53,
  "proto": "udp",
  "duration": 1.0,
  "orig_bytes": 1,
  "resp_bytes": 1,
  "conn_state": "SF",
  "history": "Dd",
  "orig_pkts": 1,
  "resp_pkts": 1
}
```

よく使う列は次の通り。

- `ts`
  - その行で要約された通信について、最初の packet の時刻
- `uid`
  - Zeek が付ける一意 ID
- `id.orig_h`, `id.orig_p`
  - originator 側の IP / port
- `id.resp_h`, `id.resp_p`
  - responder 側の IP / port
- `proto`
  - `tcp`, `udp` など
- `service`
  - Zeek がアプリケーションプロトコルを識別できた場合に付く
- `duration`
  - 通信の継続時間
- `orig_bytes`, `resp_bytes`
  - originator / responder が送った payload byte 数
- `conn_state`
  - Zeek が付ける通信状態の要約ラベル
- `history`
  - どちらがどんな packet を出したかを短い文字列で表したもの
- `orig_pkts`, `resp_pkts`
  - originator / responder が出した packet 数

## 3. originator / responder とは何か

`orig` は **originator**、`resp` は **responder** を表す。

本プロジェクトの fixture では、通常は

- 最初に packet を送った側
  - originator
- それを受ける側
  - responder

として読むと概ね合う。

そのため、たとえば

- `id.orig_h = 192.168.0.10`
- `id.resp_h = 8.8.8.8`

なら、`192.168.0.10` 側から通信が始まったと読める。

## 4. `conn_state` の見方

`conn_state` は Zeek が通信の状態を 1 つの短いコードで要約したものである。

Zeek 公式の `Conn::Info` には多数の state が定義されているが、本プロジェクトでまず重要なのは次の 3 つである。

### `SF`

Zeek 公式では **normal establishment and termination** とされる。

TCP では「正常に開始され、正常に終了した」通信を表す。
UDP については Zeek 公式が明示的に説明しており、**UDP 自体に state はないが、Zeek がその会話を正常な通信として評価した**と読む。

本プロジェクトの benign / malicious roundtrip fixture では、往復のある UDP 通信が通常 `SF` になる。

### `S0`

Zeek 公式では **connection attempt seen, no reply** とされる。要するに「通信が帰ってこない」ということ。

本プロジェクトの UDP fixture では、実務上は

- originator 側の packet は見えた
- その summary row の範囲では responder 側の返答を見ていない

くらいに読むのが安全である。

### `SHR`

Zeek 公式の定義は TCP 寄りで、**responder sent a SYN ACK followed by a FIN, we never saw a SYN from the originator** である。

ただし、この定義を **UDP にそのまま字義通り適用してはいけない**。
Zeek は UDP に対しても同じ `conn_state` のコード体系を使うため、UDP の `SHR` は「SYN/FIN が実際に流れた」という意味ではない。

本プロジェクトの UDP fixture では、`SHR` は

- Zeek が responder 側中心の summary row を別に出した
- Zeek から見ると完全な正常往復 `SF` にはならなかった

程度に読む方がよい。

### 補足

`conn_state` の多くは TCP の state machine に強く寄っている。
したがって、**UDP の解析では、`conn_state` を packet-level の厳密な wire state だと思わず、Zeek の要約ラベルとして読む**のが安全である。

## 5. `history` の見方

`history` は、どちらがどんな packet を送ったかを短い文字列に圧縮したものである。

Zeek 公式では、

- 大文字
  - originator 側の動作
- 小文字
  - responder 側の動作

と説明している。

たとえば TCP の `ShADadFf` は、公式 docs で次のように読まれている。

- `S`
  - originator が SYN を送った
- `h`
  - responder が SYN ACK を返した
- `A`
  - originator が ACK を送った
- `D`
  - originator が payload data を送った
- `a`
  - responder が ACK を返した
- `d`
  - responder が payload data を返した
- `F`
  - originator が FIN ACK を送った
- `f`
  - responder が FIN ACK を返した

本プロジェクトの UDP fixture では、まず次だけ押さえれば十分である。

- `D`
  - originator が payload data を送った
- `d`
  - responder が payload data を送った
- `Dd`
  - 双方が data を送っている

したがって、UDP の benign roundtrip で `history=Dd` が出ていれば、両側に payload があったと読める。

## 6. `weird.log` は何か

`weird.log` は IDS アラートではない。

Zeek 公式では、`weird.log` は **analyzer がそのプロトコルとして理解しづらい、想定外、あるいは例外的な traffic を見たときの記録**である。

つまり、`weird.log` が出たから即「攻撃」ではない。
ただし、次のいずれかを疑う材料にはなる。

- packet が壊れている
- protocol として不自然な payload になっている
- テスト fixture が簡略化されすぎている
- Zeek analyzer がその traffic を素直に解釈できていない

たとえば `zeek_udp_interleaved.pcap` では、ローカルの Zeek 7.0.10 が `weird.log` に

- `DNS_truncated_len_lt_hdr_len`

を出している。

これは `source="DNS"` なので DNS analyzer 由来の weird であり、`UDP/53` なのに payload が DNS header として短すぎる、という方向の異常を示していると読むのが自然である。

この repo の tiny fixture は payload 長を 1 byte にしているため、`port 53` を使うと DNS analyzer を刺激しやすい。

## 7. このプロジェクトでは `ts` と `duration` をどう使うか

Zeek 公式では `ts` は **the time of the first packet** である。

本プロジェクトでは、この `ts` をそのまま runtime に渡していない。

### `pcap_to_log_extractor.py`

- 生成された `*.log` 全体から最小 `ts` を探す
- その値を JST の `YYYYMMDDHHMMSS` に変換する
- log ディレクトリ名に使う

例:

```text
data/logs/unproc/test_region/20250513234727/conn.log
```

### `log_to_csv_extractor.py`

- 各 row の `ts` と `duration` から `daytime` を作る
- 原則は `daytime = ts + duration`
- `duration` が欠損・不正なときだけ `daytime = ts`
- `duration = 0` は有効値として扱う
- `conn.log` に `duration` キーが無い row でも、現在の CSV 変換では `duration` 列自体は残し、その row の値は `0` として出力する
- 最終的に JST の `YYYY-MM-DD HH:MM:SS` 文字列へ変換する

つまり、このプロジェクトの Zeek CSV における `daytime` は、**原則としてフロー開始時刻ではなくフロー終了時刻**である。

## 8. `label` は Zeek の `conn_state` から作っていない

本プロジェクトで CSV に付く `label` は、Zeek の `conn_state` から決めていない。

`log_to_csv_extractor.py` は、`settings.json` の `NetworkAddress` にある

- `BENIGN`
- `MALICIOUS`
- `EXCEPTION`

を使って、`id.orig_h` / `id.resp_h` の所属から `label` を付ける。

したがって、

- `conn_state=SF`
- `conn_state=S0`

であっても、それだけで benign / malicious が決まるわけではない。

## 9. まずどこを見ればよいか

この repo で Zeek 出力を読むときは、最初に次の順で見るとよい。

1. `conn.log`
   - row 数
   - `id.orig_h`, `id.resp_h`
   - `conn_state`
   - `history`
   - `duration`
2. `weird.log`
   - analyzer が traffic を不自然だと見ていないか
3. 変換後 CSV
   - `daytime`
   - `label`
   - `conn_state`
   - `duration`

特に E2E fixture が想定通りに出ないときは、**まず `weird.log` を確認する**のが有効である。

## 10. 参考

- Zeek 公式 `conn.log`
  - https://docs.zeek.org/en/current/logs/conn.html
- Zeek 公式 `Conn::Info`
  - https://docs.zeek.org/en/current/scripts/base/protocols/conn/main.zeek.html
- Zeek 公式 `weird.log`
  - https://docs.zeek.org/en/v8.0.3/logs/weird-and-notice.html
- この repo の CSV 契約
  - [CSVスキーマ仕様.md](./CSVスキーマ仕様.md)
- この repo の前処理手順
  - [pcapファイルから特徴量を抽出する方法.md](./pcapファイルから特徴量を抽出する方法.md)
