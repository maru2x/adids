# `src/util/Visualize` の説明

## 概要

`src/util/Visualize` は、runtime や drift analysis の結果を図表として可視化するための script 群である。

このディレクトリの特徴は次の通り。

- reusable な package というより、研究・論文・発表用の standalone script が多い
- 多くの file が固定 path を直接持つ
- CSV を読み、`matplotlib` / `seaborn` で図を保存するのが中心
- ディレクトリ名がそのまま用途や発表文脈を反映している

以下では subdirectory ごとに整理する。

## `graph/`

### `compare_plotter.py`

単一 CSV の複数 metric を同一グラフ上に重ねる最も基本的な line plot script である。

### `csv_basic_plotter_with_daytime.py`

`daytime` を横軸に取り、指定 metric を 1 枚の折れ線グラフへ出力する簡易 script である。
変数名や一部未定義変数から、作業途中の派生版という色が強い。

### `hist_plotter.py`

指定した前後時間帯に分けて特徴量分布をヒストグラム化し、Wasserstein 距離も計算する大きめの script である。

役割:

- 複数 CSV を結合
- 2 つの時間帯へ分割
- 各 feature を標準化
- before / after の histogram を保存
- Wasserstein 距離を CSV 保存
- さらに評価 metric の時系列グラフ上にハイライト領域を重ねる

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

## `exp1/`

データ特性観測・分布比較・時系列解析のための script 群である。

### `heatmap.py`

任意 CSV を読み、ヒートマップ画像へ変換する対話型 script である。

### `drift_plotter.py`

drift CSV を個別に line plot へ変換する。

### `drift_plotter_mean_all.py`

同じ window size の `mean_dis` を複数ディレクトリ横断で 1 枚に重ねる。

### `histgram.py`

各ディレクトリ内の数値列分布をまとめて histogram 化する。
ディレクトリ単位処理を `ProcessPoolExecutor` で並列化している。

### `dist_compare.py`

複数ディレクトリ間で feature 分布を比較し、

- Wasserstein 距離
- KL divergence
- KS statistic

を計算して行列 CSV に保存する重めの分析 script である。

### `feature_importance.py`

drift 指標 `mean_dis` と各 feature の相関を region / window size / feature の 3 軸で集計し、heatmap や bar chart にする。

### `tsa.py`

指定期間内の feature の値を時系列折れ線として出力する、最も直接的な data observation script である。

### `tsa2.py`

current window と past window を動かしながら、feature ごとの Wasserstein / KL / KS 距離を時間発展として求める初期版の drift 観測 script である。

### `tsa3.py`

population dataset を基準分布として用い、current window の feature 分布が population とどれだけ離れるかを、複数 window size について計算する。
`w_mean_dis`, `ks_mean_dis`, `mean_dis` も後段で追加する。

### `tsa4.py`

`tsa3.py` に近いが、population 自体のヒストグラム作成も含み、より観測用に寄った版である。

## 読み方のコツ

- `Visualize` 配下は、まずディレクトリ名で目的を当てる方が早い
- `exp1` はデータ観測・分布比較
- `result`, `exp5` は実験結果比較
- `b_thesis*`, `2025ieice_abs` は論文・発表向けの図作成
- ほとんどの file が固定 path を直接持つため、再利用したい場合は最初に path 定数部を見るのがよい

## 補足

- これらの script は runtime 本体から呼ばれるわけではない
- あくまで研究作業・分析・図表出力の補助群として理解するのが自然である
