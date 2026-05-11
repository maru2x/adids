import pandas as pd
import matplotlib.pyplot as plt
import os
import numpy as np
from datetime import datetime
import pytz
from sklearn.preprocessing import MinMaxScaler,StandardScaler
from scipy.stats import wasserstein_distance

# JSTの現在時刻を基にした保存ディレクトリ名
jst = pytz.timezone("Asia/Tokyo")
init_time: str = datetime.now(jst).strftime("%Y%m%d%H%M%S")
directory_path = "data/csv/unproc/2201UkSouth"  # データディレクトリ
output_directory = f"exp/{init_time}_{os.path.basename(directory_path)}_histPlotter"  # 保存先ディレクトリ
csv_output_path = f"{output_directory}/results.csv"
os.makedirs(output_directory, exist_ok=True)

# CSVファイルを読み込む
file_path = "exp/exp1-DriftObservation/terminated/2201UkSouth+0_nt/results_evaluate.csv"  # CSVファイルのパスを指定
data = pd.read_csv(file_path)
metrix = ["f1_score"]
output_path = f"{output_directory}/{','.join(metrix)}.png"
os.makedirs(output_directory, exist_ok=True)

# 時間範囲を指定
before_start_time = "2022-01-17 09:04:05"
before_end_time = "2022-01-18 08:04:05"
after_start_time = "2022-01-18 08:04:05"
after_end_time = "2022-01-19 07:04:05"

# 時間範囲をCSVに出力
time_range_path = f"{output_directory}/time_range.csv"
time_range_data = {
    "Time Range": ["Before Start", "Before End", "After Start", "After End"],
    "Timestamp": [before_start_time, before_end_time, after_start_time, after_end_time]
}
pd.DataFrame(time_range_data).to_csv(time_range_path, index=False)

# ヒストグラム作成対象の特徴量リスト
features = [
    "rcv_packet_count", "snd_packet_count", "tcp_count", "udp_count",
    "most_port", "port_count", "rcv_max_interval", "rcv_min_interval",
    "rcv_max_length", "rcv_min_length", "snd_max_interval", "snd_min_interval",
    "snd_max_length", "snd_min_length"
]

# 空のリストを作成してデータを格納
before_data = []
after_data = []

# スケーラーの初期化
# scaler = MinMaxScaler()
scaler = StandardScaler()

# ディレクトリ内のCSVファイルを処理
for filename in sorted(os.listdir(directory_path)):
    if filename.endswith(".csv"):  # CSVファイルのみ対象
        file_path = os.path.join(directory_path, filename)
        df = pd.read_csv(file_path)  # CSV読み込み
        
        # 日付形式を指定して変換
        try:
            df['daytime'] = pd.to_datetime(df['daytime'], format="%Y-%m-%d %H:%M:%S")
        except ValueError:
            print(f"Invalid datetime format in file: {filename}")
            continue

        # 時間範囲でフィルタリング
        before_filtered = df[(df['daytime'] >= before_start_time) & (df['daytime'] <= before_end_time)]
        after_filtered = df[(df['daytime'] >= after_start_time) & (df['daytime'] <= after_end_time)]

        if not before_filtered.empty:
            before_data.append(before_filtered)
        if not after_filtered.empty:
            after_data.append(after_filtered)

# データの結合
if before_data:
    before_combined_data = pd.concat(before_data, ignore_index=True)
else:
    print("前時間範囲のデータが見つかりません．")
    exit()

if after_data:
    after_combined_data = pd.concat(after_data, ignore_index=True)
else:
    print("後時間範囲のデータが見つかりません．")
    exit()

# データセットを結合してスケーリング
combined_data = pd.concat([before_combined_data, after_combined_data], ignore_index=True)
wasserstein_results = []

