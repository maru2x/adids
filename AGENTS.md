# adids Agent Guide

## 1. What This Repository Does

`adids` is an adaptive IDS for gateway-monitored IoT traffic.

The repository currently has two practical parts:

1. Feature extraction
   - `Legacy`: direct `pcap -> csv`
   - `Zeek`: `pcap -> zeek json logs -> csv`
2. Simulation runtime
   - reads CSV files
   - runs inference
   - optionally retrains models
   - writes results under `exp/`

For new work, assume **Zeek mode is the primary path** unless the user explicitly asks for Legacy.

## 2. Stable Workflow

The most stable end-to-end flow right now is:

1. Edit `src/util/FeatureExtract/Zeek/settings.json`
2. Run `make pcap-to-log`
3. Run `make log-to-csv`
4. Edit `src/main/settings.json`
5. Set `DATASETS_DIR_PATH` to a **leaf CSV directory** such as `data/csv/unproc/test_region/conn`
6. Run `make run`

Important:
- `DATASETS_DIR_PATH` must point to a directory that contains **CSV files only**
- Do not point it at `data/csv` or `data/csv/unproc`
- The runtime does not recurse into nested directories
- Synthetic validation CSVs may be kept under `data/csv/` for local verification, but they must live in a clearly named synthetic/test fixture directory so they are not confused with real datasets.

## Documentation Consistency Rule

When a code change affects behavior, configuration, input/output layout, supported modes, constraints, or test coverage, update the docs in the same turn.

Session-specific rule: In this session, the agent must not modify `README.md` unless the user explicitly asks for it.
Session-specific rule: In this session, before changing program behavior or editing program files, the agent must explain why the change is needed and get the user's agreement on the proposed fix.

Always check:
- `README.md`
- `AGENTS.md`
- the relevant files under `docs/`

Minimum consistency items:
- command names and command examples
- settings keys and their meaning
- input/output paths and directory layout
- supported modes and current limitations
- what tests/CI do and do not cover

Do not finish a behavior-changing task with code updated but docs still describing the old behavior.

If a docs file contains user-authored prose, preserve tone and structure and prefer minimal-diff edits.

## Naming Conventions

Use the following naming rules for Python code in this repository:

- Python file names must use `snake_case`
- Class names must use `PascalCase`
- Function names must use `snake_case`
- Variable names must use `snake_case`

When touching existing code that does not follow these rules:
- prefer moving it toward these rules if the user has approved the rename or refactor
- update related docs and tests in the same turn when the visible names change
- avoid partial renames that leave imports, entry points, or documentation inconsistent

## Definition of Done

A change is not done until all of the following are true:
- the code works
- the relevant tests pass
- `README.md`, `AGENTS.md`, and the affected `docs/` files agree

## 3. Important Files

### User-facing docs

- `README.md`
- `docs/pcapファイルから特徴量を抽出する方法.md`
- `docs/設定ファイルの各種パラメータ.md`
- `docs/CSVスキーマ仕様.md`
- `docs/実験結果ファイルの見方.md`
- `docs/テスト方針.md`
- `docs/開発タスク.md`
- `docs/ユーティリティ利用方法.md`

### Runtime

- `src/main/run.py`
- `src/main/settings.json`
- `src/main/settings_loader.py`
- `src/main/session_controller.py`
- `src/main/session_definer.py`
- `src/main/drift_detection.py`
- `src/main/model_factory.py`
- `src/main/trainer.py`
- `src/main/evaluator.py`

### Feature extraction

- `src/util/FeatureExtract/Zeek/pcap_to_log_extractor.py`
- `src/util/FeatureExtract/Zeek/log_to_csv_extractor.py`
- `src/util/FeatureExtract/Zeek/normalize_pcap_extensions.py`
- `src/util/FeatureExtract/Zeek/settings.json`
- `src/util/FeatureExtract/Legacy/pcap_to_csv_extractor.py`
- `src/util/FeatureExtract/Legacy/settings.json`

### Utility data modification

- `src/util/DataModified/two_csv_combine.py`
- `src/util/DataModified/csv_daytime_override.py`
- `src/util/DataModified/settings.json`

### Tests / CI

- `tests/unit/data_modified/test_csv_daytime_override.py`
- `tests/unit/data_modified/test_two_csv_combine.py`
- `tests/unit/feature_extract/test_pcap_to_log_extractor.py`
- `tests/unit/feature_extract/test_zeek_log_to_csv_extractor.py`
- `tests/e2e/feature_extract/test_zeek_tiny_golden.py`
- `tests/e2e/feature_extract/test_zeek_scenario_golden.py`
- `tests/e2e/feature_extract/test_zeek_bulk_golden.py`
- `tests/e2e/runtime/test_run_smoke.py`
- `tests/fixtures/`
- `tests/manual/`
- `.github/workflows/ci.yml`

## 4. Current Repository Contracts

### Zeek output layout

`make pcap-to-log` writes:

```text
<OUTPUT_ROOT_DIR_PATH>/<input_dir_name>/<timestamp>/...
```

Example:

```text
data/logs/unproc/test_region/20250513234727/conn.log
```

`make log-to-csv` writes:

