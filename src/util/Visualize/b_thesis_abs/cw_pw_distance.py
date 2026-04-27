import os
import pandas as pd
import japanize_matplotlib
import matplotlib.pyplot as plt
from datetime import timedelta,datetime

dir_path = "/mnt/nas0/g005/murasemaru/exp/2_DriftDetection/euc_k32/c600p3600"
metrix = "math"
th1 = 0.1
th2 = 0.05
start_time = '2022-01-10 15:00:00'

output_dir = f"{dir_path}/res_img"
os.makedirs(output_dir, exist_ok=True)

label_size = 26
ticks_size = 20
legend_size = 30

file_path = os.path.join(dir_path, 'dd_res.csv')
if not os.path.exists(file_path):  # ファイルが存在しない場合はスキップ
    print(f"File not found: {file_path}. Skipping.")
else:
    df = pd.read_csv(file_path)
    df['date'] = pd.to_datetime(df['date'])
    # 経過時間の計算（時間単位）
    start_time = datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S')
    df['elapsed_hours'] = (df['date'] - start_time).dt.total_seconds() / 3600  # 経過時間を時間単位に変換
    
    plt.figure(figsize=(14, 6))
    plt.plot(df['elapsed_hours'], df[metrix], label="ウィンドウ間距離", linewidth=3, alpha=0.8, color='tab:orange')
    
    # y=0.01に破線を追加
    plt.axhline(y=th1, color='tab:green', linestyle='--', linewidth=3, label="閾値0.1")
    plt.axhline(y=th2, color='tab:purple', linestyle='--', linewidth=3, label="閾値0.05")

    plt.xlim(12, 52)  # 描画範囲を固定
    plt.xticks(fontsize=ticks_size)
    plt.yticks(fontsize=ticks_size)
    plt.xlabel("Elapsed time[h]", fontsize=label_size)
    plt.legend(fontsize=legend_size)
    plt.grid(True)
    plt.tight_layout()
    
    # ファイルに保存
    output_path = os.path.join(output_dir, f"CwPwDistance.png")
    plt.savefig(output_path, dpi=500)
    plt.show()
