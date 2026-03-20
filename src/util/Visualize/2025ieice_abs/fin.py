import os
import pandas as pd
import japanize_matplotlib
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator, MultipleLocator

#-------------------------------------------------------------------#
# 定数定義
metrix = "TN_rate"
nt_dir_path = "/mnt/nas0/g005/murasemaru/exp/5_Eval/20220110-20220114_UsEast/nt/dnn_e30b10"
st_dir_path = "/mnt/nas0/g005/murasemaru/exp/5_Eval/20220110-20220114_UsEast/st/dnn_e30b10"
st_epochs = 30
dy_dir_path = "/mnt/nas0/g005/murasemaru/exp/5_Eval/20220110-20220114_UsEast/dy/dnn_e30b10/e50b10/c600p1800/th450"
dy_epochs = 30
#-------------------------------------------------------------------#

# 出力先ディレクトリの設定
output_dir = f"{dy_dir_path}/res_img"
os.makedirs(output_dir, exist_ok=True)
output_path = f"{output_dir}/STvsDY_{metrix}.png"

# データの読み込みと前処理
nt_eval_data = pd.read_csv(f"{nt_dir_path}/eval_res.csv").rename(columns={metrix: "nt"})
st_eval_data = pd.read_csv(f"{st_dir_path}/eval_res.csv").rename(columns={metrix: "static"})
dy_eval_data = pd.read_csv(f"{dy_dir_path}/eval_res.csv").rename(columns={metrix: "dynamic"})

eval_data = pd.concat(
    [nt_eval_data.loc[:, ["daytime", "nt"]],
     st_eval_data.loc[:, ["static"]],
     dy_eval_data.loc[:, ["dynamic"]]],
    axis=1
)
eval_data['daytime'] = pd.to_datetime(eval_data['daytime'])

st_tr_data = pd.read_csv(f"{st_dir_path}/tr_res.csv")
st_tr_data["daytime"] = pd.to_datetime(st_tr_data["daytime"])
dy_tr_data = pd.read_csv(f"{dy_dir_path}/tr_res.csv")
dy_tr_data["daytime"] = pd.to_datetime(dy_tr_data["daytime"])
print(dy_tr_data["daytime"])

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
eval_data['st_tr_cost'] = st_tr_cost / 1e3  # 10^6で割る
eval_data['dy_tr_cost'] = dy_tr_cost / 1e3  # 10^6で割る
eval_data = eval_data.reset_index()

#-------------------------------------------------------------------#
# 経過時間の計算（時間単位）
start_time = eval_data['daytime'].min()
eval_data['elapsed_hours'] = (eval_data['daytime'] - start_time).dt.total_seconds() / 3600  # 経過時間を時間単位に変換

# dy_tr_data の日時を破線でグラフに追加するための処理
dy_training_times = dy_tr_data["daytime"]

def plot_training_cost(eval_data, output_path, label_size, ticks_size, legend_size, dy_training_times):
    fig, ax = plt.subplots(figsize=(18, 6))

    # 学習コストをプロット
    line1, = ax.plot(eval_data['elapsed_hours'], eval_data['st_tr_cost'], label='従来手法による学習コスト',
                     linewidth=2, linestyle='--', color='#984ea3', marker='o')
    line2, = ax.plot(eval_data['elapsed_hours'], eval_data['dy_tr_cost'], label='提案手法による学習コスト',
                     linewidth=2, linestyle='--', color='#ff7f00', marker='s')
    ax.set_ylabel(r'Training cost [$10^3$]', fontsize=label_size, color='black')
    ax.set_xlabel('Elapsed time [h]', fontsize=label_size, color='black')
    
    # dy_training_times を縦線として描画
    for time in dy_training_times:
        elapsed_hour = (time - eval_data['daytime'].min()).total_seconds() / 3600
        ax.axvline(x=elapsed_hour, color='black', linestyle='--', linewidth=1, label="Dynamic Training Time")

    # 目盛りを調整（ここで目盛り間隔を指定）
    ax.yaxis.set_major_locator(MultipleLocator(10))  # 目盛り間隔を10に設定
    ax.tick_params(axis='y', labelsize=ticks_size)
    ax.tick_params(axis='x', labelsize=ticks_size)
    ax.grid(True)

    # 凡例
    lines = [line1, line2]
    labels = [line.get_label() for line in lines]
    fig.legend(lines, labels, loc='upper right', bbox_to_anchor=(0.95, 0.68), fontsize=legend_size)

    # 保存と表示
    fig.tight_layout()
    plt.savefig(output_path, dpi=300)
    plt.show()

def plot_f1_score(eval_data, output_path, label_size, ticks_size, legend_size, dy_training_times):
    fig, ax = plt.subplots(figsize=(18, 6))

    # F1スコアをプロット
    line1, = ax.plot(eval_data['elapsed_hours'], eval_data["nt"], label="再学習なし", linewidth=2, color="#7F7F7F")
    line2, = ax.plot(eval_data['elapsed_hours'], eval_data["static"], label="従来手法", linewidth=2, color="#377eb8")
    line3, = ax.plot(eval_data['elapsed_hours'], eval_data["dynamic"], label="提案手法", linewidth=2, color='#e41a1c')
    ax.set_ylabel('F1score', fontsize=label_size, color='black')
    ax.set_xlabel('Elapsed time [h]', fontsize=label_size, color='black')
    
    # dy_training_times を縦線として描画
    for time in dy_training_times:
        elapsed_hour = (time - eval_data['daytime'].min()).total_seconds() / 3600
        ax.axvline(x=elapsed_hour, color='black', linestyle='--', linewidth=1, label="Dynamic Training Time")

    ax.tick_params(axis='y', labelsize=ticks_size)
    ax.tick_params(axis='x', labelsize=ticks_size)
    ax.grid(True)

    # 凡例
    lines = [line1, line2, line3]
    labels = [line.get_label() for line in lines]
    fig.legend(lines, labels, loc='upper right', bbox_to_anchor=(0.3, 0.5), fontsize=legend_size)

    # 保存と表示
    fig.tight_layout()
    plt.savefig(output_path, dpi=300)
    plt.show()

# ファイル出力パスの設定
output_path_f1 = f"{output_dir}/STvsDY_F1score.png"
output_path_cost = f"{output_dir}/STvsDY_TrainingCost.png"


# 修正後のプロット実行
plot_f1_score(eval_data, output_path_f1, label_size=26, ticks_size=20, legend_size=26, dy_training_times=dy_training_times)
plot_training_cost(eval_data, output_path_cost, label_size=26, ticks_size=20, legend_size=26, dy_training_times=dy_training_times)


print(output_path_f1)
print(output_path_cost)
