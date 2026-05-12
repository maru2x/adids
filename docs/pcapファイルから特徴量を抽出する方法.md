# pcapファイルから特徴量を抽出する方法

## 概要

`adids`プロジェクトにおいて、pcapファイルから特徴量を抽出する方法は大きく2つ用意されている。
- Legacy: 自作プログラムによりpcapファイルからcsv出力を実行するモード。
- Zeek: Zeekによりpcapファイルからlogを出力。その後自作プログラムによりcsv出力を実行する。どんな特徴量を抽出するのかは別途定義されている。

Legacyモードは、卒論研究の際に使用していた特徴量。ただ厳密な5-tuplesのフロー特徴量となっていないため、Zeekの導入により、より現実的な運用の環境に近づけたのがZeekモードである。

ちなみに、LegacyモードとZeekモードで出力されるcsvファイルのカラム形式が異なるため、侵入検知プログラム `make run` などを実行する際は `src/main/settings.json` での設定が必要。

## Legacyモード

### 利用方法

Legacyモードでは `src/util/FeatureExtract/Legacy/pcap_to_csv_extractor.py` を直接実行する。
各種設定は `src/util/FeatureExtract/Legacy/settings.json` で行う。
`TRAFFIC_DATA_PATH` に指定したpcapファイル、もしくはpcapファイルを含むディレクトリを入力として `pcap -> csv` を直接実行する。
出力先は `data/csv/unproc/<init_time>-<input_name>/` 配下となる。
ただし、Legacyモードの特徴量は現行の `zeek` スキーマとは列構成が異なるため、そのまま `Simulation` 本体へ入力する場合は `src/main/settings.json` 側の想定列と一致しているか確認が必要。

## Zeekモード

### 利用方法

前提として、pcapファイルからlogファイルを抽出するためには事前に`Zeek`のインストールが必要。
各種設定は `src/util/FeatureExtract/Zeek/settings.json` で行う。
実行する際は`make`コマンドを用意してあるので、以下コマンドで実行する。

- `make pcap-to-log`
- `make log-to-csv`
- `make pcap-to-csv`

先述したように、Zeekモードでcsvファイルを出力するために、一度 Zeek.log 形式のログをjsonで出力し、それをcsvに変換するという手順をたどる。
`pcap-to-log`はpcapファイルをlogファイルに変換するスクリプトで、`log-to-csv`はlogファイルをcsvファイルに変換するスクリプトである。
また、両コマンドともに `Makefile` で定義しているが、実際の処理ロジックは以下のような対応関係で Python スクリプトに分離している。

- `pcap-to-log`: `src/util/FeatureExtract/Zeek/pcap_to_log_extractor.py`
- `log-to-csv`: `src/util/FeatureExtract/Zeek/log_to_csv_extractor.py`
- `pcap-to-csv`: `src/util/FeatureExtract/Zeek/pcap_to_csv_pipeline.py`
- 拡張子なし PCAP / PCAPNG の補助リネーム: `src/util/FeatureExtract/Zeek/normalize_pcap_extensions.py`

`pcap-to-log` は拡張子が `.pcap` または `.pcapng` のファイルを再帰収集する。
そのため、拡張子なしの PCAP / PCAPNG が混ざっている場合は、事前に補助スクリプトで `.pcap` / `.pcapng` を付けてから `make pcap-to-log` を実行する。

```bash
python3 src/util/FeatureExtract/Zeek/normalize_pcap_extensions.py data/pcap/test_region
```

実際に変更せず確認だけしたい場合は `--dry-run` を付ける。

```bash
python3 src/util/FeatureExtract/Zeek/normalize_pcap_extensions.py data/pcap/test_region --dry-run
```

#### pcap-to-logの使い方

設定項目：
- `PcapToLog.INPUT_DIR_PATH`: logファイルに変換したいpcapファイルを含めたディレクトリを指定する。プロジェクトルートからの相対パスもしくは絶対パスで指定。
- `PcapToLog.OUTPUT_ROOT_DIR_PATH`: 変換後のlogファイルの出力ルートを指定する。実際の出力先は `OUTPUT_ROOT_DIR_PATH/<input_dir_name>/` となる。

