# CSVスキーマ仕様

## 概要

`make run` が読む CSV は、`src/main/settings.json` の `FeatureSchema` に従う。

現在の本体は次の2種類を扱う。

- `zeek`: Zeek モード向け
- `legacy`: 旧 `pcap_to_csv_extractor.py` 向け

重要:
- `DATASETS_DIR_PATH` には **CSV ファイルだけが並ぶディレクトリ** を指定する
- 本体はサブディレクトリを自動では探索しない
- 余分な列はあってもよいが、必要列が欠けているとエラーになる
- `src/util/Validate/validate_csv_dataset.py` を使うと、runtime に渡す前に leaf CSV ディレクトリの契約違反を点検できる

## 1. 共通ルール

### ディレクトリ構造

本体は `DATASETS_DIR_PATH` 直下の各エントリをそのまま `open()` する。

有効な例:

```text
data/csv/zeek/conn/2201AusEast/
  00000_20250513234728.csv
  00001_20250513240000.csv
```

無効な例:

```text
data/csv/
  test_run.csv
  unproc/
```

このようにディレクトリが混ざると `IsADirectoryError` で落ちる。

### `daytime`

どのモードでも `daytime` 列が必要。

形式:

```text
YYYY-MM-DD HH:MM:SS
```

例:

```text
2025-05-13 23:47:27
```

本体はこの列を `datetime.strptime(..., "%Y-%m-%d %H:%M:%S")` で読む。

Zeek モードの `log-to-csv` では、`daytime` は `conn.log` の `ts` をそのまま使うのではなく、原則として `ts + duration** を JST 文字列へ変換したものになる。
つまり `daytime** は開始時刻ではなく、CSV 化された**フローが観測完了した時刻**として扱う。

補足:
- `duration = 0` は有効値として扱う
- `duration` が空文字、欠落、非数値のときだけ `daytime` は `ts` ベースへフォールバックする
- 現在の `conn.log -> csv` 変換では、`conn.log` に `duration` が無い row でも CSV 側には `duration` 列を残し、その row の値は `0` として出力する

### `label`

どのモードでも `label` 列が必要。

- 数値として解釈できる必要がある
- 実装上は `int(float(value))` で読まれる
- ふつうは `0` または `1`

## 2. `zeek` スキーマ

### 想定用途

Zeek モードの `log-to-csv` が出した `conn.csv` 系を読むときに使う。

### 必須列

`src/main/settings.json` の既定値なら、最低限次が必要。

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

一般化すると:
- `daytime`
- `LABEL_COLUMN`
- `LABEL_FEATURES` に入っている列全部
- `VECTOR_FEATURES` に入っている列全部

余分な列があってもよい。たとえば Zeek 由来の:
- `uid`
- `id.orig_h`
- `id.resp_h`
- `proto`
- `service`
- `history`
- `ip_proto`

などは存在していても無視される。

### 値の扱い

#### 数値列

`VECTOR_FEATURES` は基本的に `float()` で解釈される。

既定値で空文字を `0.0` にする列:
- `duration`
- `orig_bytes`
- `resp_bytes`
- `orig_pkts`
- `resp_pkts`
- `orig_ip_bytes`
- `resp_ip_bytes`
- `missed_bytes`

補足:
- `one-way` のように Zeek JSON に `orig_bytes` / `resp_bytes` が無い row でも、`conn.log` 由来 CSV では列自体は残す
- その場合、値が空文字でも runtime 側で `0.0` として扱える

それ以外で数値に変換できない場合はエラーになる。

#### 真偽値列

`local_orig` と `local_resp` は真偽値として扱われる。

受け付ける値:
- 真: `1`, `true`, `t`, `yes`, `y`
- 偽: `0`, `false`, `f`, `no`, `n`

大文字小文字は無視される。

### `LABEL_FEATURES` の意味

`LABEL_FEATURES` はモデルを分けるキーになる。

既定値では:

```json
"LABEL_FEATURES": ["conn_state"]
```

なので、たとえば:
- `conn_state=SF`
- `conn_state=S0`

のように列値ごとに別モデルを持つ。

複数列を指定した場合は `|` で連結される。

例:

```text
conn_state|service
SF|http
```

### 最小例

```csv
daytime,label,conn_state,duration,orig_bytes,resp_bytes,orig_pkts,resp_pkts,orig_ip_bytes,resp_ip_bytes,missed_bytes,local_orig,local_resp
2025-05-13 23:47:27,0,SF,0.0984,71,377,6,4,335,549,0,True,False
```

この例では、`daytime` は開始時刻ではなく `ts + duration` の値だと考える。

### Zeek モードでの標準入力

Zeek モードを使うなら、まずは `TARGET_LOGS = ["conn.log"]` にして、次のような leaf ディレクトリを `DATASETS_DIR_PATH` に渡すのが標準。

```text
data/csv/zeek/conn/<batch_name>
```

## 3. `legacy` スキーマ

### 想定用途

`src/util/FeatureExtract/Legacy/pcap_to_csv_extractor.py` の出力を読むときに使う。

### 必須列

Legacy 出力のヘッダは次。

- `ex_address`
- `in_address`
- `daytime`
- `rcv_packet_count`
- `snd_packet_count`
- `tcp_count`
- `udp_count`
- `most_port`
- `port_count`
- `rcv_max_interval`
- `rcv_min_interval`
- `rcv_max_length`
- `rcv_min_length`
- `snd_max_interval`
- `snd_min_interval`
- `snd_max_length`
- `snd_min_length`
- `label`

本体が入力特徴量として使うのは、通常このうち `LEGACY_FEATURES` に入っている列。

### 注意

- Legacy 導線は Zeek 導線よりメンテナンス優先度が低い
- 新規実験では Zeek モードを優先した方が安全
- Legacy CSV を使う場合は `FeatureSchema.MODE = "legacy"` に切り替える必要がある

## 4. 本体がエラーにする条件

### 列定義のエラー

次のような場合は実行時エラーになる。

- `VECTOR_FEATURES` が空
- `VECTOR_FEATURES` に重複がある
- `LABEL_FEATURES` に重複がある
- `LABEL_FEATURES` と `VECTOR_FEATURES` が重複している
- `LABEL_COLUMN` が CSV に存在しない
- 必要列が CSV に存在しない

### 値のエラー

次のような場合も実行時エラーになる。

- 数値列に数値化できない文字列が入っている
- `local_orig` / `local_resp` に解釈できない値が入っている
- `label` が数値として読めない
- `daytime` の書式が `%Y-%m-%d %H:%M:%S` ではない

## 5. よくあるミス

- `DATASETS_DIR_PATH` に途中ディレクトリを指定する
- `zeek` のまま Legacy CSV を読ませる
- `legacy` のまま Zeek `conn.csv` を読ませる
- `TARGET_LOGS` を複数にしたのに、本体で `conn/` ではなくその親を指定する
- `local_orig` / `local_resp` を `TRUE/FALSE` 以外の独自表記にする

## 6. 関連ドキュメント

- [設定ファイルの各種パラメータ.md](./設定ファイルの各種パラメータ.md)
- [pcapファイルから特徴量を抽出する方法.md](./pcapファイルから特徴量を抽出する方法.md)
- [実験結果ファイルの見方.md](./実験結果ファイルの見方.md)
