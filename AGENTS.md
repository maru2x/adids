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
- the relevant files under `src/docs/`

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
- `README.md`, `AGENTS.md`, and the affected `src/docs/` files agree
- `make docs-check` passes after behavior-affecting documentation changes

## 3. Important Files

### User-facing docs

- `README.md`
- `src/docs/pcapファイルから特徴量を抽出する方法.md`
- `src/docs/設定ファイルの各種パラメータ.md`
- `src/docs/CSVスキーマ仕様.md`
- `src/docs/実験結果ファイルの見方.md`
- `src/docs/テスト方針.md`
- `src/docs/開発タスク.md`
- `src/docs/ユーティリティ利用方法.md`

### Runtime

- `src/main/Run.py`
- `src/main/settings.json`
- `src/main/SettingsLoader.py`
- `src/main/SessionController.py`
- `src/main/SessionDefiner.py`
- `src/main/DriftDetection.py`
- `src/main/ModelFactory.py`
- `src/main/Trainer.py`
- `src/main/Evaluator.py`

### Feature extraction

- `src/util/FeatureExtract/Zeek/PcapToLogExtractor.py`
- `src/util/FeatureExtract/Zeek/LogToCsvExtractor.py`
- `src/util/FeatureExtract/Zeek/NormalizePcapExtensions.py`
- `src/util/FeatureExtract/Zeek/settings.json`
- `src/util/FeatureExtract/Legacy/PcapToCsvExtractor.py`
- `src/util/FeatureExtract/Legacy/settings.json`

### Utility data modification

- `src/util/DataModified/two_csv_combine.py`
- `src/util/DataModified/csv_daytime_override.py`
- `src/util/DataModified/settings.json`

### Tests / CI

- `src/test/test_docs_consistency.py`
- `src/test/test_csv_daytime_override.py`
- `src/test/test_two_csv_combine.py`
- `src/test/manual/`
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

The runtime opens every entry directly under `DATASETS_DIR_PATH`, so nested dirs are invalid input.

## 5. Known Traps

### Trap 1: default `make run` config can fail

`src/main/settings.json` still points at `/home/mnl/adids/data/csv` by default.
That directory contains subdirectories, so `make run` can fail with `IsADirectoryError`.

### Trap 2: dynamic mode + ensemble method 0

`RETRAINING_MODE = "dy"` with `ENSEMBLE_METHOD_CODE = 0` is currently unsafe.
The current implementation casts raw sigmoid probabilities with `int()`, so `0.7` becomes `0`.
If you touch dynamic mode, inspect `src/main/DriftDetection.py` first.

### Trap 3: model support is uneven

Current practical support:
- `MODEL_CODE 0`: DNN
- `MODEL_CODE 4`: Logistic Regression

Known issues:
- `MODEL_CODE 2`: autoencoder path does not match current trainer
- `MODEL_CODE 5`: LSTM input shape mismatch
- `MODEL_CODE 6`, `7`: need extra dependency not in `requirements.txt`

### Trap 4: docs have user-authored wording

`src/docs/pcapファイルから特徴量を抽出する方法.md` contains user-authored prose.
Prefer minimal-diff edits there. Add information without rewriting tone or structure unless explicitly asked.

## 6. What CI Covers

`make test` runs the same checks as GitHub Actions.
It performs a Python syntax pass with `compileall`, then runs the unit tests.

Current coverage:
- baseline consistency between `README.md`, `AGENTS.md`, and the required files in `src/docs/`
- `src/test/` top-level layout stays reserved for automated tests
- `csv_daytime_override.py` baseline shift and missing-`daytime` failure handling
- `two_csv_combine.py` ordered merge, chunk splitting, and header mismatch handling
- `two_csv_combine.py` invalid daytime, empty input, non-positive chunk size, and non-empty output failure handling

CI currently does **not** cover:
- Zeek extractor behavior
- runtime smoke tests
- actual `zeek` execution

## 7. Recommended Commands

### Run tests

```bash
make docs-check
make test
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
3. `src/docs/設定ファイルの各種パラメータ.md`
4. `src/docs/CSVスキーマ仕様.md`
5. `src/docs/実験結果ファイルの見方.md`
6. `src/docs/テスト方針.md`
7. `src/docs/開発タスク.md`
8. feature extractor or runtime files relevant to the task
