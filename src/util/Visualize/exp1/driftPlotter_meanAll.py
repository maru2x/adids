import os

import pandas as pd
import matplotlib.pyplot as plt

# --- 指定した親ディレクトリに含まれるサブディレクトリのmean_disをサブディレクトリごとにグラフにまとめて出力
# -------------------------------------------------------------------------------#
all_dir_path = "/mnt/nas0/g005/murasemaru/exp/1_DataAnalytics/drift/unproc/2201HP"
metrix = "mean_dis"
label_size = 22
ticks_size = 16
legend_size = 26

wnds = [0.5,1,4,8,16,32,64]

# 出力ディレクトリを設定
output_dir_path = os.path.join(all_dir_path, "res_img")
os.makedirs(output_dir_path, exist_ok=True)

for wnd in sorted(wnds):
    plt.figure(figsize=(12, 8))
    # 各ディレクトリのデータを同じプロットに追加
    for di in sorted(os.listdir(all_dir_path)):
        di_path = f"{all_dir_path}/{di}"
        fi = os.path.join(di_path, f"tsa_{wnd}H.csv")
        fi_path = os.path.join(di_path, fi)
    
        if os.path.exists(fi_path):  # eval_res.csv が存在する場合のみ処理
            print(f"Processing file: {fi_path}")
            
            data = pd.read_csv(fi_path)
            data['date'] = pd.to_datetime(data['date'])
    
            # 各ディレクトリごとに異なる色でプロット
            plt.plot(data['date'], data[metrix], label=f"{di}", linewidth=2)
    
    # グラフの装飾
    # plt.ylabel(f"{metrix}", fontsize=label_size)
    plt.xticks(fontsize=ticks_size, rotation=30)
    plt.yticks(fontsize=ticks_size)
    plt.legend(fontsize=legend_size)
    plt.grid(True)
    
    # 出力
    plt.tight_layout()
    output_path = f"{output_dir_path}/{metrix}_{wnd}H.png"
    plt.savefig(output_path, dpi=500)
    plt.close()
    
    print(f"Combined graph saved at: {output_path}")

