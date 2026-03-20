import os

import pandas as pd
import matplotlib.pyplot as plt

# --- 指定した親ディレクトリに含まれるサブディレクトリの結果をサブディレクトリごとにグラフにまとめて出力
# -------------------------------------------------------------------------------#
all_dir_path = "/mnt/nas0/g005/murasemaru/exp/5_Eval/20220110-20220114_UsEast/fm"
file_name = "eval_metrixes"
metrix = ["f1_score"]
label_size = 22
ticks_size = 16
legend_size = 22

for di in os.listdir(all_dir_path):
    di_path = f"{all_dir_path}/{di}"
    output_dir_path = os.path.join(os.path.dirname(di_path), "res_img")
    os.makedirs(output_dir_path, exist_ok=True)  # ループの外で1回だけ実行

    fi=os.path.join(di_path,"eval_res.csv")
    fi_path = os.path.join(di_path, fi)
    print(f"Processing file: {fi_path}")
    
    data = pd.read_csv(fi_path)
    output_path = f"{output_dir_path}/{file_name}_{di}.png"
    
    data['daytime'] = pd.to_datetime(data['daytime'])
    plt.figure(figsize=(12, 8))
    for y in metrix:
        plt.plot(data['daytime'], data[y], label=y, linewidth=2)
    
    plt.xlabel('daytime', fontsize=label_size)
    
    plt.xticks(fontsize=ticks_size, rotation=45)
    plt.yticks(fontsize=ticks_size)
    
    plt.legend(fontsize=legend_size)
    plt.grid(True)
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=300)
    plt.close()
