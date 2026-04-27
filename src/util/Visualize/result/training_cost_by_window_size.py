import pandas as pd
import os
import matplotlib.pyplot as plt

# --- 基本設定
all_dir_path = "/mnt/nas0/g005/murasemaru/exp/5_Eval/20220110-20220114_UsEast/dy/dnn/euc/e30b10/c01200"
target = "th0.1"
output_dir_path = os.path.join(all_dir_path, "res_img")
os.makedirs(output_dir_path, exist_ok=True)
epochs = 30  # 学習エポック数を指定
first_reading_flag = True

# targetに基づき，各ウィンドウサイズにおける対象ファイルを指定
# evalファイルから時間を抽出
# 抽出した時間範囲にそってtrainingファイルのtrainingコストを各時間範囲ごとに計算
# 計算結果を単一のDataFrameに結合
# DataFrameをプロット

# 学習コストを計算する関数
def calculate_training_cost(di, tr_data, eval_times, epochs, window_minutes=30):
    costs = []
    for eval_time in eval_times:
        start_time = eval_time - pd.Timedelta(minutes=window_minutes)
        end_time = eval_time + pd.Timedelta(minutes=window_minutes)
        window_data = tr_data[(tr_data["daytime"] >= start_time) & (tr_data["daytime"] < end_time)]
        if window_data.empty:
            costs.append(0)
        else:
            tr_cost = window_data["flow_num"] * epochs
            costs.append(tr_cost.sum())
    return pd.Series(costs, name=di)

# --- データ処理
dfs = pd.DataFrame()

for di in sorted(os.listdir(all_dir_path)):
    if di == 'st':
        dir_path = os.path.join(all_dir_path, di)
    else:
        dir_path = os.path.join(all_dir_path, di, target)
    tr_file_path = os.path.join(dir_path, "tr_res.csv")
    eval_file_path = os.path.join(dir_path, "eval_res.csv")
    
    if not os.path.exists(tr_file_path) or not os.path.exists(eval_file_path):
        print(f"ファイルが見つかりません: {tr_file_path} または {eval_file_path}")
        continue

    # 学習データを読み込み
    tr_data = pd.read_csv(tr_file_path)
    eval_data = pd.read_csv(eval_file_path)

    tr_data['daytime'] = pd.to_datetime(tr_data['daytime'])
    eval_data['daytime'] = pd.to_datetime(eval_data['daytime'])

    # 評価時刻を設定
    eval_times = eval_data['daytime']

    # 各ウィンドウサイズの Training Cost を計算
    tr_cost = calculate_training_cost(di, tr_data, eval_times, epochs)
    tr_cost = tr_cost / 1e3  # スケール調整（10^3単位）
    
    if first_reading_flag:
        dfs = pd.concat([eval_times,tr_cost],axis=1)
        first_reading_flag = False
    else:
        dfs = pd.concat([dfs,tr_cost],axis=1)
    print(dfs)
    print('==========')

print(dfs)

# --- プロット
plt.figure(figsize=(12, 8))

for column in dfs.columns:
    if column != "daytime":
        plt.plot(dfs["daytime"], dfs[column], label=column)

# グラフ設定
plt.xlabel("Daytime", fontsize=14)
plt.ylabel("Training Cost [$10^3$]", fontsize=14)
plt.xticks(rotation=45, fontsize=10)
plt.yticks(fontsize=10)
plt.legend(fontsize=10, title="Window Size")
plt.title(f'{target}:{os.path.basename(all_dir_path)}')
plt.grid(True)

# グラフ保存
output_plot_path = os.path.join(output_dir_path, f"TrainingCost_{target}_{os.path.basename(all_dir_path)}.png")
plt.savefig(output_plot_path, dpi=300)
plt.show()

print(f"グラフを保存しました: {output_plot_path}")