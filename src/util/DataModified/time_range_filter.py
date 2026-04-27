import os
import pandas as pd
from datetime import datetime

# 設定
input_folder = "/mnt/nas0/g005/murasemaru/data/csv/unproc/2201Lab04"  # 元のCSVフォルダ
time_range_start = "2022-01-17 00:00:00"  # 開始日時（例）
time_range_end = "2022-01-21 00:00:00"    # 終了日時（例）

# フィルタ条件を含む出力フォルダ名
time_range_str = f"{time_range_start[:10].replace('-', '')}-{time_range_end[:10].replace('-', '')}"
input_folder_name = os.path.basename(input_folder)
output_folder = f"/mnt/nas0/g005/murasemaru/data/csv/modif/filtered_{time_range_str}/{input_folder_name}"

rows_per_file = 3000  # 1ファイル当たりの行数

# 日時をdatetime形式に変換
time_range_start = datetime.strptime(time_range_start, "%Y-%m-%d %H:%M:%S")
time_range_end = datetime.strptime(time_range_end, "%Y-%m-%d %H:%M:%S")

# 出力フォルダの作成
os.makedirs(output_folder, exist_ok=True)

# CSVファイルの処理
for csv_file in os.listdir(input_folder):
    if csv_file.endswith(".csv"):
        # CSV読み込み
        file_path = os.path.join(input_folder, csv_file)
        df = pd.read_csv(file_path)

        # daytime列の確認と処理
        if 'daytime' not in df.columns:
            print(f"Skipping {csv_file}: 'daytime' column not found.")
            continue

        df['daytime'] = pd.to_datetime(df['daytime'], errors='coerce')
        df = df.dropna(subset=['daytime'])  # 無効な日時データを削除

        # 時間範囲でフィルタリング
        filtered_df = df[(df['daytime'] >= time_range_start) & (df['daytime'] < time_range_end)]

        # 分割して保存
        for i in range(0, len(filtered_df), rows_per_file):
            chunk = filtered_df.iloc[i:i + rows_per_file]
            if not chunk.empty:
                # 出力ファイル名（元のファイル名を保持）
                output_file = os.path.join(output_folder, f"{csv_file}")
                chunk.to_csv(output_file, index=False, mode='a', header=not os.path.exists(output_file))

print(f"データ処理が完了しました．出力フォルダ: {output_folder}")

