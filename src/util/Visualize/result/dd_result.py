import os
import pandas as pd
import matplotlib.pyplot as plt

# Drift Detection (mode obs)の結果を比較
all_dir_path = "/mnt/nas0/g005/murasemaru/exp/2_DriftDetection/euc_k32/target"
metrix = "math"

output_dir = f"{all_dir_path}/res_img"
os.makedirs(output_dir, exist_ok=True)

label_size = 22
ticks_size = 16
legend_size = 22


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
    
    if not df.empty:
        print(df)
        plt.figure(figsize=(18, 6))
        plt.plot(df['date'], df[metrix], label=metrix, linewidth=1.5, alpha=0.8)
        plt.xticks(fontsize=ticks_size)
        plt.yticks(fontsize=ticks_size)
        plt.title(f"DD:{di}",fontsize=label_size)
        plt.grid(True)
        plt.tight_layout()
    
        # ファイルに保存
        output_path = os.path.join(output_dir, f"{os.path.basename(di)}.png")
        plt.savefig(output_path, dpi=300)
        plt.show()
    else:
        print("No data available for plotting.")

    df = None
