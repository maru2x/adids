import os
import pandas as pd
import japanize_matplotlib
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

# --- 入力パスと設定
drift_dir_path1 = "/mnt/nas0/g005/murasemaru/exp/1_DataAnalytics/drift/filtered_22020110-22020114/2201HP/2201UkSouth"
drift_dir_path2 = "/mnt/nas0/g005/murasemaru/exp/1_DataAnalytics/drift/filtered_22020110-22020114/2201Lab02"

file_name = "data_drift"
metrix = "mean_dis"
label_size = 26
ticks_size = 20
legend_size = 30

common_path = os.path.commonpath([drift_dir_path1, drift_dir_path2])

# ハイライト窓の設定
highlight_start_1 = pd.Timestamp("2022-01-10 15:00:00")
highlight_end_1 = pd.Timestamp("2022-01-11 03:00:00")
highlight_start_2 = pd.Timestamp("2022-01-11 03:00:00")
highlight_end_2 = pd.Timestamp("2022-01-12 21:00:00")

# グラフの描画範囲設定
plot_start = pd.Timestamp("2022-01-10 15:00:00")
plot_end = pd.Timestamp("2022-01-12 21:00:00")

# 出力ディレクトリ
output_dir_path = os.path.join(common_path, "res_img")
os.makedirs(output_dir_path, exist_ok=True)

# ファイル処理
files1 = {fi for fi in os.listdir(drift_dir_path1) if fi.endswith('.csv')}
files2 = {fi for fi in os.listdir(drift_dir_path2) if fi.endswith('.csv')}
common_files = files1 & files2

for fi in common_files:
    fi_path1 = os.path.join(drift_dir_path1, fi)
    fi_path2 = os.path.join(drift_dir_path2, fi)
    print(f"Processing file: {fi_path1}, {fi_path2}")

    df1 = pd.read_csv(fi_path1)
    df2 = pd.read_csv(fi_path2)

    # 日付列をdatetime型に変換し、経過時間を計算
    df1['date'] = pd.to_datetime(df1['date'])
    df1['elapsed_time'] = (df1['date'] - plot_start).dt.total_seconds() / 3600

    df2['date'] = pd.to_datetime(df2['date'])
    df2['elapsed_time'] = (df2['date'] - plot_start).dt.total_seconds() / 3600

    # グラフ描画範囲でフィルタリング
    filtered_df1 = df1[(df1['date'] >= plot_start) & (df1['date'] <= plot_end)]
    filtered_df2 = df2[(df2['date'] >= plot_start) & (df2['date'] <= plot_end)]

    # グラフ描画
    plt.figure(figsize=(14, 6))
    plt.xlim(0, 52)

    
    plt.plot(filtered_df2['elapsed_time'], filtered_df2[metrix], label="良性トラヒック", linewidth=2,color='blue')
    plt.plot(filtered_df1['elapsed_time'], filtered_df1[metrix], label="悪性トラヒック", linewidth=2,color='red')
    # ハイライト窓の追加
    ax = plt.gca()  # 現在の軸を取得
    ylim = ax.get_ylim()  # Y軸の範囲を取得

    ax.add_patch(Rectangle(
        ((highlight_start_1 - plot_start).total_seconds() / 3600, ylim[0]),  # 開始位置
        (highlight_end_1 - highlight_start_1).total_seconds() / 3600,  # 幅
        ylim[1] - ylim[0],  # 高さ
        color='tab:gray', alpha=0.3, label="初期モデルの学習範囲", edgecolor='#A9A9A9'
    ))

    ax.add_patch(Rectangle(
        ((highlight_start_2 - plot_start).total_seconds() / 3600, ylim[0]),  # 開始位置
        (highlight_end_2 - highlight_start_2).total_seconds() / 3600,  # 幅
        ylim[1] - ylim[0],  # 高さ
        color='tab:purple', alpha=0.3, label="評価範囲", edgecolor='#778899'
    ))

    # グラフのラベル設定
    plt.xlabel('Elapsed time [h]', fontsize=label_size)
    plt.xticks(fontsize=ticks_size)
    plt.yticks(fontsize=ticks_size)
    plt.legend(loc='upper left', fontsize=legend_size)
    plt.grid(True)

    # 出力
    output_path = os.path.join(output_dir_path, f"{file_name}_{fi.replace('tsa_', '').replace('.csv', '')}.png")
    plt.tight_layout()
    plt.savefig(output_path, dpi=750, format='png')
    plt.close()

