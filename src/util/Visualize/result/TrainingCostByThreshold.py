import pandas as pd
import os
import matplotlib.pyplot as plt

# --- 基本設定
window_dir_path = "/mnt/nas0/g005/murasemaru/exp/5_Eval/20220110-20220114_UsEast/dy/dnn/cos/e30b10/c1800/p3600"  # ウィンドウディレクトリを指定
metrix = "flow_num"  # 対象列名
output_dir_path = os.path.join(window_dir_path, "res_img")
os.makedirs(output_dir_path, exist_ok=True)  # 保存ディレクトリを作成

# 閾値のディレクトリ一覧を取得
threshold_dirs = [d for d in os.listdir(window_dir_path) if os.path.isdir(os.path.join(window_dir_path, d))]

# データフレームを初期化
dfs = pd.DataFrame()

# 各thresholdフォルダからデータを読み込み
for threshold in threshold_dirs:
    file_path = os.path.join(window_dir_path, threshold, "tr_res.csv")
    
    if not os.path.exists(file_path):
        print(f"ファイルが見つかりません: {file_path}")
        continue

    # データ読み込み
    df = pd.read_csv(file_path)
    df['daytime'] = pd.to_datetime(df['daytime'])  # 日時列をdatetime型に変換

    # 列名をthresholdで識別可能に変更
    new_column_name = f"{threshold}_{metrix}"
    df = df.rename(columns={metrix: new_column_name})
    selected_columns = ['daytime', new_column_name]
    df = df[selected_columns]

    # データフレームを結合
    if dfs.empty:
        dfs = df
    else:
        dfs = pd.merge(dfs, df, on="daytime", how="outer")

# --- プロット
plt.figure(figsize=(12, 8))
for column in dfs.columns:
    if column != "daytime":
        plt.plot(dfs["daytime"], dfs[column], label=column.split('_')[0])  # threshold名を凡例に表示

# グラフ設定
plt.title("Comparison of Training Cost by Threshold", fontsize=16)
plt.xlabel("Daytime", fontsize=14)
plt.ylabel(f"Training Cost ({metrix})", fontsize=14)
plt.xticks(rotation=45, fontsize=10)
plt.yticks(fontsize=10)
plt.legend(fontsize=10, title="Threshold")
plt.grid(True)

# グラフ保存
output_plot_path = os.path.join(output_dir_path, f"threshold_compare_{metrix}.png")
plt.savefig(output_plot_path, dpi=300)
plt.show()
print(f"グラフを保存しました: {output_plot_path}")
