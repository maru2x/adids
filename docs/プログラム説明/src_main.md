# `src/main` の説明

## 概要

`src/main` は、この repository の runtime 本体である。
現在は `Simulation/` と `Live/` に分かれている。

処理の大きな流れは次の通り。

1. `Simulation/run.py` または `Live/run.py` が起動する
2. それぞれの `SettingsLoader` が対応する `settings.json` を読む
3. `SessionController` が出力先や結果バッファを初期化する
4. `ModelFactory` が基礎モデルを作る
5. `NoRetrainSession` / `StaticSession` / `DynamicSession` のいずれかが CSV を順次読みながら推論・評価・再学習を行う
6. `SessionController` が結果ファイルを `exp/` 配下へ保存する

## ファイルごとの説明

### `src/main/Simulation/settings.json`

runtime の挙動を決める設定ファイルである。

主に次を持つ。

- 実験出力先の基準パス
- 利用モデル
- 特徴量スキーマ
- 入力 CSV ディレクトリ
- セッション開始時刻と実行範囲
- 再学習モード
- 評価周期
- 動的再学習用のドリフト検知窓設定

このファイルは、`SettingsLoader` と `SessionDefiner` 系クラスから広く参照される。

### `src/main/Simulation/run.py`

runtime の最小入口である。

中身はかなり薄く、次の 3 つを順に行うだけである。

- `SettingsLoader()` で設定を読む
- `SessionController(loader)` でセッション管理を初期化する
- `ModelFactory(...)` を作り、`session.run(model_factory)` を呼ぶ

このファイル自身は判断ロジックをほとんど持たず、「初期化の順序を固定するランチャー」という位置づけである。

### `src/main/Simulation/settings_loader.py`

`settings.json` を読み、実行時設定として扱いやすい形にするクラスである。

主な責務は次の通り。

- JSON の読み込み
- `Log.INIT_TIME` の初期化
- TensorFlow 関連環境変数の設定
- 単純な `get()` アクセス
- `FeatureSchema` に応じた入力次元数の計算
- 実行後ログ付き設定の保存

注意点:

- 初期化時に設定全体を `print()` する
- 環境変数設定は TensorFlow import より後なので、完全には効かないことがある

### `model_factory.py`

モデル生成責務を集約したファイルである。

`ModelFactory` クラスは、`MODEL_CODE` に応じてモデル constructor を切り替え、必要なら foundation weight を読み込んで返す。

主要要素:

- `ModelFactory`
  - `foundation_model` を初期生成する
  - `create_model()` で同じ種類の新規モデルを追加生成する
  - `FOUNDATION_MODEL_PATH` がある場合は pickle weights を読む
- モデル関数群
  - `dnn`
  - `rnn`
  - `autoencoder`
  - `svm`
  - `logistic_regression`
  - `lstm`
  - `random_forest`
  - `gradient_boosting`

注意点:

- `random_forest` と `gradient_boosting` は未導入依存のため `ValueError`
- `lstm` や `autoencoder` は現行の trainer / input 形状との整合に注意が必要

### `trainer.py`

再学習 1 回分を担当する小さな関数ファイルである。

`train()` は次を行う。

- 再学習用配列を DataFrame に変換
- feature と target を分離
- `model.fit(...)`
- 学習時間の計測
- accuracy / loss の最終値取得
- `m{i}_weights/<timestamp>.pickle` へ weights 保存
- 正常件数 / 攻撃件数 / 総件数を集計

返り値は `(model, training_summary_row)` である。

### `evaluator.py`

推論結果の評価を 1 評価区間ぶんまとめる関数ファイルである。

`evaluate()` は次を返す。

- `TP`, `FN`, `FP`, `TN`
- `flow_num`
- `TP_rate`, `FN_rate`, `FP_rate`, `TN_rate`
- `accuracy`, `precision`, `f1`
- binary cross entropy loss
- `benign_rate`

