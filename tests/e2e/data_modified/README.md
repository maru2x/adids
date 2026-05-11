## 概要

このディレクトリでは、`src/util/DataModified/` 配下の CSV 加工スクリプトに対して、
固定入力 CSV と expected CSV を使った golden E2E テストを置く。

現在は次を確認する。

- `align_mix.py`
  - 片側の `daytime` をもう片側へ合わせ、そのまま merge した結果が expected CSV と一致すること
- `two_csv_combine.py`
  - 時系列 merge と chunk 分割結果が expected CSV と一致すること
- `csv_daytime_override.py`
  - baseline 平行移動結果と出力ファイル名が expected CSV と一致すること

実行方法:

```bash
make test-DataModif
```

この E2E はローカル向けで、現時点では CI job には含めない。
