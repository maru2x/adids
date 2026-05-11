# プログラム説明

## 概要

このディレクトリには、`src/main` と `src/util` 配下の主要プログラムを理解するための補助ドキュメントを置く。

目的は次の 2 つ。

- 各ファイルが何のためにあるかを素早く把握できるようにする
- 設定ファイル、処理フロー、スクリプト間のつながりを追いやすくする

このディレクトリでは、`__pycache__` や notebook ではなく、実際に読んで理解対象になる `.py` / `settings.json` を主対象にする。

## 読み方

- runtime を理解したい場合
  - [src_main.md](./src_main.md)
- 前処理を理解したい場合
  - [feature_extract.md](./feature_extract.md)
- CSV 加工や補助ユーティリティを理解したい場合
  - [data_modified_and_misc.md](./data_modified_and_misc.md)
- 可視化スクリプト群を理解したい場合
  - [visualize.md](./visualize.md)

個別ファイルの詳細解説:

- [pcap_to_log_extractor.md](./pcap_to_log_extractor.md)

## 対象範囲

### `src/main`

- `src/main/settings.json`
- `src/main/run.py`
- `src/main/settings_loader.py`
- `src/main/model_factory.py`
- `src/main/trainer.py`
- `src/main/evaluator.py`
- `src/main/drift_detection.py`
- `src/main/session_definer.py`
- `src/main/session_controller.py`

### `src/util/FeatureExtract`

- `src/util/FeatureExtract/Legacy/settings.json`
- `src/util/FeatureExtract/Legacy/pcap_to_csv_extractor.py`
- `src/util/FeatureExtract/Zeek/settings.json`
- `src/util/FeatureExtract/Zeek/pcap_to_log_extractor.py`
- `src/util/FeatureExtract/Zeek/log_to_csv_extractor.py`
- `src/util/FeatureExtract/Zeek/normalize_pcap_extensions.py`

### `src/util/DataModified`

- `src/util/DataModified/settings.json`
- `src/util/DataModified/align_mix.py`
- `src/util/DataModified/two_csv_combine.py`
- `src/util/DataModified/csv_daytime_override.py`
- `src/util/DataModified/time_range_filter.py`
- `src/util/DataModified/delete_attack.py`
- `src/util/DataModified/injector.py`

### `src/util/ElasticSearch`

- `src/util/ElasticSearch/es_utils.py`

### `src/util/Validate`

- `src/util/Validate/validate_csv_dataset.py`
- `src/util/Validate/README.md`
- `src/util/Validate/settings.json`

### `src/util/Visualize`

- `src/util/Visualize/graph/feature_dataset_overview.py`
- `src/util/Visualize/graph/sliding_window_feature_drift.py`
- `src/util/Visualize/graph/zeek_conn_leaf_common.py`
- `src/util/Visualize/result/result_combiner.py`
- `src/util/Visualize/result/dd_result.py`
- `src/util/Visualize/result/eval_metrics_by_threshold.py`
- `src/util/Visualize/result/eval_metrics_by_window_size.py`
- `src/util/Visualize/result/eval_comparator.py`
- `src/util/Visualize/result/training_cost_by_threshold.py`
- `src/util/Visualize/result/training_cost_by_window_size.py`
- `src/util/Visualize/exp5/combined_plotter.py`
- `src/util/Visualize/exp5/fin_nt_delete.py`
- `src/util/Visualize/exp5/metrics_plotter.py`
- `src/util/Visualize/b_thesis/dd_result.py`
- `src/util/Visualize/b_thesis/gplot.py`
- `src/util/Visualize/b_thesis/ntst.py`
- `src/util/Visualize/b_thesis_abs/cw_pw_distance.py`
- `src/util/Visualize/b_thesis_abs/data_drift.py`
- `src/util/Visualize/b_thesis_abs/dd_method1.py`
- `src/util/Visualize/b_thesis_abs/dd_method2.py`
- `src/util/Visualize/b_thesis_abs/dd_method3.py`
- `src/util/Visualize/b_thesis_abs/fin.py`
- `src/util/Visualize/2025ieice_abs/dd_method.py`
- `src/util/Visualize/2025ieice_abs/fin.py`
- `src/util/Visualize/legacy/graph/compare_plotter.py`
- `src/util/Visualize/legacy/graph/csv_basic_plotter_with_daytime.py`
- `src/util/Visualize/legacy/graph/hist_plotter.py`
- `src/util/Visualize/legacy/exp1/dist_compare.py`
- `src/util/Visualize/legacy/exp1/drift_plotter.py`
- `src/util/Visualize/legacy/exp1/drift_plotter_mean_all.py`
- `src/util/Visualize/legacy/exp1/feature_importance.py`
- `src/util/Visualize/legacy/exp1/heatmap.py`
- `src/util/Visualize/legacy/exp1/histgram.py`
- `src/util/Visualize/legacy/exp1/tsa.py`
- `src/util/Visualize/legacy/exp1/tsa2.py`
- `src/util/Visualize/legacy/exp1/tsa3.py`
- `src/util/Visualize/legacy/exp1/tsa4.py`

## 補足

- `src/main` と `FeatureExtract/Zeek` は、日常運用で触る頻度が高い
- `DataModified` は研究用データ作成の補助スクリプト群で、設計の新しさにばらつきがある
- `Visualize` は reusable な library というより、研究・分析・図表作成のための standalone script 群である
