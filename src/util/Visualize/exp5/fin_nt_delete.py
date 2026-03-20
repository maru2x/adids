import os
import pandas as pd
import japanize_matplotlib
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator

#-------------------------------------------------------------------#
# 定数定義
metrix = "accuracy"
st_dir_path = "/mnt/nas0/g005/murasemaru/exp/5_Eval/2201AusEast/1/st"
st_epochs = 30
dy_dir_path = "/mnt/nas0/g005/murasemaru/exp/5_Eval/2201AusEast/1/dy_th100_cw600_pw1200"
dy_epochs = 30
#-------------------------------------------------------------------#

# 出力先ディレクトリの設定
output_dir = f"{dy_dir_path}/res_img"
os.makedirs(output_dir, exist_ok=True)
output_path = f"{output_dir}/STvsDY_{metrix}.png"

# データの読み込みと前処理
st_eval_data = pd.read_csv(f"{st_dir_path}/results_evaluate.csv").rename(columns={metrix: "static"})
dy_eval_data = pd.read_csv(f"{dy_dir_path}/results_evaluate.csv").rename(columns={metrix: "dynamic"})

eval_data = pd.concat(
    [st_eval_data.loc[:, ["daytime", "static"]],
     dy_eval_data.loc[:, ["dynamic"]]],
    axis=1
)
eval_data['daytime'] = pd.to_datetime(eval_data['daytime'])

st_tr_data = pd.read_csv(f"{st_dir_path}/results_training.csv")
st_tr_data["daytime"] = pd.to_datetime(st_tr_data["daytime"])
dy_tr_data = pd.read_csv(f"{dy_dir_path}/results_training.csv")
dy_tr_data["daytime"] = pd.to_datetime(dy_tr_data["daytime"])

# 学習コストを計算する関数を定義
def calculate_training_cost(tr_data, eval_times, epochs, window_minutes=30):
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
    return pd.Series(costs, index=eval_times)

# 評価時刻のリスト
eval_times = eval_data['daytime']

# 各データセットの学習コストを計算
st_tr_cost = calculate_training_cost(st_tr_data, eval_times, st_epochs)
dy_tr_cost = calculate_training_cost(dy_tr_data, eval_times, dy_epochs)

# データの結合
eval_data = eval_data.set_index('daytime')
eval_data['st_tr_cost'] = st_tr_cost / 1e6  # 1e6で割る
eval_data['dy_tr_cost'] = dy_tr_cost / 1e6  # 1e6で割る
eval_data = eval_data.reset_index()

#-------------------------------------------------------------------#
# 経過時間の計算（時間単位）
start_time = eval_data['daytime'].min()
eval_data['elapsed_hours'] = (eval_data['daytime'] - start_time).dt.total_seconds() / 3600  # 経過時間を時間単位に変換
# プロット関数の修正
def plot_accuracy_and_cost_with_elapsed_hours(eval_data, dy_tr_data, output_path, label_size, ticks_size, legend_size):
    fig, ax1 = plt.subplots(figsize=(14, 10))

    # 左側の軸に精度をプロット
    line1, = ax1.plot(eval_data['elapsed_hours'], eval_data["static"], label="従来手法", linewidth=2, color="#377eb8")
    line2, = ax1.plot(eval_data['elapsed_hours'], eval_data["dynamic"], label="提案手法", linewidth=2, color='#e41a1c')
    ax1.set_ylabel('Accuracy', fontsize=label_size, color='black')  # ラベルを「Accuracy」に変更
    ax1.tick_params(axis='y', labelsize=ticks_size)
    ax1.tick_params(axis='x', labelsize=ticks_size)
    ax1.set_xlabel('Elapsed time [h]', fontsize=label_size, color='black')  # 横軸ラベルを変更
    ax1.grid(True)

    # dy_tr_dataの日付を破線でプロット
    for timestamp in dy_tr_data["daytime"]:
        elapsed_hour = (timestamp - eval_data['daytime'].min()).total_seconds() / 3600  # 経過時間を計算
        ax1.axvline(x=elapsed_hour, color='gray', linestyle='--', linewidth=1, alpha=0.6)

    # 右側の軸に学習コストをプロット
    ax2 = ax1.twinx()
    line3, = ax2.plot(eval_data['elapsed_hours'], eval_data['st_tr_cost'], label='従来手法による学習コスト',
                      linewidth=2, linestyle='--', color='#984ea3', marker='o')
    line4, = ax2.plot(eval_data['elapsed_hours'], eval_data['dy_tr_cost'], label='提案手法による学習コスト',
                      linewidth=2, linestyle='--', color='#ff7f00', marker='s')
    ax2.set_ylabel('Training cost [1e6]', fontsize=label_size, color='black')  # 1e6形式のラベル
    ax2.yaxis.set_major_locator(MaxNLocator(integer=True))  # 整数値の目盛りを設定
    ax2.tick_params(axis='y', labelsize=ticks_size)

    # 凡例
    lines = [line1, line2, line3, line4]
    labels = [line.get_label() for line in lines]
    fig.legend(lines, labels, loc='center left', fontsize=legend_size, bbox_to_anchor=(0.08, 0.65), ncol=1)

    # 保存と表示
    fig.tight_layout()
    plt.savefig(output_path, dpi=300)
    plt.show()

plot_accuracy_and_cost_with_elapsed_hours(eval_data, dy_tr_data, output_path, label_size=24, ticks_size=18, legend_size=24)
