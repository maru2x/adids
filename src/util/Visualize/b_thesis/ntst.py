import os
import pandas as pd
import japanize_matplotlib
import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator
from datetime import timedelta, datetime

#-------------------------------------------------------------------#
# 定数定義
metrix = "f1_score"
nt_dir_path = "/mnt/nas0/g005/murasemaru/exp/3_Eval/20220110-20220114_UsEast/nt/dnn_e30b10"
st_dir_path = "/mnt/nas0/g005/murasemaru/exp/3_Eval/20220110-20220114_UsEast/st/dnn_e30b10"
st_epochs = 30
start_date = '2022-01-10 15:00:00'
#-------------------------------------------------------------------#

# 出力先ディレクトリの設定
output_dir = f"{st_dir_path}/res_img"
os.makedirs(output_dir, exist_ok=True)
output_path = f"{output_dir}/ST_{metrix}.png"
start_date = datetime.strptime(start_date, '%Y-%m-%d %H:%M:%S')

# 評価データの読み込みと前処理
nt_eval_data = pd.read_csv(f"{nt_dir_path}/eval_res.csv").rename(columns={metrix: "nt"})
st_eval_data = pd.read_csv(f"{st_dir_path}/eval_res.csv").rename(columns={metrix: "static"})

eval_data = pd.concat(
    [nt_eval_data.loc[:, ["daytime", "nt"]],
     st_eval_data.loc[:, ["static"]]],
    axis=1
)
eval_data['daytime'] = pd.to_datetime(eval_data['daytime'])

# 経過時間の計算（時間単位）
eval_data['elapsed_hours'] = (eval_data['daytime'] - start_date).dt.total_seconds() / 3600

def plot_metrix(eval_data, start_date, output_path, label_size, ticks_size, legend_size):
    fig, ax = plt.subplots(figsize=(18, 6))
    line1, = ax.plot(eval_data['elapsed_hours'], eval_data["nt"], label="再学習なし", linewidth=2, color="tab:gray")
    line2, = ax.plot(eval_data['elapsed_hours'], eval_data["static"], label="従来手法", linewidth=2, color="tab:blue")
    ax.set_ylabel('F1score', fontsize=label_size, color='black')
    ax.set_xlabel('Elapsed time [h]', fontsize=label_size, color='black')
    ax.tick_params(axis='y', labelsize=ticks_size)
    ax.tick_params(axis='x', labelsize=ticks_size)
    ax.grid(True)
    lines = [line1, line2]
    labels = [line.get_label() for line in lines]
    plt.xlim(12, 52)
    fig.legend(lines, labels, loc='upper right', bbox_to_anchor=(0.3, 0.6), fontsize=legend_size)
    fig.tight_layout()
    plt.savefig(output_path, dpi=500)
    plt.show()

plot_metrix(eval_data, start_date, output_path, label_size=26, ticks_size=20, legend_size=30)

print(output_path)
