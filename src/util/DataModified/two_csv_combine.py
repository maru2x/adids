import csv
import json
from datetime import datetime
from pathlib import Path


SETTINGS_PATH = Path(__file__).with_name("settings.json")
DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"


def load_settings(settings_path=SETTINGS_PATH):
    # settings.json 全体ではなく、このスクリプト用の Combiner 設定だけを取り出す。
    with Path(settings_path).open("r", encoding="utf-8") as f:
        settings = json.load(f)
    return settings["Combiner"]


def list_csv_files(input_dir):
    # 入力ディレクトリ直下の CSV だけを対象にする。
    # runtime 側と同じく、ここでも再帰探索はしない。
    csv_files = sorted(
        path for path in Path(input_dir).iterdir() if path.is_file() and path.suffix == ".csv"
    )
    if not csv_files:
        raise ValueError(f"No CSV files found in input directory: {input_dir}")
    return csv_files


def parse_daytime(value, source_name):
    # daytime は比較のたびに使うので、最初に datetime へ変換しておく。
    # ここで弾いておくと、後段のマージ処理は「時刻として比較できる値」だけを扱えばよい。
    try:
        return datetime.strptime(value, DATETIME_FORMAT)
    except ValueError as exc:
        raise ValueError(
            f"Invalid daytime value '{value}' in {source_name}. Expected format: {DATETIME_FORMAT}"
        ) from exc


def validate_output_dir(output_dir):
    # 既存出力と今回の出力が混ざると検証しづらいので、
    # 出力先は「空ディレクトリ」または「まだ存在しないディレクトリ」に限定する。
    output_path = Path(output_dir)
    if output_path.exists():
        if any(output_path.iterdir()):
            raise ValueError(f"OUTPUT_DIR must be empty before running: {output_dir}")
    else:
        output_path.mkdir(parents=True, exist_ok=True)
    return output_path


class CsvSequence:
    def __init__(self, csv_files):
        # csv_files は「まだ開いていない CSV ファイルの並び」であり、
        # ここではまずイテレータ化だけしておく。
        self.csv_files = iter(csv_files)
        # expected_header は、この系列で最初に見つかったヘッダを覚えるためのもの。
        # 2個目以降の CSV は、これと一致しなければならない。
        self.expected_header = None
        # current_file / current_path / reader は「今まさに読んでいる CSV」を指す。
        self.current_file = None
        self.current_path = None
        self.reader = None
        # current_row は「次に取り出される予定の 1 行」。
        # current_dt は、その current_row["daytime"] を datetime 化したもの。
        self.current_row = None
        self.current_dt = None
        self.header = None
        # ended は「この系列を最後まで読み切ったか」を表す。
        # 片側が終わったあとのマージ分岐で使う。
        self.ended = False
        try:
            # 初期化直後に 1 行目まで進めておく。
            # こうしておくと、呼び出し側はすぐ current_row/current_dt を比較できる。
            self.advance()
        except Exception:
            self.close()
            raise

    def close(self):
        # 現在開いているファイルがあれば閉じる。
        # 複数ファイルを順に読むが、同時に開くのは常に 1 ファイルだけにする。
        if self.current_file is not None:
            self.current_file.close()
            self.current_file = None
            self.reader = None
            self.current_path = None

    def _open_next_file(self):
        # 次の CSV を開く前に、今の CSV は確実に閉じる。
        self.close()
        while True:
            try:
                next_path = next(self.csv_files)
            except StopIteration:
                # もう開ける CSV がなければ、この系列は完全終了。
                self.ended = True
                self.header = self.expected_header
                return False

            # DictReader を使うことで、1 行ずつ dict として読む。
            # ここでは全件をメモリに載せず、必要になったときだけ next(reader) する。
            current_file = next_path.open("r", encoding="utf-8", newline="")
            reader = csv.DictReader(current_file)
            fieldnames = reader.fieldnames
            if not fieldnames or "daytime" not in fieldnames:
                current_file.close()
                raise ValueError(f"Missing 'daytime' column in {next_path}")
            if self.expected_header is None:
                # この系列で最初に見た CSV のヘッダを基準として保存する。
                self.expected_header = list(fieldnames)
            elif list(fieldnames) != self.expected_header:
                # 同じ入力ディレクトリの中で列構成が揃っていない場合は、
                # 後続処理が安全にできないので明示的に止める。
                current_file.close()
                raise ValueError(
                    f"CSV header mismatch in {next_path}. Expected {self.expected_header}, got {list(fieldnames)}"
                )

            # 今後はこの CSV から 1 行ずつ読む。
            self.current_file = current_file
            self.current_path = next_path
            self.reader = reader
            self.header = self.expected_header
            return True

    def advance(self):
        while True:
            # まだ reader が無い場合は、次に読むべき CSV を開く。
            # _open_next_file() が False を返したら、この系列は完全終了している。
            if self.reader is None and not self._open_next_file():
                self.current_row = None
                self.current_dt = None
                return
            try:
                # DictReader はイテレータなので、ここで 1 行だけ読む。
                row = next(self.reader)
            except StopIteration:
                # この CSV のデータ行を読み切った。
                # reader を空にして continue することで、次の CSV へ進む。
                self.reader = None
                continue

            # ここに来た時点で、row は「実データを持つ 1 行」である。
            # header-only CSV は StopIteration で流れているので、ここには残らない。
            self.current_row = row
            self.current_dt = parse_daytime(row["daytime"], self.current_path.name)
            self.ended = False
            return

    def pop_current(self):
        # current_row は「まだ消費していない先頭 1 行」なので、
        # それを返した直後に advance() で次の 1 行へ進める。
        if self.ended or self.current_row is None:
            raise StopIteration("No current row available.")
        row = dict(self.current_row)
        self.advance()
        return row


