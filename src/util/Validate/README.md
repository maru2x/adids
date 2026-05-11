## 概要

このディレクトリには、runtime へ渡す前の入力や関連成果物を検査する補助スクリプトを置く。

現在は次を持つ。

- `validate_csv_dataset.py`
  - leaf CSV ディレクトリが runtime の想定契約を満たしているかを標準出力へ報告する
- `settings.json`
  - `validate_csv_dataset.py` の既定入力を決める

## runtime 契約とは何か

ここでいう runtime 契約とは、`make run` に渡す `DATASETS_DIR_PATH` が最低限満たしているべき入力条件のことである。

典型的な Zeek モードでは、次のような leaf CSV ディレクトリを指す。

```text
data/csv/zeek/conn/2201AusEast/
  00000_202201010900.csv
  00001_202201010901.csv
```

重要なのは次の点である。

- `DATASETS_DIR_PATH` は CSV ファイルだけが並ぶ末端ディレクトリであること
- runtime はサブディレクトリを再帰探索しないこと
- 必要列が揃っていること
- `daytime` が `%Y-%m-%d %H:%M:%S` 形式で読めること
- ディレクトリ全体をファイル名順に読んだとき、`daytime` が後戻りしないこと

この契約を外すと、runtime は `IsADirectoryError` や `ValueError` を起こしたり、意図しない時系列で実験を進めたりする。

## `validate_csv_dataset.py` が検査すること

`validate_csv_dataset.py` は、指定された leaf CSV ディレクトリに対して主に次を確認する。

- 指定 path が存在し、ディレクトリであること
- 直下に `.csv` 以外のファイルやサブディレクトリが混ざっていないこと
- 少なくとも 1 個以上の CSV があること
- 各 CSV に必要列があること
- 各 CSV が header-only ではなく、少なくとも 1 行以上のデータを持つこと
- 必須列のうち空欄を許さない列に欠損値がないこと
- `daytime` が `%Y-%m-%d %H:%M:%S` 形式で解釈できること
- 各 CSV 内で `daytime` が非減少であること
- ディレクトリ全体でも、前の CSV の最後より次の CSV の先頭が戻っていないこと
- `label` が数値として読めること
- `label` が runtime 評価前提の二値 `0/1` であること
- Zeek スキーマでは、数値列と `local_orig` / `local_resp` の基本的な型が崩れていないこと

## `settings.json`

`validate_csv_dataset.py` は、既定では `src/util/Validate/settings.json` の `CsvDatasetValidator` を読む。

- `DATASET_DIR_PATH`
  - 検査対象の leaf CSV ディレクトリ
- `SCHEMA`
  - `zeek` または `legacy`
- `RUNTIME_SETTINGS_PATH`
  - required columns を解決するために参照する `src/main/settings.json`

CLI 引数を与えた場合は、その値で settings を上書きする。

## Zeek の required columns とは何か

Zeek スキーマでいう required columns は、「このリポジトリの現在の runtime 設定が実際に読む列」のことである。

固定の Zeek 全列を要求しているのではなく、`RUNTIME_SETTINGS_PATH` で指定した `src/main/settings.json` の `FeatureSchema` を見て決める。

具体的には、次を必須として扱う。

- `daytime`
- `LABEL_COLUMN`
- `LABEL_FEATURES` に含まれる列
- `VECTOR_FEATURES` に含まれる列

現在の既定 `src/main/settings.json` では、これは次と同じ意味になる。

- `daytime`
- `label`
- `conn_state`
- `duration`
- `orig_bytes`
- `resp_bytes`
- `orig_pkts`
- `resp_pkts`
- `orig_ip_bytes`
- `resp_ip_bytes`
- `missed_bytes`
- `local_orig`
- `local_resp`

この列集合は、runtime が `session_definer.py` で `daytime` を読み、`LABEL_COLUMN` を正解ラベルとして使い、`LABEL_FEATURES` で model key を作り、`VECTOR_FEATURES` を数値特徴量として `float()` 変換する流れに対応している。

## 出力

結果は標準出力へ出る。

- 問題がなければ `[OK]`
- 問題があれば `[NG]`

違反がある場合は、ファイル名と行番号付きで内容を列挙する。

将来的に、同種の validator を追加する場合もこのディレクトリへ寄せる想定である。
