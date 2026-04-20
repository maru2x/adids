# adids

## 概要
IoT機器はそれ自体に十分なセキュリティ機能を備えていないことが多く、近年多くのサイバー攻撃の標的となっている。リソースの少ないIoT機器に処理負荷の高いセキュリティ機能を搭載することは現実的でないという観点から、本プロジェクトでは特にスマートホーム環境に着目し、GWにてIoT機器への通信を一元監視する侵入検知システム `adids` を開発している。`adids` ではGWを通過するトラヒックに対して侵入検知を行いつつリアルタイムに学習することで、適応的な予測を行う。

## 前提
- Debian 12 を前提にしている
- Python 3.11 と `venv` が使えること
- Zeek モードを使う場合は `zeek` コマンドが必要
- `Simulation` を実行する前に、学習対象の CSV を `data/csv/` 配下に用意しておくこと

## セットアップ
よく使うコマンドは `Makefile` で定義済み。とりあえず以下のコマンドを実行すると必要なセットアップは完了する。

```bash
make bootstrap
```

これは次を自動で行う。
- `.venv` の作成
- `requirements.txt` による依存パッケージのインストール

## 実行
本プロジェクトの実行モードは `Simulation` と `Live` の大きく2つ存在する。
- `Simulation`: すでに収集したトラヒック（pcapファイル）から事前に特徴量を抽出し、擬似的にリアルタイムな「侵入検知」「概念ドリフト検出」「モデルの再学習」を行う
- `Live`（未実装）: 実際にGWに設置し、「トラヒック収集」「特徴量抽出」「侵入検知」「概念ドリフト検出」「モデルの再学習」をリアルタイムで行う

`Simulation` モードの実行は以下のコマンドで行う。各種パラメータの設定は `src/main/settings.json` で行う。詳細は [src/docs/設定ファイルの各種パラメータ.md](src/docs/設定ファイルの各種パラメータ.md) を参照。

```bash
make run
```

ただし、事前にトラヒックの収集と特徴量の抽出を行う必要がある。すでにトラヒックを収集して PCAP ファイルが存在している場合は、特徴量抽出コマンドを利用できる。詳細は [src/docs/pcapファイルから特徴量を抽出する方法.md](src/docs/pcapファイルから特徴量を抽出する方法.md) を参照。

重要:
- `src/main/settings.json` の `DATASETS_DIR_PATH` は、CSV ファイルだけが並ぶディレクトリに向ける必要がある
- Zeek モードなら典型的には `data/csv/unproc/<batch_name>/conn` のような末端ディレクトリを指定する
- `data/csv` や `data/csv/unproc` のような途中ディレクトリはそのまま読めない

開発者向けの現状整理と TODO は [src/docs/開発タスク.md](src/docs/開発タスク.md) を参照。

補足ドキュメント:
- [src/docs/CSVスキーマ仕様.md](src/docs/CSVスキーマ仕様.md)
- [src/docs/実験結果ファイルの見方.md](src/docs/実験結果ファイルの見方.md)
- [src/docs/テスト方針.md](src/docs/テスト方針.md)

## プロジェクト構成
主要なディレクトリだけを抜粋している。

```text
adids/
├─ AGENTS.md                # 他モデル向けの入口ガイド
├─ Makefile                 # bootstrap / run / test / pcap-to-log / log-to-csv
├─ requirements.txt         # 依存の固定
├─ tests/                   # CI 用の自動テスト
├─ .github/workflows/       # GitHub Actions
├─ src/
│  ├─ main/                 # 実行本体（make run の入口）
│  │  ├─ Run.py
│  │  ├─ settings.json
│  │  ├─ SessionController.py
│  │  └─ SessionDefiner.py
│  ├─ docs/                 # 補足ドキュメント
│  ├─ util/                 # 前処理・変換などのユーティリティ
│  │  └─ FeatureExtract/    # Legacy / Zeek の特徴量抽出
│  └─ test/                 # 旧来の試験・検証スクリプト
├─ data/
│  ├─ csv/                  # 学習・評価用CSVの置き場
│  ├─ logs/                 # Zeekログなど
│  └─ pcap/                 # PCAPの置き場
└─ exp/                     # 実行結果の出力先
```

## 追加コマンド

### pcap / Zeekログから特徴量CSVを作る
詳細は [src/docs/pcapファイルから特徴量を抽出する方法.md](src/docs/pcapファイルから特徴量を抽出する方法.md) を参照。
設定は `src/util/FeatureExtract/Zeek/settings.json` で行う。`PcapToLog.INPUT_DIR_PATH` / `PcapToLog.OUTPUT_ROOT_DIR_PATH` と `LogToCsv.INPUT_DIR_PATH` / `LogToCsv.OUTPUT_ROOT_DIR_PATH` / `LogToCsv.TARGET_LOGS` / `LogToCsv.NETWORK_KEY` を編集してから実行する。

最小例:

```bash
make pcap-to-log
make log-to-csv
```

拡張子なしの PCAP / PCAPNG が混ざっている場合は、事前に補助スクリプトで `.pcap` / `.pcapng` を付けられる。

```bash
python3 src/util/FeatureExtract/Zeek/NormalizePcapExtensions.py data/pcap/test_region
```

確認だけしたい場合:

```bash
python3 src/util/FeatureExtract/Zeek/NormalizePcapExtensions.py data/pcap/test_region --dry-run
```

このときの出力は次のようになる。

```text
data/logs/unproc/test_region/
  <YYYYMMDDHHMMSS>/
    conn.log
    dns.log
    ...

data/csv/unproc/test_region/
  conn/
    <YYYYMMDDHHMMSS>.csv
```

注意:
- `pcap -> log` には `zeek` コマンドが必要
- `log -> csv` は **JSON行形式** の Zeek ログを前提としている
- `LogToCsv.TARGET_LOGS` は配列で、単一指定でもログ名ごとのサブディレクトリに出力する
- 既存の ASCII 形式 Zeek ログや一般の CSV ファイルはそのままでは入力できない
- `make run` に渡すときは、出力ルートではなく `conn/` のような末端ディレクトリを `DATASETS_DIR_PATH` に設定する

### テスト
詳細なテスト戦略と現在のカバレッジは [src/docs/テスト方針.md](src/docs/テスト方針.md) を参照。
ローカルで CI と同じテストを実行する場合は次を使う。

```bash
make docs-check
make test
```

このテストでは次を確認する。
- Python ソースの構文チェック
- `AGENTS.md` / `README.md` / `src/docs/` の基本整合
- Zeek 前処理の出力構造
- Zeek 実行失敗時の一時ディレクトリ cleanup
- `EXCEPTION` 除外
- `TARGET_LOGS` ごとの CSV 出力
- split スキーマの leaf ディレクトリを使った `nt` / `st` / `dy` の本体スモークテスト
- 不正な CSV や不正な `DATASETS_DIR_PATH` に対する失敗系

### 仮想環境を手で触りたいとき

activate 派:

```bash
source .venv/bin/activate
python -m pip install <package>
```

activate しない派:

```bash
.venv/bin/python -m pip install <package>
```

## よくある詰まりどころ
- `ModuleNotFoundError` が出たら:
  - まず `make bootstrap` を実行
- `make run` が `IsADirectoryError` で落ちたら:
  - `src/main/settings.json` の `DATASETS_DIR_PATH` が途中ディレクトリを指していないか確認する
  - Zeek モードでは `data/csv/unproc/<batch>/conn` のような leaf ディレクトリに直す
- `/mnt/c` などのパスで失敗したら:
  - `src/main/settings.json` の `USER_DIR` / `DATASETS_DIR_PATH` をローカルのパスに直す
