# Zeek Log Fixtures

ここには、`log -> csv` 系テストで使う固定 Zeek JSON ログを置く。

現在の主な fixture:
- `unordered_conn.log`
  - `ts + duration` 順へ並び替わることを確認する
- `zero_duration_conn.log`
  - `duration=0` を有効値として扱うことを確認する
- `duration_fallback_conn.log`
  - `duration` 欠損・非数値時の `ts` フォールバックを確認する
