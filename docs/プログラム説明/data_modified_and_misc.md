# `src/util/DataModified` と補助ユーティリティの説明

## 概要

`DataModified` は、既に抽出済みの CSV データを研究用に加工するためのディレクトリである。

設計の新しさにはかなり差があり、次の 2 系統に分かれる。

- 近年整理された設定駆動スクリプト
  - `two_csv_combine.py`
  - `csv_daytime_override.py`
- 研究用の one-off script
  - `time_range_filter.py`
  - `delete_attack.py`
  - `injector.py`

ここでは `ElasticSearch/es_utils.py` も補助ユーティリティとして一緒に説明する。

## `DataModified/settings.json`

現在は 2 スクリプト向けの設定を持つ。

- `Combiner`
  - 2 つの CSV leaf dir を時系列に merge するための設定
- `DaytimeOverride`
  - 1 系列の `daytime` を平行移動するための設定

比較的新しいスクリプトは、このファイルを entry point として読む。

## `two_csv_combine.py`

2 つの CSV ディレクトリを `daytime` 昇順に merge し、一定件数ごとに split して出力するスクリプトである。

役割:

- 入力 dir 直下の `.csv` だけを対象にする
- 各 dir 内で複数 CSV を 1 本の連続列として扱う
- `daytime` で比較しながら merge する
- `CHUNK_SIZE` ごとに `00000_YYYYMMDDHHMM.csv` のような名前で吐く
- 出力先は空 dir であることを要求する

主要要素:

- `load_settings()`
  - `Combiner` セクションだけを読む
- `list_csv_files()`
  - 入力 dir の直下 CSV 列挙
- `parse_daytime()`
  - `daytime` の strict 変換
- `validate_output_dir()`
  - 非空出力 dir を拒否
- `CsvSequence`
  - 複数 CSV を 1 本の逐次行系列として扱う helper class
  - header 一貫性確認
  - header-only CSV のスキップ
- `flush_rows()`
  - 行バッファを 1 ファイルとして書き出す
- `combine_csv_directories()`
  - merge 全体の本体

性質としては、「runtime が読む leaf CSV dir を人工的に作る」ための補助導線である。

## `csv_daytime_override.py`

1 つの CSV ディレクトリ全体の `daytime` を平行移動するスクリプトである。

役割:

- 入力 dir 直下の CSV を順に読む
- 最も早い `daytime` を求める
- その時刻が `BASELINE` に一致するよう全行を shift する
- shift 後の先頭時刻を使った新ファイル名で出力する

主要要素:

- `load_settings()`
  - `DaytimeOverride` セクションだけを読む
- `list_csv_files()`
- `parse_daytime()`
- `validate_output_dir()`
- `collect_earliest_daytime()`
  - 全 CSV を横断して最小 `daytime` を取る
- `shifted_filename()`
  - 出力ファイル名を組み立てる
- `override_daytime()`
  - shift 本体

用途としては、攻撃データや良性データの時間軸を重ね直して synthetic dataset を作る場面に向く。

## `time_range_filter.py`

CSV 群から指定時間帯だけを抜き出して新しいディレクトリへ保存する one-off script である。

特徴:

- 入出力 path と時間範囲がファイル先頭に直接書かれている
- `daytime` を `datetime` 化して range filter を掛ける
- `rows_per_file` ごとに分割して追記保存する

設定駆動ではなく、研究メモを兼ねた ad-hoc script に近い。

## `delete_attack.py`

指定期間以前の `label == 1` データを削除する one-off script である。

処理内容:

- target dir 配下の CSV を順に読む
- `daytime` を datetime 化する
- `timestamp` より前かつ `label == 1` の行を drop する
- 出力先へ同名 CSV として保存する

攻撃期間を切り落とした比較用データセットを作る意図が強い。

## `injector.py`

ある CSV 系列に、別系列の 1 時間分データを 1 対 1 で混ぜ込むスクリプトである。

流れ:

- source dir の先頭 1 時間分行を集める
- それを `cycle()` で無限反復可能にする
- target dir の各行に対して
  - 元行を書き
  - source 側行の `daytime` だけ target 時刻へ合わせた複製行を書く

結果として、target 系列に source 系列を交互注入した synthetic dataset を作る。

## `es_utils.py`

ElasticSearch 接続補助である。

中身はかなり小さい。

- `es_client()`
  - URL を受け取り `Elasticsearch` client を返す
- `bucketize_conn_per_min()`
  - `zeek.conn` 相当データを date histogram で 1 分ごとに集約する
  - bytes, flows, src_ips, dst_ips を集計する

このファイルは runtime 本体というより、Zeek を ElasticSearch に送っている別基盤と分析系をつなぐための補助関数として使う想定である。

## このディレクトリを読むときの注意

- `two_csv_combine.py` と `csv_daytime_override.py` は、現在のテストが存在し、比較的新しい設計である
- `time_range_filter.py`, `delete_attack.py`, `injector.py` は path や定数がハードコードされており、library 的再利用より作業用 script として読む方が自然
- 研究用 synthetic dataset を作るときは、出力先が runtime の leaf CSV dir 契約を満たしているか確認する必要がある
