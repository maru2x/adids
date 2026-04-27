import os
import pandas as pd
import matplotlib.pyplot as plt

drift_dir_path = "/mnt/nas0/g005/murasemaru/exp/1_DataAnalytics/drift/unproc/2201HP"
file_name = "mean_dis"
metrix = ["mean_dis"]
label_size = 22
ticks_size = 16
legend_size = 22

for di in os.listdir(drift_dir_path):
    di_path = f"{drift_dir_path}/{di}"
    output_dir_path = os.path.join(di_path, "res_img")
    os.makedirs(output_dir_path, exist_ok=True)  # ループの外で1回だけ実行

    for fi in os.listdir(di_path):
        if fi.endswith('.csv'):
            fi_path = os.path.join(di_path, fi)
            print(f"Processing file: {fi_path}")

            data = pd.read_csv(fi_path)
            ex_val = fi.replace("tsa_", "").replace(".csv", "")
            output_path = f"{output_dir_path}/{file_name}_{ex_val}.png"

            data['date'] = pd.to_datetime(data['date'])
            plt.figure(figsize=(12, 8))
            for y in metrix:
                plt.plot(data['date'], data[y], label=y, linewidth=2)

            plt.xlabel('date', fontsize=label_size)

            plt.xticks(fontsize=ticks_size, rotation=45)
            plt.yticks(fontsize=ticks_size)

            plt.legend(fontsize=legend_size)
            plt.grid(True)

            plt.tight_layout()
            plt.savefig(output_path, dpi=150, format='png')  # フォーマットをJPEGに変更
            plt.close()
