## 概要

`adids`では、pcapファイルからlogファイルを作成し、logファイルからcsvファイルを作成することで、`Simulation`モードを実行する。
このディレクトリでは、`pcap -> log -> csv` の実導線に問題がないかを検証する E2E テストを置く。

具体的に、本 E2E テストが確認することと、そのテストが記述されたファイルの対応表を以下に示す。

| 確認すること | 記述ファイル |
| 1. 実 `pcap` を `zeek` が読めること | `test_zeek_tiny_golden.py`, `test_zeek_scenario_golden.py`, `test_zeek_bulk_golden.py`, `test_zeek_pipeline_main_contract.py` |
| 2. `pcap_to_log_extractor.py` の出力レイアウトが崩れていないこと | `test_zeek_pipeline_main_contract.py` |
| 3. `log_to_csv_extractor.py` の出力レイアウトが崩れていないこと | `test_zeek_pipeline_main_contract.py` |
| 4. `daytime` の生成ルールが実導線でも崩れていないこと | `test_zeek_tiny_golden.py`, `test_zeek_scenario_golden.py`, `test_zeek_bulk_golden.py`, `test_zeek_pipeline_main_contract.py` |
| 5. 事前に用意した正解のcsvファイルと、`fixtures/pcap`にあるテスト用のpcapファイルをcsvに変換したものが一致すること | `test_zeek_tiny_golden.py`, `test_zeek_scenario_golden.py`, `test_zeek_bulk_golden.py` |

## 各テストの詳細

### 1. 実 `pcap` を `zeek` が読めること

記述ファイル:

- `test_zeek_tiny_golden.py`
- `test_zeek_scenario_golden.py`
- `test_zeek_bulk_golden.py`
- `test_zeek_pipeline_main_contract.py`

この観点では、`fixtures/pcap` に置かれたテスト用の `pcap` ファイルを、実際の `zeek` コマンドに読ませる。

具体的には、次を確認する。

- `zeek` コマンド自体が起動できること
- 対象 `pcap` を `zeek` が正常に処理できること
- 最低限 `conn.log` が生成されること

ここで見ているのは、`pcap` の中身を本プロジェクトが直接解釈できるかではなく、`zeek` を前提にした前処理導線が成立しているかである。

### 2. `pcap_to_log_extractor.py` の出力レイアウトが崩れていないこと

記述ファイル:

- `test_zeek_pipeline_main_contract.py`

この観点では、`pcap_to_log_extractor.py` を `main()` から実行し、`pcap -> log` の wrapper が期待したディレクトリ構造を作れているかを見る。

出力レイアウトのイメージは次の通り。

```text
入力:
pcap/sample_batch/
└─ roundtrip.pcap

出力:
logs/
└─ sample_batch/
   └─ 20220101090000/
      ├─ conn.log
      ├─ packet_filter.log
      └─ weird.log
```

ここで重要なのは、次の 2 点である。

- `sample_batch`
  - 入力ディレクトリ名がそのまま batch 名として使われる
- `20220101090000`
  - `zeek` が出した `*.log` 全体の最小 `ts` を JST に直したディレクトリ名になる

具体的には、次を確認する。

- `<log_root>/<batch>/<timestamp>/conn.log` の形で出力されること
- `timestamp` が `log` 中の最小 `ts` をもとにした名前になること
- 一時ディレクトリ `.tmp_*` が最終的に残らないこと

ここでの主眼は、Zeek の解析内容そのものではなく、本プロジェクト側のラッパーが出力先と命名規則を正しく扱えているかである。

### 3. `log_to_csv_extractor.py` の出力レイアウトが崩れていないこと

記述ファイル:

- `test_zeek_pipeline_main_contract.py`

この観点では、`log_to_csv_extractor.py` を `main()` から実行し、`log -> csv` の wrapper が期待したディレクトリ構造を作れているかを見る。

出力レイアウトのイメージは次の通り。

```text
入力:
logs/
└─ sample_batch/
   └─ 20220101090000/
      ├─ conn.log
      ├─ packet_filter.log
      └─ weird.log

出力:
csv/
└─ conn/
   └─ sample_batch/
      └─ 20220101090000.csv
```

ここで重要なのは、次の 3 点である。

- `conn`
  - `TARGET_LOGS = ["conn.log"]` のように、対象 log 名ごとに最上位ディレクトリが分かれる