このコマンドでは、入力されたディレクトリ配下の `.pcap` / `.pcapng` ファイルを再帰的に収集して処理する。
設定した `PcapToLog.OUTPUT_ROOT_DIR_PATH` の下に、入力ディレクトリ名と同じ名前のディレクトリを作成し、各pcapファイルごとに `zeek -r <pcap> LogAscii::use_json=T` を実行する。
生成された `.log` の最初の `ts` を使って、各ログディレクトリ名を `YYYYMMDDHHMMSS` にする。
壊れたpcapファイルや途中で欠損したpcapファイルに当たって Zeek が失敗した場合は、そのpcapだけを飛ばして残りの処理を継続する。
実行終了後に、欠損していたpcapファイルのパスと失敗理由を stderr のサマリに出す。
標準出力には開始・完了ログも出る。
出力先の batch ディレクトリがすでに存在する場合は、対話端末なら `使う / 削除して作り直す / 中止する` の確認を出す。
非対話環境では自動選択せず、その場で中止する。
確認を出さずに明示的に選びたい場合は、スクリプトに `--reuse` / `--replace` / `--abort` を渡す。
`make` から使うときは次のように変数で渡せる。

```bash
make pcap-to-log PCAP_TO_LOG_ARGS="--replace"
```

実行例：
```
data/example/input_path/
  a.pcap
  b.pcap
  c.pcap
```
このような構造のディレクトリに対し、
```
make pcap-to-log
```
を実行すると、以下のような構造でログが出力される。
```
data/zeek/
  input_path/
    20250513234727/
      conn.log
      files.log
      http.log
      packet_filter.log
      weird.log
    20250513240000/
      ...
```

#### log-to-csvの使い方

設定項目：
- `LogToCsv.INPUT_DIR_PATH`: CSVに変換したいログバッチディレクトリ、もしくは単一ログディレクトリを指定する。
- `LogToCsv.OUTPUT_ROOT_DIR_PATH`: 変換後のcsvファイルの出力ルートを指定する。実際の出力先は `OUTPUT_ROOT_DIR_PATH/<target_log_name>/<batch_name>/` となる。
- `LogToCsv.OUTPUT_CHUNK_SIZE`: batch 全体を `daytime` で再統合したあと、何行ごとに最終CSVを分割するかを指定する。
- `LogToCsv.RUN_ROW_LIMIT`: log を streaming で読みながら、temp run を 1 本作る前にメモリ上へ何行までためるかを指定する。
- `LogToCsv.MERGE_FAN_IN`: temp run を何本ずつ段階マージするかを指定する。
- `LogToCsv.AUTO_VALIDATE_CONN_OUTPUT`: `conn.log` 系 CSV の出力後に runtime 契約チェックを自動実行するかを指定する。
- `LogToCsv.TARGET_LOGS`: CSV化の対象にするログファイル名を配列で指定する。`["conn.log"]` のように1件でも複数件でもよい。
- `LogToCsv.NETWORK_KEY`: 同じ設定ファイル内の `NetworkAddress` から参照するキーを指定する。

実行コマンド:

```bash
make log-to-csv
```

