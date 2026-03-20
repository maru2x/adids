import os
import pandas as pd
import matplotlib.pyplot as plt
import japanize_matplotlib
from matplotlib.patches import Rectangle
import seaborn as sns

# --- 特定のディレクトリから特定の特徴量についてプロットを行う

drift_dir_path = "/mnt/nas0/g005/murasemaru/exp/1_DataAnalytics/drift/filtered_20220110-20220114/2201UkSouth+2201Lab02"
file_name = "feature_drift"
metrix = "mean_dis"
label_size = 14
legend_size = 16

output_dir_path = os.path.join(drift_dir_path, "res_img")
os.makedirs(output_dir_path, exist_ok=True)  # ループの外で1回だけ実行

# フィルタリングの時間範囲を設定
start_date = "2022-01-12 00:00:00"
end_date = "2022-01-13 00:00:00"

# past
highlight_green_start = "2022-01-12 9:00:00"
highlight_green_end = "2022-01-12 15:00:00"

# current
highlight_yellow_start = "2022-01-12 15:00:00"
highlight_yellow_end = "2022-01-12 19:00:00"

for fi in os.listdir(drift_dir_path):
    if fi.endswith('.csv'):
        fi_path = os.path.join(drift_dir_path, fi)
        print(f"Processing file: {fi_path}")
        
        data = pd.read_csv(fi_path)
        
        # 日付列をdatetime型に変換してフィルタリング
        data['date'] = pd.to_datetime(data['date'])
        filtered_data = data[(data['date'] >= start_date) & (data['date'] <= end_date)]
        
        ex_val = fi.replace("with_population_", "").replace(".csv", "")
        output_path = f"{output_dir_path}/{file_name}_{ex_val}.png"
        kde_output_path = f"{output_dir_path}/{file_name}_kde_{ex_val}.png"

        # --- 時系列プロット
        if not filtered_data.empty:  # フィルタ後にデータが存在する場合のみプロット
            fig, ax = plt.subplots(figsize=(8.56, 4.28))
            ax.plot(filtered_data['date'], filtered_data[metrix], label="データ特性", linewidth=2, color="#377eb8")
            
            # 目盛りを消す
            ax.tick_params(axis='both', which='both', bottom=False, top=False, left=False, right=False, labelleft=False, labelbottom=False)
            ax.set_xlabel("Time", fontsize=label_size, color='black')
            
            # ハイライト部分を追加（背景色）
            ax.axvspan(pd.to_datetime(highlight_yellow_start), pd.to_datetime(highlight_yellow_end), color='#ff7f00', alpha=0.3, label="現在ウィンドウ")
            ax.axvspan(pd.to_datetime(highlight_green_start), pd.to_datetime(highlight_green_end), color='#4daf4a', alpha=0.3, label="過去ウィンドウ")
            
            # 縁取りの位置調整用バッファ
            buffer = 0.003 * (ax.get_ylim()[1] - ax.get_ylim()[0])  # Y軸全体の5%をマージンとする
            
            # ハイライト部分を縁取り（外枠）
            ax.add_patch(Rectangle((pd.to_datetime(highlight_green_start), ax.get_ylim()[0] + buffer), 
                                    pd.to_datetime(highlight_green_end) - pd.to_datetime(highlight_green_start),
                                    ax.get_ylim()[1] - ax.get_ylim()[0] - 2 * buffer,
                                    fill=False, edgecolor='#4daf4a', linewidth=3))
            ax.add_patch(Rectangle((pd.to_datetime(highlight_yellow_start), ax.get_ylim()[0] + buffer), 
                                    pd.to_datetime(highlight_yellow_end) - pd.to_datetime(highlight_yellow_start),
                                    ax.get_ylim()[1] - ax.get_ylim()[0] - 2 * buffer,
                                    fill=False, edgecolor='#ff7f00', linewidth=3))
            
            plt.legend(fontsize=legend_size)
            plt.grid(True)
            
            plt.tight_layout()
            plt.savefig(output_path, dpi=300, format="png")  # 高画質PNGに保存
            plt.close()
        else:
            print(f"No data in the range {start_date} to {end_date} for file: {fi_path}")

        # --- KDEプロット
        past_data = data[(data['date'] >= highlight_green_start) & (data['date'] <= highlight_green_end)]
        current_data = data[(data['date'] >= highlight_yellow_start) & (data['date'] <= highlight_yellow_end)]
        
        if not past_data.empty and not current_data.empty:  # 両ウィンドウにデータが存在する場合のみプロット
            plt.figure(figsize=(2.38, 2.04))
            
            # KDEプロットを作成
            sns.kdeplot(past_data[metrix], color='#357a38', fill=True, alpha=0.5)
            sns.kdeplot(current_data[metrix], color='#cc6600', fill=True, alpha=0.5)
            
            # 軸ラベルと目盛りを完全に削除
            plt.tick_params(axis='both', which='both', bottom=False, top=False, left=False, right=False, labelleft=False, labelbottom=False)
            plt.xlabel("")
            plt.ylabel("")
            
            # グリッドを削除
            plt.grid(False)
            
            # レイアウトを調整して保存
            plt.tight_layout()
            plt.savefig(kde_output_path, dpi=300, format="png")  # KDE用に保存
            plt.close()
        else:
            print(f"Not enough data for KDE plot in file: {fi_path}")
