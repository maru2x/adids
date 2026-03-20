import os
import csv
import shutil
from datetime import datetime, timedelta
from itertools import cycle
# --- 対象のデータセットに1対1の割合で，特定のデータセットを混入させる．
# --- 設定 ----------------------------------------------------------------------- #
target_dir_path: str = "data/csv/unproc/2202Lab04"
source_dir_path: str = "data/csv/unproc/2201JpnEast"
output_dir_path: str = f"data/csv/modif/{os.path.basename(target_dir_path)}+1"
# -------------------------------------------------------------------------------- #
# CSVファイルのリストを取得
t_csv_files = [f for f in sorted(os.listdir(target_dir_path)) if f.endswith('.csv')]
s_csv_files = [f for f in sorted(os.listdir(source_dir_path)) if f.endswith('.csv')]
# source_dir_pathから1時間分のデータを抽出 -> first_hour_data
s_row_list = []
first_time = None
for s_csv_file in s_csv_files:
    s_file_path: str = os.path.join(source_dir_path, s_csv_file)
    with open(s_file_path, mode="r") as s_row_iter:
        s_reader = csv.reader(s_row_iter)
        s_header = next(s_reader)
        s_ts_index = s_header.index("daytime")
        while True:
            try:
                s_row = next(s_reader)
                s_row_ts = datetime.strptime(s_row[s_ts_index], "%Y-%m-%d %H:%M:%S")
                if first_time is None:
                    first_time = s_row_ts
                if not s_row_ts < first_time + timedelta(hours=1):
                    break
                else:
                    s_row_list.append(s_row)
            except StopIteration:
                break
s_row_cycle = cycle(s_row_list)
# 出力ディレクトリを準備
if os.path.exists(output_dir_path):
    print("delete dir")
    shutil.rmtree(output_dir_path)
os.makedirs(output_dir_path, exist_ok=True)
# CSVファイルを逐次処理
total_files = len(t_csv_files)
for count, t_csv_file in enumerate(t_csv_files, start=1):
    t_file_path = os.path.join(target_dir_path, t_csv_file)
    output_file_path = os.path.join(output_dir_path, t_csv_file)
    with open(t_file_path, mode="r") as t_file, open(output_file_path, mode="w", newline="") as output_file:
        t_reader = csv.reader(t_file)
        t_header = next(t_reader)
        daytime_index = t_header.index("daytime")
        writer = csv.writer(output_file)
        writer.writerow(t_header)  # ヘッダーを書き込む
        for t_row in t_reader:
            s_row = next(s_row_cycle)
            # `s_row` のデータを加工して `t_row` に適応
            t_new_row = t_row[:]  # `t_row`をコピー
            s_new_row = s_row[:]
            s_new_row[daytime_index] = t_row[daytime_index]
            # デバッグ用の出力
            # print("t_new_row:", t_new_row)
            # print("s_new_row:", s_new_row)
            # 出力
            writer.writerow(t_new_row)
            writer.writerow(s_new_row)
    print(f"{count}/{total_files} : {t_csv_file} complete")
print("処理が完了しました")