# 各特徴量に対して処理を実行
for feature in features:
    if feature not in combined_data.columns:
        print(f"Feature {feature} is not in the dataset, skipping.")
        continue

    # スケーリング
    combined_data[f"scaled_{feature}"] = scaler.fit_transform(combined_data[[feature]])

    # 時間範囲ごとにデータを分割
    scaled_before_data = combined_data[
        (combined_data['daytime'] >= before_start_time) & (combined_data['daytime'] <= before_end_time)]
    scaled_after_data = combined_data[
        (combined_data['daytime'] >= after_start_time) & (combined_data['daytime'] <= after_end_time)]

    # ヒストグラムの最大値を計算してylimを統一
    before_hist, _ = np.histogram(scaled_before_data[f"scaled_{feature}"], bins=100)
    after_hist, _ = np.histogram(scaled_after_data[f"scaled_{feature}"], bins=100)
    max_y = max(before_hist.max(), after_hist.max())  # 最大頻度を取得
    ylim = (0, max_y + 10)  # 少し余裕を持たせる

    # 前時間範囲のヒストグラムを作成
    plt.figure(figsize=(10, 6))
    plt.hist(scaled_before_data[f"scaled_{feature}"], bins=100, color='blue', edgecolor='black')
    plt.ylim(ylim)  # 縦幅を設定
    plt.xlabel(feature)
    plt.ylabel('Frequency')
    plt.title(f'Before Time Range Histogram for {feature}')
    plt.grid(True)
    plt.savefig(os.path.join(output_directory, f"before_{feature}.png"))
    plt.close()

    # 後時間範囲のヒストグラムを作成
    plt.figure(figsize=(10, 6))
    plt.hist(scaled_after_data[f"scaled_{feature}"], bins=100, color='red', edgecolor='black')
    plt.ylim(ylim)  # 縦幅を設定
    plt.xlabel(feature)
    plt.ylabel('Frequency')
    plt.title(f'After Time Range Histogram for {feature}')
    plt.grid(True)
    plt.savefig(os.path.join(output_directory, f"after_{feature}.png"))
    plt.close()

    # Wasserstein距離を計算
    wasserstein_dist = wasserstein_distance(
        scaled_before_data[f"scaled_{feature}"].values,
        scaled_after_data[f"scaled_{feature}"].values
    )
    wasserstein_results.append({"Feature": feature, "Wasserstein Distance": wasserstein_dist})

# 結果をCSVに出力
wasserstein_df = pd.DataFrame(wasserstein_results)
wasserstein_df.to_csv(csv_output_path, index=False)
print(f"Wasserstein distances saved to {csv_output_path}")

label_size = 22
ticks_size = 16
legend_size = 22

# datetime列をdatetime型に変換（必要に応じて）
data['daytime'] = pd.to_datetime(data['daytime'])

# ハイライトしたい時間範囲を指定
b_highlight_start = pd.to_datetime(before_start_time)
b_highlight_end = pd.to_datetime(before_end_time)
a_highlight_start = pd.to_datetime(after_start_time)
a_highlight_end = pd.to_datetime(after_end_time)

# グラフを作成
plt.figure(figsize=(12, 8))  # グラフ全体を少し大きく設定

for y in metrix:
    plt.plot(data['daytime'], data[y], label=y, linewidth=2)

plt.axvspan(b_highlight_start, b_highlight_end, color='yellow', alpha=0.3, label='Before Range')
plt.axvspan(a_highlight_start, a_highlight_end, color='green', alpha=0.3, label='After Range')


# 軸ラベルとタイトルの設定（文字サイズを調整）
plt.xlabel('daytime', fontsize=label_size)
plt.ylabel(",".join(metrix), fontsize=label_size)

# 軸目盛りの文字サイズを調整
plt.xticks(fontsize=ticks_size, rotation=45)  # 横軸ラベルを回転
plt.yticks(fontsize=ticks_size)

# 凡例とグリッドを追加（凡例の文字サイズを調整）
plt.legend(fontsize=legend_size)
plt.grid(True)

# グラフを表示
plt.tight_layout()  # レイアウト調整
plt.savefig(output_path, dpi=300)  # 高解像度で保存
plt.show()
