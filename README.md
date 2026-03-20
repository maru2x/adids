# adids

## 概要
IoT機器はそれ自体に十分なセキュリティ機能を備えていないことが多く、近年多くのサイバー攻撃の標的となっている。リソースの少ないIoT機器に処理負荷の高いセキュリティ機能を搭載することは現実的でないという観点から、本プロジェクトでは特にスマートホーム環境に着目し、GWにてIoT機器への通信を一元監視する侵入検知システム `adids` を開発している。`adids` ではGWを通過するトラヒックに対して侵入検知を行いつつリアルタイムに学習することで、適応的な予測を行う。

## 前提

## セットアップ
よく使うコマンドは `Makefile`で定義済み。とりあえず以下のコマンドを実行すると必要なセットアップは完了する（多分）

```bash
make bootstrap
```

これは次を自動で行います。
- `.venv` の作成
- `requirements.txt` による依存パッケージのインストール

## 実行
本プロジェクトの実行モードは`Simulation`と`Live`の大きく２つ存在する。
- Simulation: すでに収集したトラヒック（pcapファイル）から事前に特徴量を抽出し、擬似的にリアルタイムな「侵入検知」「概念ドリフト検出」「モデルの再学習」を行う。
- Live（未実装）: 実際にGWに設置し、「トラヒック収集」「特徴量抽出」「侵入検知」「概念ドリフト検出」「モデルの再学習」をリアルタイムで行う

`Simulation`モードの実行は以下のコマンドで行う。各種パラメータの設定は `src/main/settings.json`で行う。詳細はhogehoge
```bash
make run
```
ただし、事前にトラヒックの収集と特徴量の抽出を行う必要がある。すでにトラヒックを収集してpcapファイルが存在している場合、本プロジェクトにはpcapファイルから特徴量を抽出するためのプログラムが実装されているので、それを利用することも可能。詳細はhogehoge

## プロジェクト構成
主要なディレクトリだけを抜粋しています。

```text
adids/
├─ Makefile                # bootstrap / run / log-to-csv
├─ requirements.txt        # 依存の固定
├─ src/
│  ├─ main/                # 実行本体（make run の入口）
│  │  ├─ Run.py
│  │  ├─ settings.json
│  │  ├─ SessionController.py
│  │  └─ SessionDefiner.py
│  ├─ util/                # 前処理・変換などのユーティリティ
│  │  └─ LogToCsvExtractor.py
│  └─ test/                # テスト・検証用
├─ data/
│  ├─ csv/                 # 学習・評価用CSVの置き場
│  ├─ logs/                # Zeekログなど
│  └─ pcap/                # PCAPの置き場
└─ exp/                    # 実行結果の出力先
```

## 追加コマンド

### ZeekログからCSVを作る
ZeekのJSONログがある場合:

```bash
make log-to-csv \
  LOG_DIR=data/logs/<log_dir> \
  OUT_CSV=data/csv/<name>/conn.csv \
  NETWORK_KEY=202304 \
  PATTERN=conn.log
```

注意:
- `src/util/LogToCsvExtractor.py` は **JSON行形式** のZeekログを想定しています。
- CSVなど別形式のログにはそのまま使えません。

### 仮想環境を手で触りたいとき

activate派:

```bash
source .venv/bin/activate
python -m pip install <package>
```

activateしない派:

```bash
.venv/bin/python -m pip install <package>
```

## よくある詰まりどころ
- `ModuleNotFoundError` が出たら:
  - まず `make bootstrap` を実行
- `/mnt/c` などのパスで失敗したら:
  - `src/main/settings.json` の `USER_DIR` / `DATASETS_DIR_PATH` をローカルのパスに直す
