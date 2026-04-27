import os

import pandas as pd
import matplotlib.pyplot as plt

all_dir_path = "/mnt/nas0/g005/murasemaru/exp/5_Eval/20220110-20220114_UsEast/dy/dnn_e30b10/e30b10/c2400p7200"
metrix = "f1_score"
label_size = 22
ticks_size = 16
legend_size = 22
file_name = f"compare_{metrix}"

# 出力ディレクトリを設定
output_dir_path = os.path.join(all_dir_path, "res_img")
os.makedirs(output_dir_path, exist_ok=True)

# 全てのグラフを1つの図にまとめる
plt.figure(figsize=(12, 8))
plt.title(f"{os.path.basename(all_dir_path)}:{metrix}")

# 各ディレクトリのデータを同じプロットに追加
for di in os.listdir(all_dir_path):
    di_path = f"{all_dir_path}/{di}"
    fi = os.path.join(di_path, "eval_res.csv")
    fi_path = os.path.join(di_path, fi)

    if os.path.exists(fi_path):  # eval_res.csv が存在する場合のみ処理
        print(f"Processing file: {fi_path}")
        
        data = pd.read_csv(fi_path)
        data['daytime'] = pd.to_datetime(data['daytime'])

        # 各ディレクトリごとに異なる色でプロット
        plt.plot(data['daytime'], data[metrix], label=f"{di}", linewidth=2)

# グラフの装飾
plt.xlabel('daytime', fontsize=label_size)
plt.ylabel(f"{metrix}", fontsize=label_size)
plt.xticks(fontsize=ticks_size, rotation=45)
plt.yticks(fontsize=ticks_size)
plt.legend(fontsize=legend_size)
plt.grid(True)

# 出力
plt.tight_layout()
output_path = f"{output_dir_path}/{file_name}.png"
plt.savefig(output_path, dpi=300)
plt.close()

print(f"Combined graph saved at: {output_path}")