def output_filename(output_index, first_daytime):
    # ファイル名には連番と先頭行の時刻を入れる。
    # どの時間帯の chunk かを後から追いやすくするため。
    return f"{output_index:05d}_{first_daytime.strftime('%Y%m%d%H%M')}.csv"


def flush_rows(output_dir, fieldnames, rows, output_index):
    # rows は「まだ書き出していない行バッファ」。
    # 空なら何もせず、そのまま連番だけ返す。
    if not rows:
        return output_index
    # chunk の代表時刻として、先頭行の daytime をファイル名に使う。
    first_daytime = parse_daytime(rows[0]["daytime"], "combined output")
    output_path = Path(output_dir) / output_filename(output_index, first_daytime)
    with output_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    # ここで clear() して同じリストを空に戻す。
    # 新しいバッファを作り直すのではなく、既存の未出力バッファを再利用する。
    rows.clear()
    return output_index + 1


def combine_csv_directories(input_dir_a, input_dir_b, output_dir, chunk_size):
    # chunk_size は「1 出力ファイルあたり最大何行まで持つか」。
    # 0 以下だと分割単位として意味を持たないので止める。
    if chunk_size <= 0:
        raise ValueError(f"CHUNK_SIZE must be a positive integer: {chunk_size}")

    # A 側 / B 側の CSV 群を列挙する。
    csv_files_a = list_csv_files(input_dir_a)
    csv_files_b = list_csv_files(input_dir_b)
    # 出力先は空ディレクトリであることを確認する。
    output_path = validate_output_dir(output_dir)

    seq_a = None
    seq_b = None
    try:
        # 各入力ディレクトリを「1 本の連続した行系列」として扱う。
        seq_a = CsvSequence(csv_files_a)
        seq_b = CsvSequence(csv_files_b)

        # header が None のままということは、CSV はあっても実データ行に到達できていない。
        if seq_a.header is None or seq_b.header is None:
            raise ValueError("Input directories must contain at least one data row.")
        # current_row が無い場合も同様に、実データ 0 件として扱う。
        if seq_a.current_row is None or seq_b.current_row is None:
            raise ValueError("Input directories must contain at least one data row.")
        # A 側と B 側で列構成が違うものは、そのまま結合してはいけない。
        if seq_a.header != seq_b.header:
            raise ValueError(
                f"CSV header mismatch between directories. A={seq_a.header}, B={seq_b.header}"
            )

        # combined_rows は「まだ出力ファイルに書いていない行」を溜めるバッファ。
        # 今回の修正で一番重要なのは、このバッファを途中で捨てないこと。
        combined_rows = []
        output_index = 0

        while not (seq_a.ended and seq_b.ended):
            # 基本方針は「今見えている 2 行のうち、早い方を 1 行だけ採用する」。
            # 片側が終わっている場合は、残っている側をそのまま流し切る。
            #
            # ここで重要なのは、片側終了時でも combined_rows を作り直さないこと。
            # 以前の不具合は、未出力バッファを新しい 1 行で上書きしていた点にあった。
            if seq_a.ended:
                combined_rows.append(seq_b.pop_current())
            elif seq_b.ended:
                combined_rows.append(seq_a.pop_current())
            elif seq_a.current_dt <= seq_b.current_dt:
                combined_rows.append(seq_a.pop_current())
            else:
                combined_rows.append(seq_b.pop_current())

            # バッファが chunk_size に達したら、その時点で 1 ファイルとして書き出す。
            # これにより、巨大データでもメモリ使用量は chunk_size にほぼ抑えられる。
            if len(combined_rows) >= chunk_size:
                output_index = flush_rows(output_path, seq_a.header, combined_rows, output_index)

        # ループを抜けた時点で、端数の行が残っていれば最後に書き出す。
        flush_rows(output_path, seq_a.header, combined_rows, output_index)
    finally:
        # 途中で失敗してもファイルハンドルを閉じる。
        if seq_a is not None:
            seq_a.close()
        if seq_b is not None:
            seq_b.close()


def main():
    # スクリプト単体実行時は settings.json を読む。
    # テストでは combine_csv_directories() を直接呼び出す。
    settings = load_settings()
    combine_csv_directories(
        input_dir_a=settings["INPUT_DIR_A"],
        input_dir_b=settings["INPUT_DIR_B"],
        output_dir=settings["OUTPUT_DIR"],
        chunk_size=settings["CHUNK_SIZE"],
    )
    print("csv combine complete")


if __name__ == "__main__":
    main()
