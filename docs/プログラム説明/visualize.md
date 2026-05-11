# `src/util/Visualize` の説明

## 概要

`src/util/Visualize` は、runtime や drift analysis の結果を図表として可視化するための script 群である。

現在は次の 2 層に分かれている。

- `graph/`
  - 現行の Zeek `conn` leaf CSV など、今の repository 契約に合わせて使う script
- `legacy/`
  - 過去の研究作業で使っていた script 群
  - 固定 path や旧スキーマ前提が混ざるため、既存資産として退避してある

このディレクトリの特徴は次の通り。

- reusable な package というより、研究・論文・発表用の standalone script が多い
- 多くの file が固定 path を直接持つ
- CSV を読み、`matplotlib` / `seaborn` で図を保存するのが中心
- ディレクトリ名がそのまま用途や発表文脈を反映している

以下では subdirectory ごとに整理する。

## `graph/`

現行の安定導線向けの script 群である。

前提:

- 入力は `data/csv/.../conn/<batch_name>` のような **leaf CSV ディレクトリ**
- `daytime` 列を持つ
- 主に Zeek `conn.csv` 系を観測する

### `feature_dataset_overview.py`

Zeek `conn` leaf CSV ディレクトリ全体の概況をまとめる script である。

役割:

- ファイル数、総行数、時刻範囲を集計
- feature ごとの欠損率、最小値、最大値、平均、標準偏差を CSV 保存
- `label` 分布を図示
- `daytime` の時間バケットごとの flow 数を図示
- 各数値 feature のヒストグラムを保存

巨大データを前提に、CSV を chunk 単位で読みながら処理する。

### `sliding_window_feature_drift.py`

Zeek `conn` leaf CSV ディレクトリについて、スライディングウィンドウの feature 分布が、基準分布からどれだけ離れるかを計測する script である。

役割:

- データセット全体、または指定した参照範囲を reference distribution にする
- 一定時間幅の sliding window を流す
- feature ごとに Wasserstein 距離と KS statistic を計算する
- 平均 drift の時系列グラフと feature ごとの drift グラフを保存する

これは旧 `exp1/tsa3.py` で行っていた「population 分布との距離観測」を、現行の leaf CSV 契約と CLI 引数ベースへ寄せたものだと考えると分かりやすい。

### `zeek_conn_leaf_common.py`

上の 2 script で共有する helper 群である。

内容:

- leaf CSV ディレクトリ探索
- feature 解決
- `local_orig` / `local_resp` のような真偽値列の数値化
- plot 用サンプルの down-sampling

## `legacy/`

旧研究作業の script 群である。

この配下には、以前 `graph/` や `exp1/` にあった観測用 script を移してある。
たとえば:

- `legacy/graph/hist_plotter.py`
- `legacy/exp1/tsa.py`
- `legacy/exp1/tsa2.py`
- `legacy/exp1/tsa3.py`
- `legacy/exp1/tsa4.py`

これらは再利用価値がある一方で、次のような前提を持つことが多い。

- path がコード内に固定されている
- legacy 特徴量や過去の CSV 配置を前提にしている
- 実験・発表の文脈に強く依存している

したがって、新しく使うならまず `graph/` 側の現行 script を優先した方が安全である。

## `result/`

`exp/` 配下の実験結果 CSV を比較・結合・集約して plot する script 群である。

### `result_combiner.py`

2 つの評価結果 CSV から同じ metric を横持ち結合し、比較 CSV と比較グラフを作る。

### `dd_result.py`

drift detection の `dd_res.csv` を各実験ディレクトリごとに読み、時系列で plot する。

### `eval_metrics_by_threshold.py`

閾値ごとに存在する `eval_res.csv` を集め、同一 metric を threshold 比較 plot にする。

### `eval_metrics_by_window_size.py`

window size ごとの `eval_res.csv` を横並び比較する。
`st` と `dy` でディレクトリの深さが違う前提を吸収している。

### `eval_comparator.py`

複数ディレクトリの評価 CSV から同一 metric を抜き出し、1 枚の比較グラフへまとめる。

### `training_cost_by_threshold.py`

threshold ごとの `tr_res.csv` を比較し、学習コスト系 metric を plot する。

### `training_cost_by_window_size.py`

評価時刻を基準に、各 window size で発生した training cost を再計算して比較する。
単純 plot ではなく、`eval_res.csv` と `tr_res.csv` の時間窓を付き合わせて cost を再構成する点が特徴である。

## `exp5/`

評価実験 5 系の比較 plot script 群である。

### `combined_plotter.py`

1 つの親ディレクトリ配下にある複数実験の `eval_res.csv` を 1 枚に重ねる。

### `metrics_plotter.py`

各サブディレクトリについて個別に metric plot を作る。
`combined_plotter.py` が「全部まとめる」版なら、こちらは「各実験を個別に出す」版である。

### `fin_nt_delete.py`

No Retrain と Static / Dynamic の比較、および training cost を 2 軸で図にした script である。
論文・発表の最終図作成用に近い構成になっている。

## `b_thesis/`

卒論向けの図表出力 script 群である。

### `dd_result.py`

drift detection の結果を、開始時刻からの経過時間軸へ変換して plot する。

### `ntst.py`

No Retrain と Static Retrain の metric 比較図を作る。
横軸を実日時ではなく経過時間にしている。

### `gplot.py`

単純な曲線画像を 1 枚生成する script で、説明図や装飾図の作成に近い。

## `b_thesis_abs/`

卒論概要や中間発表向けの図を作る script 群である。

### `cw_pw_distance.py`

1 つの `dd_res.csv` について、window 間距離と閾値線を同じ図へ出す。

### `data_drift.py`

良性 / 悪性トラヒックの drift 指標を比較し、特定区間を矩形ハイライトする。

### `dd_method1.py`, `dd_method2.py`, `dd_method3.py`

3D 散布図で drift detection の概念図を描く script 群である。
データ点はコード内固定で、実データ計算ではなく説明図専用である。

### `fin.py`

No Retrain / Static / Dynamic の metric と training cost を別図で出す総合比較 script である。
経過時間軸への変換、training event の縦線表示などが含まれる。

## `2025ieice_abs/`

2025 年 IEICE 関連発表向けの図表 script 群である。

### `dd_method.py`

drift metric の時系列と、過去 window / 現在 window の KDE を同時に可視化する。
時系列図では背景色と矩形枠で window 範囲を示している。

### `fin.py`

No Retrain / Static / Dynamic の比較と training cost plot をまとめる script である。
`b_thesis_abs/fin.py` と近い目的だが、図の見せ方や target metric が異なる。

## 読み方のコツ

- `Visualize` 配下は、まずディレクトリ名で目的を当てる方が早い
- 現在の安定導線なら `graph/` を先に見る
- `legacy/exp1` は過去のデータ観測・分布比較の蓄積として読む
- `result`, `exp5` は実験結果比較
- `b_thesis*`, `2025ieice_abs` は論文・発表向けの図作成
- `legacy/` 配下は固定 path を直接持つ file が多いため、再利用したい場合は最初に path 定数部を見るのがよい

## 補足

- これらの script は runtime 本体から呼ばれるわけではない
- あくまで研究作業・分析・図表出力の補助群として理解するのが自然である