```text
<OUTPUT_ROOT_DIR_PATH>/<batch_name>/<target_log_name>/<timestamp>.csv
```

Example:

```text
data/csv/unproc/test_region/conn/20250513234727.csv
```

### Runtime CSV contract

For `FeatureSchema.MODE = "split"`, the runtime expects:

- `daytime`
- `label`
- `conn_state` or whatever is listed in `LABEL_FEATURES`
- all columns listed in `VECTOR_FEATURES`

In the current Zeek CSV path, `daytime` is the flow end time derived from `ts + duration`.
When `duration` is missing or invalid, `daytime` falls back to the start time derived from `ts`.
`duration = 0` is treated as a valid value, not as missing data.

The runtime opens every entry directly under `DATASETS_DIR_PATH`, so nested dirs are invalid input.

## 5. Known Traps

### Trap 1: default `make run` config can fail

`src/main/settings.json` still points at `/home/mnl/adids/data/csv` by default.
That directory contains subdirectories, so `make run` can fail with `IsADirectoryError`.

### Trap 2: dynamic mode + ensemble method 0

`RETRAINING_MODE = "dy"` with `ENSEMBLE_METHOD_CODE = 0` is currently unsafe.
The current implementation casts raw sigmoid probabilities with `int()`, so `0.7` becomes `0`.
If you touch dynamic mode, inspect `src/main/drift_detection.py` first.

### Trap 3: model support is uneven

Current practical support:
- `MODEL_CODE 0`: DNN
- `MODEL_CODE 4`: Logistic Regression

Known issues:
- `MODEL_CODE 2`: autoencoder path does not match current trainer
- `MODEL_CODE 5`: LSTM input shape mismatch
- `MODEL_CODE 6`, `7`: need extra dependency not in `requirements.txt`

### Trap 4: docs have user-authored wording

`docs/pcapファイルから特徴量を抽出する方法.md` contains user-authored prose.
Prefer minimal-diff edits there. Add information without rewriting tone or structure unless explicitly asked.

## 6. What CI Covers

GitHub Actions currently runs three jobs:

- `unit`
  - `make unit-test`
- `e2e_feature_extract`
  - `pytest tests/e2e/feature_extract -q`
  - uses the official `zeek/zeek:8.0.5` Debian-based image
- `e2e_runtime`
  - `pytest tests/e2e/runtime -q`

`make unit-test` performs a Python syntax pass with `compileall`, then runs the unit tests via `pytest`.

Current coverage:
- `tests/unit/data_modified/`, `tests/unit/feature_extract/` stay reserved for automated tests while `tests/manual/` stays outside the default test path
- `csv_daytime_override.py` baseline shift and missing-`daytime` failure handling
- `two_csv_combine.py` ordered merge, chunk splitting, and header mismatch handling
- `two_csv_combine.py` invalid daytime, empty input, non-positive chunk size, and non-empty output failure handling
- `pcap_to_log_extractor.py` file collection, path resolution, timestamp scan, unique-dir naming, and Zeek error propagation
- `log_to_csv_extractor.py` flow-end-based ordering and duration fallback behavior
- `tests/e2e/feature_extract/test_zeek_pipeline_main_contract.py` wrapper layout and `daytime` contract checks
- `tests/e2e/feature_extract/test_zeek_tiny_golden.py` tiny real `pcap -> zeek log -> csv` golden comparisons
- `tests/e2e/feature_extract/test_zeek_scenario_golden.py` protocol-specific `dns.log` / `ssl.log` expected CSV comparisons
- `tests/e2e/feature_extract/test_zeek_bulk_golden.py` multi-pcap batch expected CSV comparisons
- `tests/e2e/runtime/test_run_smoke.py` minimal runtime smoke coverage

CI currently does **not** cover:
- Legacy mode
- long-running or large real-world datasets
- more rigorous `make run` expectation checks beyond the smoke tests
- dynamic mode prediction aggregation correctness

Optional local coverage:
- `make test-e2e`
- `tests/e2e/feature_extract/test_zeek_tiny_golden.py` runs tiny real `pcap -> zeek log -> csv` golden comparisons when `zeek` is installed
- `tests/e2e/feature_extract/test_zeek_scenario_golden.py` checks protocol-specific `dns.log` / `ssl.log` CSV generation against expected CSV when `zeek` is installed
- `tests/e2e/feature_extract/test_zeek_bulk_golden.py` checks a multi-pcap batch against expected CSV outputs when `zeek` is installed
- `tests/e2e/runtime/test_run_smoke.py` checks that the `src/main/` runtime can process a minimal CSV and write expected output files

## 7. Recommended Commands

### Run tests

```bash
make unit-test
make test-e2e
make test-all
```

### Run Zeek preprocessing

```bash
make pcap-to-log
make log-to-csv
```

### Run simulation

```bash
make run
```

## 8. If You Need the Full Context

Read in this order:

1. `AGENTS.md`
2. `README.md`
3. `docs/設定ファイルの各種パラメータ.md`
4. `docs/CSVスキーマ仕様.md`
5. `docs/実験結果ファイルの見方.md`
6. `docs/テスト方針.md`
7. `docs/開発タスク.md`
8. feature extractor or runtime files relevant to the task
