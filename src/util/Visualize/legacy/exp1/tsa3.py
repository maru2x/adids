import csv
import os
from collections import deque
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
from joblib import Parallel, delayed
from scipy.stats import ks_2samp, wasserstein_distance
from sklearn.preprocessing import StandardScaler

# --- データセットの各特徴量の分布がどのように遷移しているかを調査 Time Series Analysis --------------------------------------------------- #
dir_path = "/mnt/nas0/g005/murasemaru/data/csv/modif/filtered_20220117-20220121"
population_dir_path = "/mnt/nas0/g005/murasemaru/data/csv/unproc/2201Lab02"
data_sec_sizes = [0.5, 1, 4, 8, 16, 32, 64]  # データ区間の長さ(hours)
unit_time = 0.5  # 評価単位時間(hours)
output_base_dir = f"/mnt/nas0/g005/murasemaru/exp/1_DataAnalytics/drift/filtered_20220117-20220121/{os.path.basename(dir_path)}"
# ---------------------------------------------------------------------------------------------------------------------------------- #

features = ["rcv_packet_count", "snd_packet_count", "tcp_count", "udp_count", "most_port", "port_count",
            "rcv_max_interval", "rcv_min_interval", "rcv_max_length", "rcv_min_length", "snd_max_interval",
            "snd_min_interval", "snd_max_length", "snd_min_length", "label"]

population_data = []
for d_file in sorted(os.listdir(population_dir_path)):
    d_file_path: str = f"{population_dir_path}/{d_file}"
    with open(d_file_path, mode='r') as f:
        reader = csv.reader(f)
        headers = next(reader)
        for row in reader:
            population_data.append([float(row[headers.index(feature)]) for feature in features])

population_data = np.array(population_data).T
print("Population data loaded and prepared.")

class Window:
    def __init__(self):
        self.cw = deque()
        self.cw_date_q = deque()
        self.cw_end_date = None

    def update(self, row, c_time, data_sec_size):
        self.cw.append(np.array(row, dtype=float))

        if not self.cw_date_q:
            self.cw_end_date = c_time - timedelta(hours=data_sec_size)
        else:
            delta = c_time - self.cw_date_q[-1]
            self.cw_end_date += delta
            while self.cw_date_q and self.cw_date_q[0] < self.cw_end_date:
                self.cw.popleft()
                self.cw_date_q.popleft()
        self.cw_date_q.append(c_time)

for data_sec_size in data_sec_sizes:
    output_dir = os.path.join(output_base_dir, f"{data_sec_size}H")

    w = Window()
    first_row_flag = True
    start_date = None
    next_eval_date = None
    row_ct = 0

    eval_res_col = ["date", "row_ct", "w_rcv_pkt_ct", "w_snd_pkt_ct", "w_tcp_ct", "w_udp_ct",
                    "w_most_port", "w_port_ct", "w_rcv_max_int", "w_rcv_min_int", 
                    "w_rcv_max_len", "w_rcv_min_len", "w_snd_max_int", "w_snd_min_int", 
                    "w_snd_max_len", "w_snd_min_len", "w_label",
                    "ks_rcv_pkt_ct", "ks_snd_pkt_ct", "ks_tcp_ct", "ks_udp_ct", 
                    "ks_most_port", "ks_port_ct", "ks_rcv_max_int", "ks_rcv_min_int", 
                    "ks_rcv_max_len", "ks_rcv_min_len", "ks_snd_max_int", 
                    "ks_snd_min_int", "ks_snd_max_len", "ks_snd_min_len", "ks_label"]

    eval_res_li = np.empty((0, len(eval_res_col)), dtype=object)
    for d_file in sorted(os.listdir(dir_path)):
        d_file_path: str = f"{dir_path}/{d_file}"
        print(f"- {d_file} set now")
        f = open(d_file_path, mode='r')
        reader = csv.reader(f)
        headers = next(reader)
        for row in reader:
            row_ct += 1
            c_time = datetime.strptime(row[headers.index("daytime")], "%Y-%m-%d %H:%M:%S")
            print(f"ct: {row_ct} | {c_time}")
            if first_row_flag:
                start_date = c_time
                first_row_flag = False

            if c_time < start_date + timedelta(hours=unit_time):
                next_eval_date = c_time
                w.update(row[3:], c_time, data_sec_size)
                continue

            if c_time > next_eval_date:
                cw_arr = np.array(w.cw)
                if cw_arr.ndim == 1:
                    cw_arr = cw_arr.reshape(1, -1)
                try:
                    ex_cw = cw_arr.T
                except IndexError:
                    ex_cw = np.zeros((4, cw_arr.shape[0]))
                w_dis = Parallel(n_jobs=-1)(
                    delayed(wasserstein_distance)(c, p) for c, p in zip(ex_cw, population_data)
                )
                while len(w_dis) < len(features):
                    w_dis.append(0)
                ks_dis = Parallel(n_jobs=-1)(
                    delayed(lambda c, p: ks_2samp(c, p).statistic)(c, p) for c, p in zip(ex_cw, population_data)
                )
                eval_daytime = next_eval_date
                eval_arr = [eval_daytime, cw_arr.shape[0]] + w_dis + ks_dis
                eval_res_li = np.vstack([eval_res_li, eval_arr])
                next_eval_date += timedelta(hours=unit_time)
                row_ct = 0
                cw_arr = None

            w.update(row[3:], c_time, data_sec_size)
        f.close()

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    add_res_col = ["w_mean_dis", "ks_mean_dis", "mean_dis"]
    add_res_li = []

    scaler = StandardScaler()
    eval_res_li_scaled = scaler.fit_transform(eval_res_li[:, 2:])

    w_mean_dis = np.mean(eval_res_li_scaled[:, 0:14], axis=1)
    add_res_li.append(w_mean_dis)

    ks_mean_dis = np.mean(eval_res_li_scaled[:, 15:-1], axis=1)
    add_res_li.append(ks_mean_dis)

    mean_dis_li = (w_mean_dis + ks_mean_dis) / 2
    add_res_li.append(mean_dis_li)

    add_res_li = np.array(add_res_li).T

    eval_res_li = np.hstack((eval_res_li[:, [0, 1]], eval_res_li_scaled))
    eval_res = pd.DataFrame(eval_res_li, columns=eval_res_col)
    add_res = pd.DataFrame(add_res_li, columns=add_res_col)

    eval_res = pd.concat([eval_res, add_res], axis=1)
    eval_res.to_csv(os.path.join(output_dir, f"with_population_{data_sec_size}H.csv"), index=False)
    print(f"Output for data_sec_size={data_sec_size}: {output_dir}/with_population_{data_sec_size}H.csv")
