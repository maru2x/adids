# `pcap_to_log_extractor.py` の説明

## 概要

`src/util/FeatureExtract/Zeek/pcap_to_log_extractor.py` は、`Zeek` 自体の解析ロジックではなく、**このプロジェクト用の実行ラッパー**である。

役割はかなり明確で、`settings.json` から入出力パスを取り、入力ディレクトリ配下の `.pcap` / `.pcapng` を集め、各 PCAP に対して `zeek -r ...` を実行し、生成された `.log` 群を timestamp 名のディレクトリに整理することである。

## 全体像

- 入力は `settings.json` の `PcapToLog.INPUT_DIR_PATH` と `PcapToLog.OUTPUT_ROOT_DIR_PATH`
- Zeek 失敗時はその PCAP をスキップし、最後に失敗一覧をサマリ表示する
- 入力ディレクトリ配下の `.pcap` / `.pcapng` を**再帰的**に集める
- 各 PCAP ごとに一時ディレクトリ `.tmp_XXXX_<stem>` を作り、その中で `zeek` を実行する
- 生成された `.log` の中から最小 `ts` を読み、その JST 時刻を最終ディレクトリ名にする
- 同名ディレクトリが既にあれば `_01`, `_02` を付けて衝突回避する
- 途中で失敗したら `.tmp_*` を消す

## 定数

- `JST`
  - `UTC+9` の timezone
  - timestamp を最終ディレクトリ名にする際に使う
- `SCRIPT_DIR`
  - このファイルのあるディレクトリ
- `PROJECT_ROOT`
  - repository root
- `SETTINGS_PATH`
  - `src/util/FeatureExtract/Zeek/settings.json`

## メソッド単位の説明

### `parse_args()`

`argparse` の初期化だけをしている。
今は実質オプションを持たず、`-h/--help` 用と将来拡張用の器である。
`main()` の先頭で呼ばれるが、返り値は使っていない。

### `load_settings()`

`SETTINGS_PATH` の JSON を読む。
ファイルが無ければ `SystemExit` になる。

ここでは JSON の存在確認しかしておらず、中身の schema 検証は次の `resolve_config()` 側で行う。

### `resolve_repo_path()`

パス文字列を絶対 `Path` に変換する。

- 空文字なら即 `SystemExit`
- 絶対パスならそのまま `resolve()`
- 相対パスなら **現在のカレントディレクトリではなく repo root 基準**で解決する

ここは重要な挙動である。

### `resolve_config()`

`settings["PcapToLog"]` を取り出し、`INPUT_DIR_PATH` と `OUTPUT_ROOT_DIR_PATH` を `resolve_repo_path()` に通す。

つまりこのメソッドが、「このスクリプトが何を入力とし、どこに出すか」を確定させる場所である。
`PcapToLog` セクション自体が無ければ失敗する。

### `collect_pcap_files()`

入力ディレクトリ配下を `rglob("*")` で再帰探索し、拡張子が `.pcap` または `.pcapng` の**ファイルだけ**を集めてソートして返す。

注意点は次の 3 つ。

- 入力が単一ファイルでも受けない。必ずディレクトリを要求する
- 拡張子なしの capture file は拾わない。別スクリプト `normalize_pcap_extensions.py` 前提
- 見つからなければ `SystemExit`

### `sanitize_name()`

文字列からディレクトリ名向けの安全な名前を作る。
英数字と `._-` だけを残し、それ以外は `_` に変換する。
前後の `_` を削った結果空なら `"unknown"` を返す。

主な用途は一時ディレクトリ名と、timestamp を取れなかったときの fallback 名である。

### `read_first_ts()`

指定ディレクトリ内の `*.log` を全部見て、各 JSON line の `ts` を拾い、**最小値**を返す。

細かい挙動は次の通り。

- 空行は無視する
- JSON として壊れていれば即 `SystemExit`
- `ts` が無い、空文字、float 化できない場合はその行だけ無視する
- どの `.log` にも有効な `ts` が無ければ `None` を返す

