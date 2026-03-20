import os
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime

# Drift Detection (mode obs)の結果を比較
all_dir_path = "/mnt/nas0/g005/murasemaru/exp/2_DriftDetection/euc_k32"
metrix = "math"
start_date = '2022-01-10 15:00:00'
label_size = 22
ticks_size = 16
legend_size = 28
# ------------------------------------------------------------------------- #


output_dir = f"{all_dir_path}/bth_res_img"
start_date = datetime.strptime(start_date, '%Y-%m-%d %H:%M:%S')
os.makedirs(output_dir, exist_ok=True)

# データの読み込みと統合
for di in sorted(os.listdir(all_dir_path)):
    # データの読み込みと統合
    file_path = os.path.join(all_dir_path, di, 'dd_res.csv')
    if not os.path.exists(file_path):  # ファイルが存在しない場合はスキップ
        print(f"File not found: {file_path}. Skipping.")
        continue
    
    df = pd.read_csv(file_path)
    df['date'] = pd.to_datetime(df['date'])
    
    print(df)
    df['elapsed_hours'] = (df['date'] - start_date).dt.total_seconds() / 3600
    
    if not df.empty:
        print(df)
        plt.figure(figsize=(18, 6))
        plt.plot(df['elapsed_hours'], df[metrix], label=metrix, linewidth=1.5, alpha=0.8)
        plt.xlim(12, 52)  # 描画範囲を固定
        plt.xticks(fontsize=ticks_size)
        plt.yticks(fontsize=ticks_size)
        plt.xlabel("Elapsed time[h]",fontsize=label_size)
        plt.grid(True)
        plt.tight_layout()
    
        # ファイルに保存
        output_path = os.path.join(output_dir, f"{os.path.basename(di)}.png")
        plt.savefig(output_path, dpi=300)
        plt.show()
    else:
        print("No data available for plotting.")

    df = None