- `sample_batch`
  - `pcap -> log` で作られた batch 名がそのままその下のディレクトリ名に使われる
- `20220101090000.csv`
  - 元の log ディレクトリ名が、そのまま CSV ファイル名になる

具体的には、次を確認する。

- `<csv_root>/<target_log>/<batch>/<timestamp>.csv` の形で出力されること
- `DATASETS_DIR_PATH` に直接渡せる leaf CSV ディレクトリになっていること
- `conn.log` から `conn/sample_batch/20220101090000.csv` のように `target_log` ごとに整理されること

ここで見ているのは、CSV の値の厳密一致よりも、runtime に接続するためのレイアウト契約が守られているかである。

### 4. `daytime` の生成ルールが実導線でも崩れていないこと

記述ファイル:

- `test_zeek_tiny_golden.py`
- `test_zeek_scenario_golden.py`
- `test_zeek_bulk_golden.py`
- `test_zeek_pipeline_main_contract.py`

この観点では、`ts` と `duration` から `daytime` がどのように生成されるかを確認する。

具体的には、次を確認する。

- `daytime` が単なる `ts` ではなく、原則として `ts + duration` から作られること
- 生成された `daytime` が JST の `YYYY-MM-DD HH:MM:SS` 形式であること
- CSV の行が `daytime` 昇順に並ぶこと

本プロジェクトでは、`daytime` は「開始時刻」ではなく、原則として「フロー終了時刻」として扱う。そのため、この観点は runtime に入る直前の契約として重要である。

### 5. 事前に用意した正解のcsvファイルと、`fixtures/pcap`にあるテスト用のpcapファイルをcsvに変換したものが一致すること

記述ファイル:

- `test_zeek_tiny_golden.py`
- `test_zeek_scenario_golden.py`
- `test_zeek_bulk_golden.py`

この観点では、`fixtures/expected_csv` に置かれた正解 CSV と、実際に `pcap -> log -> csv` を通して得られた CSV を比較する。

fixture ごとの `raw pcap` と `expected csv` の詳細は、用途ごとに次のドキュメントへ分けてまとめる。

- tiny fixture
  - [golden_fixtures.md](../../fixtures/golden_fixtures.md)
- bulk fixture
  - [bulk_fixtures.md](../../fixtures/bulk_fixtures.md)
- protocol-specific fixture
  - [tests/fixtures/protocol_traffic.md](../../fixtures/protocol_traffic.md)

具体的には、次を確認する。

- 行数が一致すること
- `expected_csv` に書かれた列値が一致すること
- `expected_csv` に含めた header subset が最終 CSV に存在すること
- 併せて runtime が読むための最低限の列契約も満たすこと
- `EXCEPTION` fixture では header-only CSV が期待通りに生成されること

このテストは、fixture ベースの厳密比較に近い。そのため回帰検知には有効だが、`zeek` のバージョン差によって壊れやすいという性質も持つ。

## 補足

現時点では、このディレクトリの E2E テストは大きく次の 2 系統に分かれている。

- `test_zeek_pipeline_main_contract.py`
  - `main()` を通し、wrapper の出力構造や `daytime` 生成ルールといった契約を確認する
- `test_zeek_tiny_golden.py`
  - 1 論点 1 fixture の小さな expected CSV 比較を行う
- `test_zeek_scenario_golden.py`
  - DNS / HTTPS のような protocol-specific traffic を expected CSV と比較する
- `test_zeek_bulk_golden.py`
  - 複数 pcap / 複数 target_log をまたぐ中サイズ batch を expected CSV と比較する

今後は、前者を `contract` 系、後者を `golden` 系として整理していく想定である。

### protocol-specific fixture について

`conn.log` の stable な `golden` 比較とは別に、protocol analyzer 由来の log を見る scenario fixture も持っている。

- `test_zeek_scenario_golden.py`
  - `protocol_traffic/dns_udp_query_response.pcap` から `conn.csv` と `dns.csv` を作り、expected CSV と比較する
  - `protocol_traffic/https_tls_handshake.pcap` から `conn.csv` と `ssl.csv` を作り、expected CSV と比較する

詳細は [tests/fixtures/protocol_traffic.md](../../fixtures/protocol_traffic.md) にまとめる。