実装上は TensorFlow tensor に変換した上で二値化し、scikit-learn と TensorFlow loss を併用している。

### `drift_detection.py`

動的再学習で使うドリフト検知窓を実装している。

主な構成:

- `DetectionWindow`
  - current window / past window を時間窓で維持する
  - window 内データの前処理スケーリングを行う
  - `detect()` で drift 有無を返す
  - `detect_and_log()` で score を CSV へ書く
- `WindowManager`
  - 複数 window を束ねる
  - 各 window の予測を集約する
  - 最初の drift 判定まで何秒待つか計算する
- 距離関数
  - `cos_similarity`
  - `euc_distance`
  - `euc_distance_hnsw`

注意点:

- `faiss` に依存する
- `ENSEMBLE_METHOD_CODE = 0` は、現在の実装では raw sigmoid を `int()` 化するため危険

### `session_definer.py`

runtime の本体ロジックが最も集中しているファイルである。

中心になるのは `NoRetrainSession` で、ここが CSV の逐次読込、時刻制御、特徴量抽出、ラベル抽出、モデル取得、推論、評価周期処理を担う。

#### `NoRetrainSession`

責務:

- `DATASETS_DIR_PATH` 直下の CSV を順番に開く
- 各行の `daytime` を見ながら session 開始・終了条件を判断する
- `FeatureSchema` に応じて列 index を確定する
- CSV 行から feature vector / label / label key を取り出す
- zeek モードでは `LABEL_FEATURES` ごとに別モデルを持つ
- 評価周期ごとに `evaluate()` を呼ぶ

重要 helper:

- `_set_column_indices()`
  - 必須列確認
  - `LABEL_FEATURES` と `VECTOR_FEATURES` の重複確認
- `_extract_features()`
  - 数値変換
  - Zeek 数値列の空文字を `0.0` 扱い
  - `local_orig`, `local_resp` を bool 変換
- `_extract_label()`
  - `int(float(value))` 変換
- `_make_label_key()`
  - zeek モードのキー生成
- `_get_or_create_model()`
  - zeek モード時のモデル registry 管理

#### `StaticSession`

`NoRetrainSession` を継承し、再学習用バッファ `rtr_list` を持つ。

評価とは別に、`RETRAINING_INTERVAL` を超えたタイミングで蓄積データを `train()` に渡して再学習する。

zeek モードでは label key ごとに別々に再学習する。

#### `DynamicSession`

`NoRetrainSession` を継承し、`WindowManager` を使った drift-driven retraining を行う。

特徴:

- label key ごとに別 `WindowManager` を持てる
- drift 判定周期ごとに `window.detect()` を走らせる
- 検知時のみ `train()` を実行する
- 推論値は複数 window の ensemble から得る

### `session_controller.py`

runtime 全体の orchestration と結果出力を担う。

主な責務:

- 出力ディレクトリの作成
- 評価結果 / 学習結果の列定義
- `RETRAINING_MODE` に応じた session class の選択
- 実行後の `settings_log.json`, `res_eval.csv`, `res_train_*.csv` 保存
- `nmr_fn_rate`, `nmr_benign_rate` の後処理計算

重要点:

- 出力ディレクトリ名は `<INIT_TIME>_<dataset_basename>_<mode>_<model_code>`
- zeek モードでは `keys/<safe_key>/` を切る
- `res_eval.csv` は追加列を後段で連結して保存する

## このディレクトリを読む順番

runtime の理解を始めるときは、次の順が追いやすい。

1. `run.py`
2. `settings.json`
3. `settings_loader.py`
4. `session_controller.py`
5. `session_definer.py`
6. `model_factory.py`
7. `trainer.py`
8. `evaluator.py`
9. `drift_detection.py`

## 補足

- 実際の分岐や制約は `session_definer.py` にかなり寄っている
- runtime の挙動を変える修正では、`settings.json` と `session_definer.py` と `session_controller.py` をセットで見るとズレを見つけやすい