つまり `conn.log` だけを見るのではなく、Zeek が出した全 `.log` を横断して最小 `ts` を使う。

### `ts_to_name()`

`ts` を最終ディレクトリ名へ変換する。

- `ts` がある場合
  - UTC unix timestamp とみなし、JST に変換して `YYYYMMDDHHMMSS` にする
- `ts` が `None` の場合
  - `fallback` を `sanitize_name()` に通して使う

通常 `fallback` は `pcap_file.stem` である。

### `make_unique_dir()`

目的のディレクトリ名が既に存在するとき、`_01`, `_02`, ... を順に試して空きを返す。

ここでは実際には `mkdir` しておらず、**使うべきパス候補を決めるだけ**である。

### `run_zeek()`

Zeek 呼び出し本体である。

実行コマンドは次。

```bash
zeek -r <pcap_file> LogAscii::use_json=T
```

`cwd=output_dir` にしているので、Zeek が生成する `.log` はそのディレクトリ直下に出る。

- `FileNotFoundError`
  - `zeek` コマンド自体が無い
  - `SystemExit` にして止める
- `CalledProcessError`
  - Zeek が非 0 終了した
  - stderr を保持した `ZeekRunError` に包む

### `main()`

処理全体のオーケストレーションである。流れは次の通り。

1. `parse_args()` を呼ぶ
2. `load_settings()` と `resolve_config()` で入出力を確定する
3. `collect_pcap_files()` で対象 PCAP を列挙する
4. `output_root` が file なら失敗、無ければ `mkdir`
5. `batch_dir = output_root / input_path.name` を作る
6. 各 PCAP について `.tmp_0001_<stem>` のような一時ディレクトリを作り、その中で `run_zeek()`
7. Zeek 出力後 `read_first_ts()` で最小 `ts` を取り、`ts_to_name()` で最終ディレクトリ名を決める
8. `make_unique_dir()` で衝突回避したあと、一時ディレクトリを `rename` して完成
9. `ZeekRunError` なら `.tmp_*` を掃除した上で、その PCAP を失敗一覧に追加して続行する
10. その他の失敗時は `.tmp_*` を `shutil.rmtree()` で掃除して再 raise
11. 失敗 PCAP があれば、実行終了時にパスと失敗理由を stderr にまとめて表示する
12. 最後に `"<pcap> -> <final_dir>"` を各件表示し、最後の 1 行で `batch_dir` を表示する

補足:

- `batch_dir` が既にある場合は stderr に warning を出すだけで続行する
- 既存成果物を壊さないため、最終ディレクトリ名は衝突回避される
- 壊れた PCAP に当たっても他の PCAP の処理を継続する

## このファイルの実質的な責務

このファイルは、Zeek の解析内容そのものを保証することが主目的ではない。
責務は次の通りである。

- Zeek をどう呼ぶか
- どの PCAP を対象にするか
- どこにどんな名前で出すか
- 失敗時に中間ゴミを残さないか
- 設定やパスの解決がぶれないか

この意味で、`pcap_to_log_extractor.py` は「薄い wrapper」だが、repository の契約そのものを持っている。

## テスト観点として重要な箇所

- `collect_pcap_files()` の収集条件
- `resolve_repo_path()` の repo root 基準解決
- `read_first_ts()` の最小 `ts` 選択
- `ts_to_name()` の JST 変換と fallback
- `make_unique_dir()` の衝突回避
- `main()` の `.tmp_*` cleanup と最終配置

## 関連ファイル

- `src/util/FeatureExtract/Zeek/pcap_to_log_extractor.py`
- `src/util/FeatureExtract/Zeek/settings.json`
- `src/util/FeatureExtract/Zeek/normalize_pcap_extensions.py`
- `docs/pcapファイルから特徴量を抽出する方法.md`
