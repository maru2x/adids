import csv
import os
from collections import deque
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
from joblib import Parallel, delayed
from scipy.stats import entropy, ks_2samp, wasserstein_distance

# --- データセットの特徴量の分布がどのように遷移しているかを調査 --------------------------------------------------------------------- #
dir_path = "/mnt/nas0/g005/murasemaru/data/csv/unproc/2201AusEast"
"""
metrix overview
"rcv_packet_count","snd_packet_count","tcp_count","udp_count",
"most_port","port_count","rcv_max_interval","rcv_min_interval",
"rcv_max_length","rcv_min_length","snd_max_interval","snd_min_interval",
"snd_max_length","snd_min_length","label"
"""
features = ["rcv_packet_count", "snd_packet_count", "tcp_count", "udp_count", "most_port", "port_count",
            "rcv_max_interval", "rcv_min_interval", "rcv_max_length", "rcv_min_length", "snd_max_interval",
            "snd_min_interval", "snd_max_length", "snd_min_length", "label"]
data_sec_size = 1 # データ区間の長さ(hours)
unit_time = 1 # 評価単位時間(hours)
output_dir = f"/mnt/nas0/g005/murasemaru/exp/1_DataAnalytics/drift/{os.path.basename(dir_path)}"  # グラフ保存先

# ---------------------------------------------------------------------------------------------------------------------------------- #

class Window:
    def __init__(self):
        self.cw = deque()
        self.cw_date_q = deque()  # datetime型を持つDeque
        self.cw_end_date=None
        self.pw = deque()
        self.pw_date_q = deque()
        self.pw_end_date=None

    def update(self, row, c_time, data_sec_size):
        self.cw.append(np.array(row, dtype=float))

        if not self.cw_date_q:
            self.cw_end_date = c_time-timedelta(hours=data_sec_size)
            self.pw_end_date = self.cw_end_date-timedelta(hours=data_sec_size)
        else:
            delta = c_time - self.cw_date_q[-1]
            self.cw_end_date+=delta
            self.pw_end_date+=delta
            while self.cw_date_q and self.cw_date_q[0] < self.cw_end_date:
                self.pw.append(self.cw.popleft())
                self.pw_date_q.append(self.cw_date_q.popleft())
            while self.pw_date_q and self.pw_date_q[0] < self.pw_end_date:
                self.pw.popleft()
                self.pw_date_q.popleft()
        self.cw_date_q.append(c_time)

w = Window()
first_row_flag = True
start_date = None
next_eval_date = None
eval_results_col = ["daytime", "rcv_pkt_ct", "snd_pkt_ct", "tcp_ct", "udp_ct", "most_port", "port_ct", 
                    "rcv_max_int", "rcv_min_int", "rcv_max_len", "rcv_min_len", "snd_max_int", 
                    "snd_min_int", "snd_max_len", "snd_min_len", "label", "mean_dis", "kl_div", "ks_dist"]
eval_results_list = np.empty((0,len(eval_results_col)),dtype=object)

for d_file in sorted(os.listdir(dir_path)):
    d_file_path: str = f"{dir_path}/{d_file}"
    print(f"- {d_file} set now")
    f = open(d_file_path, mode='r')
    reader = csv.reader(f)
    headers = next(reader)
    for row in reader:
        c_time = datetime.strptime(row[headers.index("daytime")], "%Y-%m-%d %H:%M:%S")
        if first_row_flag:
            start_date = c_time
            first_row_flag = False

        if c_time < start_date+timedelta(hours=unit_time*2):
            next_eval_date = c_time
            w.update(row[3:], c_time, data_sec_size)
            continue

        # --- 現在ウィンドウと過去ウィンドウのデータ分布の違いを計算
        if c_time > next_eval_date:
            cw_arr = np.array(w.cw)
            if cw_arr.ndim == 1:
                cw_arr = cw_arr.reshape(1, -1)
            try:
                extracted_cw = cw_arr.T
            except IndexError:
                extracted_cw = np.zeros((4, cw_arr.shape[0]))

            pw_arr = np.array(w.pw)
            if pw_arr.ndim == 1:
                pw_arr = pw_arr.reshape(1, -1)
            try:
                extracted_pw = pw_arr.T
            except IndexError:
                extracted_pw = np.zeros((4, cw_arr.shape[0]))

            # 距離計算
            distances = Parallel(n_jobs=-1)(
                delayed(wasserstein_distance)(c, p) for c, p in zip(extracted_cw, extracted_pw)
            )

            kl_divs = Parallel(n_jobs=-1)(
                delayed(entropy)(c, p) for c, p in zip(extracted_cw, extracted_pw) if np.all(p > 0)
            )

            ks_dists = Parallel(n_jobs=-1)(
                delayed(lambda c, p: ks_2samp(c, p).statistic)(c, p) for c, p in zip(extracted_cw, extracted_pw)
            )

            # 空の場合にデフォルト値を設定
            if len(distances) == 0:
                distances = [0] * (len(eval_results_col) - 3)  # カラム数に合わせてゼロ埋め
            mean_distance = np.mean(distances) if len(distances) > 0 else 0
            mean_kl_div = np.mean(kl_divs) if len(kl_divs) > 0 else 0
            mean_ks_dist = np.mean(ks_dists) if len(ks_dists) > 0 else 0

            evaluate_daytime = next_eval_date
            eval_arr = [evaluate_daytime] + distances + [mean_distance, mean_kl_div, mean_ks_dist]
            eval_results_list = np.vstack([eval_results_list, eval_arr])

            print(eval_arr)

            next_eval_date+=timedelta(hours=unit_time)

        w.update(row[3:], c_time, data_sec_size)
    f.close()
    # ディレクトリが存在しない場合は作成
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    eval_results = pd.DataFrame(eval_results_list, columns=eval_results_col)
    eval_results.to_csv(os.path.join(output_dir, "drift_obs.csv"), index=False)
