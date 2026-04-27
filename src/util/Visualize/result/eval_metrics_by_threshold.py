import pandas as pd
import os
import matplotlib.pyplot as plt

# --- Window Size ごとの各指標の変化
all_dir_path = "/mnt/nas0/g005/murasemaru/exp/5_Eval/20220110-20220114_UsEast"
target = "th0.99"
metrix = "f1_score"
label_size = 22
ticks_size = 16
legend_size = 22
first_reading_flag = True

dfs = pd.DataFrame()  # 空のDataFrameで初期化
for di in os.listdir(all_dir_path):
    print(di)
    window_size = di
    file_path = f"{all_dir_path}/{di}/{target}/eval_res.csv"
    df = pd.read_csv(file_path)
        # daytimeをdatetime型に変換
    df['daytime'] = pd.to_datetime(df['daytime'])
    
    # metrix の列名を `di` に基づいて変更
    new_column_name = f"{di}_{metrix}"  # 新しい列名を作成
    df = df.rename(columns={metrix: new_column_name})  # 列名を変更
    
    # 必要な列のみ抽出
    selected_columns = ['daytime', new_column_name]
    df = df[selected_columns]
    
    # DataFrameを結合
    if dfs.empty:
        dfs = df
    else:
        dfs = pd.concat([dfs, df], ignore_index=True)
    
print(dfs)

# 保存ディレクトリの作成
output_dir_path = os.path.join(all_dir_path, "res_img")
os.makedirs(output_dir_path, exist_ok=True)  # ループの外で1回だけ実行

# プロットの設定
plt.figure(figsize=(12, 8))

# 各列をプロット
for column in dfs.columns:
    if column != "daytime":  # daytime列はX軸に使用するため除外
        plt.plot(dfs["daytime"], dfs[column], label=column)

# グラフの詳細設定
plt.xlabel("Daytime", fontsize=14)
plt.ylabel(metrix, fontsize=14)
plt.xticks(rotation=45, fontsize=10)
plt.yticks(fontsize=10)
plt.legend(fontsize=10, title=metrix)
plt.grid(True)

# グラフの保存
output_plot_path = f"{output_dir_path}/wsize_compare_{target}_{metrix}.png"
plt.savefig(output_plot_path, dpi=300)
plt.show()
print(f"グラフを保存しました: {output_plot_path}")