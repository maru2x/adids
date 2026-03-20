import csv
import os
from datetime import datetime
import pandas as pd
# --- 二つのデータセットを時系列順に結合するスクリプト ------------------------------------------------------------------------ #
d1_folder_path: str = "/mnt/nas0/g005/murasemaru/data/csv/modif/filtered_20220110-20220114/2201UkSouth"
d2_folder_path: str = "/mnt/nas0/g005/murasemaru/data/csv/modif/filtered_20220110-20220114/2201Lab02"
dataset_size = 3000
# --- Create output directory
output_dir_path: str = f"/mnt/nas0/g005/murasemaru/data/csv/modif/filtered_20220110-20220114/{os.path.basename(d1_folder_path)}+{os.path.basename(d2_folder_path)}"
# ------------------------------------------------------------------------------------------------------------------------- #
combined_row_count = 0
output_file_count = 0
d1_iter = iter(sorted(os.listdir(d1_folder_path)))
d1_file_path: str = f"{d1_folder_path}/{next(d1_iter)}"
d1 = open(d1_file_path, mode='r')
d1_reader = csv.reader(d1)
d1_header = next(d1_reader)
d1_ts_index = d1_header.index("daytime")
d1_row = next(d1_reader)
d1_latest = datetime.strptime(d1_row[d1_ts_index], "%Y-%m-%d %H:%M:%S")
d1_end_flag = False
d2_iter = iter(sorted(os.listdir(d2_folder_path)))
d2_file_path: str = f"{d2_folder_path}/{next(d2_iter)}"
d2 = open(d2_file_path, mode='r')
d2_reader = csv.reader(d2)
d2_header = next(d2_reader)
d2_ts_index = d2_header.index("daytime")
d2_row = next(d2_reader)
d2_latest = datetime.strptime(d2_row[d2_ts_index], "%Y-%m-%d %H:%M:%S")
d2_end_flag = False
if d1_latest < d2_latest:
    print("d1")
    print(d1_latest)
    print(d2_latest)
    combined_list = [d1_row]
    d1_row = next(d1_reader)
else:
    print("d2")
    print(d1_latest)
    print(d2_latest)
    combined_list = [d2_row]
    d2_row = next(d2_reader)
os.makedirs(output_dir_path)
while True:
    if d1_end_flag and d2_end_flag:
        combined_df = pd.DataFrame(combined_list)
        combined_df.to_csv(f"{output_dir_path}/{output_file_count:05d}.csv", index=False, header=d1_header)
        break
    elif d1_latest <= d2_latest:
        combined_row_count += 1
        if combined_row_count > dataset_size:
            print(f"output {output_file_count}")
            output_file_count += 1
            combined_df = pd.DataFrame(combined_list)
            date_obj = datetime.strptime(combined_list[0][d1_ts_index], "%Y-%m-%d %H:%M:%S")
            formatted_date = date_obj.strftime("%Y%m%d%H%M")
            combined_df.to_csv(f"{output_dir_path}/{output_file_count:05d}_{formatted_date}.csv", index=False,
                               header=d1_header)
            combined_list = [d1_row]
            combined_row_count = 0
        else:
            combined_list.append(d1_row)
        try:
            d1_row = next(d1_reader)
            d1_latest = datetime.strptime(d1_row[d1_ts_index], "%Y-%m-%d %H:%M:%S")
        except StopIteration: # 次の行がないとき
            d1.close()
            try:
                d1_file_path: str = f"{d1_folder_path}/{next(d1_iter)}"
                d1 = open(d1_file_path, mode='r')
                d1_reader = csv.reader(d1)
                d1_header = next(d1_reader)
                d1_row = next(d1_reader)
                d1_latest = datetime.strptime(d1_row[d1_ts_index], "%Y-%m-%d %H:%M:%S")
            except StopIteration: # 次のファイルがないとき
                combined_list = [d2_row]
                d1_end_flag = True
    else:
        combined_row_count += 1
        if combined_row_count > dataset_size:
            print(f"output {output_file_count}")
            output_file_count += 1
            combined_df = pd.DataFrame(combined_list)
            date_obj = datetime.strptime(combined_list[0][d2_ts_index], "%Y-%m-%d %H:%M:%S")
            formatted_date = date_obj.strftime("%Y%m%d%H%M")
            combined_df.to_csv(f"{output_dir_path}/{output_file_count:05d}_{formatted_date}.csv", index=False, header=d1_header)
            combined_list = [d2_row]
            combined_row_count = 0
        else:
            combined_list.append(d2_row)
        try:
            d2_row = next(d2_reader)
            d2_latest = datetime.strptime(d2_row[d2_ts_index], "%Y-%m-%d %H:%M:%S")
        except StopIteration: # 次の行がないとき
            d2.close()
            try:
                d2_file_path: str = f"{d2_folder_path}/{next(d2_iter)}"
                d2 = open(d2_file_path, mode='r')
                d2_reader = csv.reader(d2)
                d2_header = next(d2_reader)
                d2_row = next(d2_reader)
                d2_latest = datetime.strptime(d2_row[d2_ts_index], "%Y-%m-%d %H:%M:%S")
            except StopIteration: # 次のファイルがないとき
                combined_list = [d1_row]
                d2_end_flag = True