このコマンドでは、入力が単一ログディレクトリならその1件をCSVにし、入力がログバッチディレクトリなら配下の各ログディレクトリをまとめてCSV化する。
`TARGET_LOGS` に複数のログファイル名を指定した場合は、ログ種別ごとにディレクトリを分けてCSVを出力する。単一指定でも同じ構造に揃える。
出力先は `OUTPUT_ROOT_DIR_PATH/<target_log_name>/<batch_name>/` に揃えられる。`target_log_name` には `conn.log` なら `conn` のように拡張子を除いた名前を使う。
また、Zeek の `conn.log` にある `ts` は開始時刻なので、そのままでは CSV 上で時系列が逆転しうる。
そのため現在の `log-to-csv` では、まず各rowの `daytime` を原則 `ts + duration` から作り、一定件数ごとの temp run を作ったうえで、external merge sort により batch 全体の row を `daytime` 昇順に再統合してから最終CSVを chunk 出力する。
`duration = 0` は有効値として扱い、`duration` が空文字・欠落・非数値のときだけ `ts` ベースへフォールバックする。
`ts` 自体が欠落・空文字・非数値で flow end time を決められない row は CSV に出力しない。
また、`TARGET_LOGS` が batch 全体で 1 件も見つからない場合や、最終的に 1 行も CSV 化できない場合は失敗として終了する。
変換中は、対象 log dir ごとの読込件数、一時 run の出力、段階マージ、最終 chunk 数などの進捗ログを標準出力へ出す。
さらに `TARGET_LOGS` に `conn.log` が含まれていて、`AUTO_VALIDATE_CONN_OUTPUT = true` の場合は、CSV 出力後に `validate_csv_dataset.py` を自動実行し、runtime 契約チェックとデータサマリをその場で出す。
`conn.log` 以外のログ種別は、現在の `make run` の標準入力ではないため自動 runtime チェックを省略する。

#### pcap-to-csv の使い方

`pcap-to-csv` は、現在の stable workflow を 1 回で通すラッパーである。

```bash
make pcap-to-csv
```

このコマンドは、

1. `pcap-to-log`
2. `log-to-csv`
3. `conn.log` 系 leaf CSV への自動 runtime 契約チェック

を順に実行する。

重要:

- `pcap-to-csv` は `PcapToLog.INPUT_DIR_PATH` から実際に生成した batch dir をそのまま `log-to-csv` へ渡す
- したがって `LogToCsv.INPUT_DIR_PATH` が古い batch を指していても、`pcap-to-csv` 実行時は今作ったログを優先する
- CSV の出力先や `TARGET_LOGS`, `NETWORK_KEY` などの設定値自体は、従来どおり `src/util/FeatureExtract/Zeek/settings.json` を使う
- `pcap-to-log` 段で既存 batch dir が見つかった場合は、同じ確認を出す
- `既存ディレクトリを使う` を選ぶと、以前の log も今回生成分と一緒に `log-to-csv` の入力に含まれる
- 非対話環境で自動運用したい場合は、`PCAP_TO_CSV_ARGS="--replace"` のように明示指定する

例:

```bash
make pcap-to-csv PCAP_TO_CSV_ARGS="--replace"
```

## 入出力の規約

### 1. pcap ディレクトリを入力した場合

入力:

```text
data/pcap/2201AusEast/
```

コマンド:

```bash
make pcap-to-log
```

出力:

```text
data/logs/zeek/2201AusEast/
  20230401000000/
    conn.log
    dns.log
    ...
  20230401010000/
    conn.log
    dns.log
    ...
```

各サブディレクトリ名は、その PCAP から生成されたログの最初の `ts` を JST の `YYYYMMDDHHMMSS` に変換した値です。

### 2. ログバッチディレクトリを入力して CSV 化する場合

入力:

```text
data/logs/zeek/2201AusEast/
  20230401000000/
  20230401010000/
```

コマンド:

```bash
make log-to-csv
```

出力:

```text
data/csv/zeek/
  conn/
    2201AusEast/
      00000_20230401000000.csv
      00001_20230401010000.csv
```

### 3. 単一ログディレクトリを入力して CSV 化する場合

入力:

```text
data/logs/zeek/2201AusEast/20230401000000/
```

コマンド:

```bash
make log-to-csv
```

出力:

```text
data/csv/zeek/
  conn/
    2201AusEast/
      00000_20230401000000.csv
```

単一ログディレクトリでも、親ディレクトリ名がバッチ名として使われます。

## コマンド例

### ディレクトリ単位で pcap -> log

```bash
make pcap-to-log
```

### ログバッチをまとめて csv 化

```bash
make log-to-csv
```

### pcap から一気に csv 化

```bash
make pcap-to-csv
```

### 単一ログディレクトリを csv 化

```bash
make log-to-csv
```

### 設定変更後に log バッチを csv 化

```bash
make log-to-csv
```
