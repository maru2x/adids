## 概要
IoT機器はそれ自体に十分なセキュリティ機能を備えていないことが多く、近年多くのサイバー攻撃の標的となっている。リソースの少ないIoT機器に処理負荷の高いセキュリティ機能を搭載することは現実的でないという観点から、本プロジェクトでは特にスマートホーム環境に着目し、GWにてIoT機器への通信を一元監視する侵入検知システム `adids` を開発している。`adids` ではGWを通過するトラヒックに対して侵入検知を行いつつリアルタイムに学習することで、適応的な予測を行う。

## 実行方法

本プロジェクトの実行に必要なソフトウェアは`/requirements.txt`にまとめてある。
セットアップの詳細は[src/docs/セットアップ詳細.md](セットアップ詳細)を参照。

本プロジェクトの実行モードは `Simulation` と `Live` の大きく2つ存在する。
- `Simulation`: すでに収集したトラヒック（pcapファイル）から事前に特徴量を抽出し、擬似的にリアルタイムな「侵入検知」「概念ドリフト検出」「モデルの再学習」を行う
- `Live`（未実装）: 実際にGWに設置し、「トラヒック収集」「特徴量抽出」「侵入検知」「概念ドリフト検出」「モデルの再学習」をリアルタイムで行う

`Simulation` モードの実行は以下のコマンドで行う。

```bash
make run
```

各種パラメータの設定は `src/main/settings.json` で行う。
詳細は [src/docs/設定ファイルの各種パラメータ.md](src/docs/設定ファイルの各種パラメータ.md) を参照。

`Simulation` モードの実行には、学習と予測に使用するcsvファイルが必要である。
本研究では、スマートホーム環境を想定して収集されたトラヒックを使用している。
具体的には、[src/docs/トラヒック収集方法.md](src/docs/トラヒック収集方法.md)で説明している。
[src/docs/トラヒック収集方法.md](src/docs/トラヒック収集方法.md)で抽出したpcapファイルは、適切に加工してcsvファイルに抽出する必要がある。
詳細は [src/docs/pcapファイルから特徴量を抽出する方法.md](src/docs/pcapファイルから特徴量を抽出する方法.md) を参照。
補助ユーティリティの使い方は [src/docs/ユーティリティ利用方法.md](src/docs/ユーティリティ利用方法.md) を参照。

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
│  │  ├─ FeatureExtract/    # Legacy / Zeek の特徴量抽出
│  │  └─ DataModified/      # CSV 加工用の補助スクリプト
│  └─ test/                 # 旧来の試験・検証スクリプト
├─ data/                    # 分析基盤上にパスを設定している場合もある
│  ├─ csv/                  # 学習・評価用CSVの置き場
│  ├─ logs/                 # Zeekログなど
│  └─ pcap/                 # PCAPの置き場
└─ exp/                     # 実行結果の出力先
```

## そのほか

- 開発者向けの現状整理と TODO は [src/docs/開発タスク.md](src/docs/開発タスク.md) を参照。
- 詳細なテスト戦略と現在のカバレッジは [src/docs/テスト方針.md](src/docs/テスト方針.md) を参照。
- 補助ユーティリティの設定と実行方法は [src/docs/ユーティリティ利用方法.md](src/docs/ユーティリティ利用方法.md) を参照。
- よく使うプログラムは`make`コマンドで呼び出せるようにしてある。

## makeコマンド集

