## 概要
IoT機器はそれ自体に十分なセキュリティ機能を備えていないことが多く、近年多くのサイバー攻撃の標的となっている。リソースの少ないIoT機器に処理負荷の高いセキュリティ機能を搭載することは現実的でないという観点から、本プロジェクトでは特にスマートホーム環境に着目し、GWにてIoT機器への通信を一元監視する侵入検知システム `adids` を開発している。`adids` ではGWを通過するトラヒックに対して侵入検知を行いつつリアルタイムに学習することで、適応的な予測を行う。

## 実行方法

本プロジェクトの実行モードは `Simulation` と `Live` の大きく2つ存在する。
- `Simulation`: すでに収集したトラヒック（pcapファイル）から事前に特徴量を抽出し、擬似的にリアルタイムな「侵入検知」「概念ドリフト検出」「モデルの再学習」を行う
- `Live`（未実装）: 実際にGWに設置し、「トラヒック収集」「特徴量抽出」「侵入検知」「概念ドリフト検出」「モデルの再学習」をリアルタイムで行う

`Simulation` モードの実行は以下のコマンドで行う。

```bash
make run
```

各種パラメータの設定は `src/main/settings.json` で行う。
詳細は [docs/設定ファイルの各種パラメータ.md](docs/設定ファイルの各種パラメータ.md) を参照。

## 実行前に必要なセットアップ

実行前に以下二つを行う必要がある。

- 必要なソフトウェアのインストール
  - 本プロジェクトの実行に必要なソフトウェアは`/requirements.txt`にまとめてある。
  - セットアップの詳細は[docs/セットアップ詳細.md](docs/セットアップ詳細.md)を参照。
- 機械学習モデルの学習、評価に使用するデータセットの準備
  -  `Simulation` モードの実行には、学習と予測に使用するcsvファイルが必要である。
  -  本研究では、スマートホーム環境を想定して収集されたトラヒックを使用している。
  -  具体的には、[docs/実験用データセットの作りかた.md](docs/実験用データセットの作りかた.md)で説明している。

## プロジェクト構成
主要なディレクトリだけを抜粋している。

```text
adids/
├─ AGENTS.md                # 他モデル向けの入口ガイド
├─ Makefile                 # bootstrap / run / unit-test / test-e2e / test-all / pcap-to-log / log-to-csv
├─ requirements.txt         # 依存の固定
├─ .github/workflows/       # GitHub Actions
├─ docs/                    # 補足ドキュメント
├─ tests/                   # 自動テストと手動検証用スクリプト
│  ├─ e2e/                  # ブラックボックス的なテスト
│  ├─ fixtures/             # テストに使用するデータセット
│  ├─ unit/                 # ホワイトボックス的なテスト
│  └─ manual/               # 手動確認用スクリプトや補助ファイル
├─ src/
│  ├─ main/                 # 実行本体（make run の入口）
│  ├─ util/                 # 前処理・変換などのユーティリティ
├─ data/                    # 分析基盤上にパスを設定している場合もある
│  ├─ csv/                  # 学習・評価用CSVの置き場
│  ├─ logs/                 # Zeekログなど
│  └─ pcap/                 # PCAPの置き場
└─ exp/                     # 実行結果の出力先
```

## そのほか

- 開発者向けの現状整理と TODO は [docs/開発タスク.md](docs/開発タスク.md) を参照。
- 詳細なテスト戦略と現在のカバレッジは [docs/テスト方針.md](docs/テスト方針.md) を参照。
- よく使うプログラムは`make`コマンドで呼び出せるようにしてある。
- 補助ユーティリティの使い方は [docs/ユーティリティ利用方法.md](docs/ユーティリティ利用方法.md) を参照。

## 運用

### 新しいソフトウェアを利用したい場合

#### pipでインストール可能なソフトウェアを利用したい場合

- `requirements.txt` に、 pipに登録されているソフトウェア名・バージョン名を記述する
- `make bootstrap` で `requirements.txt` の中身をインストールする

#### それ以外の場合

- [docs/セットアップ詳細.md](docs/セットアップ詳細.md) に詳細を追加

### 他のマシンで `requirements.txt` に新しいソフトウェアを追加したとき

- `make bootstrap` で `requirements.txt` の中身をインストールする

## makeコマンド集

### メイン実行系

```bash
make venv       # .venv を作成
make install    # .venv に依存をインストール
make bootstrap  # .venv 作成と依存インストールをまとめて実行
make run        # runtime を実行
make unit-test  # unit テストを実行
make test-e2e   # e2e テストを実行
make test-all   # unit / e2e テストをまとめて実行
```

### 特徴量抽出系

```bash
make pcap-to-log # pcapファイルからlogファイルを作成
make log-to-csv  # logファイルからcsvファイルを作成
```


### データ加工系

```bash
make align-mix             # 片側の daytime をもう片側へ合わせてから mixed CSV を作成
make validate-csv-dataset  # Validate/settings.json の設定で leaf CSV ディレクトリを検査
```

### グラフ作成系

```bash
make run
```

### テスト

```bash
make unit-test
make test-e2e
make test-all
```
