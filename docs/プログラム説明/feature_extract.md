# `src/util/FeatureExtract` の説明

## 概要

`FeatureExtract` は、PCAP や Zeek log を CSV 特徴量へ変換するためのディレクトリである。

現在は大きく 2 系統ある。

- `Legacy`
  - 自作の flow 集約ロジックで `pcap -> csv`
- `Zeek`
  - `pcap -> zeek json logs -> csv`

日常運用では Zeek 系が主経路である。

## `Zeek/`

### `settings.json`

Zeek 前処理の共通設定である。

主に次の 3 ブロックを持つ。

- `PcapToLog`
  - PCAP 入力と log 出力先
- `LogToCsv`
  - log 入力と CSV 出力先
  - 対象 log 名
  - 利用する network key
- `NetworkAddress`
  - `BENIGN`, `MALICIOUS`, `EXCEPTION` のネットワーク定義

`log_to_csv_extractor.py` は、この `NetworkAddress` を使って label 付与と除外判定を行う。

### `pcap_to_log_extractor.py`

Zeek 実行ラッパーであり、`settings.json` に基づいて PCAP 群を Zeek JSON log ディレクトリへ変換する。

このファイルの詳細は個別ドキュメント [pcap_to_log_extractor.md](./pcap_to_log_extractor.md) を参照。

要点だけ書くと、次を担う。

- `.pcap` / `.pcapng` の再帰収集
- `zeek -r ... LogAscii::use_json=T` の呼び出し
- log 内最小 `ts` に基づくディレクトリ命名
- 一時ディレクトリ運用と cleanup
- 失敗した PCAP のスキップと終了時サマリ

### `log_to_csv_extractor.py`

Zeek の JSON Lines log を runtime 用 CSV へ変換するファイルである。

役割は単なる format 変換だけではなく、次の repository 契約をまとめて持っている。

- `settings.json` から対象 log と network 定義を読む
- 単一 log dir と batch dir の両方を受ける
- `TARGET_LOGS` ごとに出力ディレクトリを分け、`<target_log>/<batch_name>` の順で配置する
- `conn.log` などのレコードを JSON として読む
- `ts + duration` を基準に flow end time を計算する
- `daytime` を JST 文字列として出力する
- `BENIGN` / `MALICIOUS` / `EXCEPTION` に基づいて
  - 行除外
  - label 付与
  を行う

重要な関数:

- `normalize_target_logs()`
  - `TARGET_LOGS` の妥当性確認と重複除去
- `resolve_network_config()`
  - `NETWORK_KEY` に対応する network 定義を取る
- `discover_log_dirs()`
  - 入力が単一 log dir か batch dir かを判定する
- `iter_records()` / `load_records()`
  - JSON Lines を辞書配列へ展開する
- `collect_header()`
  - レコード群から CSV header を組み立てる
- `resolve_flow_end_ts()`
  - `ts + duration` の計算を行う
- `sort_records_by_flow_end_time()`
  - flow end time で昇順に並べる
- `should_exclude_record()`
  - `EXCEPTION` を含む通信を除外する
- `assign_label()`
  - `MALICIOUS` を含めば `1`
  - `BENIGN` と外部の通信なら `0`
  - どちらにも該当しなければ `None`
- `write_csv()`
  - 上のルールを適用して最終 CSV を書く

注意点:

- header は「実際に出現したキー」に基づいて作られるため、Zeek が列を一度も出さないケースでは runtime 必須列が欠ける可能性がある
- `daytime` は開始時刻ではなく、原則 `flow end time` である

### `normalize_pcap_extensions.py`

拡張子なし capture file に `.pcap` または `.pcapng` を付ける補助スクリプトである。

役割:

- 指定ディレクトリ配下を再帰探索
- 拡張子なし file の magic header を読む
- PCAP / PCAPNG なら rename 対象として拾う
- `--dry-run` なら実際には rename せず計画だけ表示する

主な関数:

- `resolve_root_dir()`
- `collect_extensionless_files()`
- `detect_capture_extension()`
- `build_rename_pairs()`
- `rename_files()`

`pcap_to_log_extractor.py` は拡張子なし file を拾わないので、このスクリプトは Zeek 前処理の前段補助として意味がある。

## `Legacy/`

### `settings.json`

Legacy flow extractor 用設定である。

主に次を持つ。

- `ONLINE_MODE`
- `TRAFFIC_DATA_PATH`
- `FLOW_TIMEOUT`
- `CAPTURE_TIMEOUT`
- `MAX_WORKER`
- `NetworkAddress`

network 定義の構造は Zeek settings と似ているが、こちらは Legacy 抽出器側の filtering / labeling に使う。

### `pcap_to_csv_extractor.py`

Zeek を使わず、Scapy で PCAP を読み、自前 flow 管理で CSV 特徴量を作る旧系スクリプトである。

構成は 3 層になっている。

#### 1. packet 単位特徴量抽出

- `extract_features_from_packet()`
  - IP / TCP / UDP パケットから
    - 通信方向
    - protocol
    - port
    - tcp flag
    - length
    - label
    を取り出す
  - `MALICIOUS` / `BENIGN` の所属から label と direction を決める
  - 関係ない通信は `(None, None), None` を返して捨てる

#### 2. flow 単位特徴量集約

- `extract_features_from_flow()`
  - 1 flow に含まれる packet 群から
    - packet count
    - protocol count
    - most port / port count
    - 送受信間隔
    - 送受信長
    - label
    を作る

#### 3. flow 管理

- `FlowManager`
  - 現在保持中 flow を dictionary で持つ
  - timeout で古い flow を確定させる
  - `callback()` で sniff された packet を flow に積む
  - `delete_flow()` で flow を CSV 行へ確定する

補助関数:

- `online()`
- `offline()`
- `process_pcap_file()`

末尾の `if __name__ == "__main__":` では、設定読込、IP 集合展開、BPF filter 作成、出力ディレクトリ作成、offline 並列処理までを行う。

注意点:

- 現在の実装は `src/util/FeatureExtract/Legacy/settings.json` ではなく、`src/main/settings.json` を読んでいる
- 現行 runtime の `zeek` スキーマとは列構成が違う
- 実験資産として残っている旧導線であり、新規運用の主経路ではない

## どちらを優先して読むべきか

- 現行の安定導線を知りたい場合
  - `Zeek/settings.json`
  - `pcap_to_log_extractor.py`
  - `log_to_csv_extractor.py`
- 旧研究資産も含めて全体の歴史を知りたい場合
  - `Legacy/pcap_to_csv_extractor.py`

## 補足

- Zeek 系は「外部ツール + ラッパー + CSV 契約」の組み合わせで成り立っている
- Legacy 系は「すべて Python 内で閉じた一体型スクリプト」に近い
