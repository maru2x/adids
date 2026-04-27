import numpy as np
import faiss

from collections import deque
from datetime import datetime, timedelta
import csv

class DetectionWindow:
    def __init__(self, model, cw_size, pw_size, method_code, k, threshold, feature_columns, scaling_rules):
        self.model = model
        self.cw = deque()
        self.cw_size = cw_size
        self.cw_date_q = deque()
        self.cw_end_date = None
        self.pw = deque()
        self.pw_size = pw_size
        self.pw_date_q = deque()
        self.pw_end_date = None
        self.cum_statics: float = 0.0
        self.method_code = method_code
        self.k = k
        self.threshold = threshold
        self.feature_columns = feature_columns
        self._feature_idx_map = {name: idx for idx, name in enumerate(feature_columns)}
        self.scaling_rules = scaling_rules

    def update(self, row, c_time):
        self.cw.append(np.array(row, dtype=float))
        if not self.cw_date_q:
            self.cw_end_date = c_time - timedelta(seconds=self.cw_size)
            self.pw_end_date = self.cw_end_date - timedelta(seconds=self.pw_size)
        else:
            delta = c_time - self.cw_date_q[-1]
            self.cw_end_date += delta
            self.pw_end_date += delta
            while self.cw_date_q and self.cw_date_q[0] < self.cw_end_date:
                self.pw.append(self.cw.popleft())
                self.pw_date_q.append(self.cw_date_q.popleft())
            while self.pw_date_q and self.pw_date_q[0] < self.pw_end_date:
                self.pw.popleft()
                self.pw_date_q.popleft()
        self.cw_date_q.append(c_time)

    def detect(self) -> bool:
        if len(self.cw) < self.k or len(self.pw) < self.k:
            return False
        scaled_cw = self._scale_window(self.cw)
        scaled_pw = self._scale_window(self.pw)
        method_dict = {
            0: cos_similarity,
            1: euc_distance,
        }
        method = method_dict.get(self.method_code)
        if method is None:
            raise ValueError(f"Invalid method_code: {self.method_code}")
        _, detected = method(scaled_cw, scaled_pw, self.threshold, self.k)
        return detected

    def detect_and_log(self, c_time: datetime, o_dir_path: str) -> bool:
        scaled_cw = self._scale_window(self.cw)
        scaled_pw = self._scale_window(self.pw)
        method_dict = {
            0: cos_similarity,
            1: euc_distance
        }
        method = method_dict.get(self.method_code)
        if method is None:
            raise ValueError(f"Invalid method_code: {self.method_code}")
        score, detected = method(scaled_cw, scaled_pw, self.threshold, self.k)

        output_csv_path = f'{o_dir_path}/res_dd.csv'
        with open(output_csv_path, mode='a', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            if file.tell() == 0:
                writer.writerow(["date", "score", "detected"])
            writer.writerow([c_time, score, detected])
        return detected

    def _scale_window(self, window):
        feature_dim = len(self.feature_columns)
        if not window:
            return np.zeros((1, feature_dim))
        window_arr = np.array(window)
        if window_arr.ndim == 1:
            window_arr = window_arr.reshape(1, -1)
        if window_arr.shape[1] <= 1:  # ラベルしかない or 列がない
            return np.zeros((window_arr.shape[0], feature_dim))
        scaled_window = window_arr[:, :-1]
        if scaled_window.shape[1] != feature_dim:
            return scaled_window

        # スケーリング対象のインデックス群
        log_scale_names = self.scaling_rules.get("log_scale", [])
        log_scale_no_divide = self.scaling_rules.get("log_scale_no_divide", [])
        interval_names = self.scaling_rules.get("interval", [])
        length_names = self.scaling_rules.get("length", [])
        port_bucket_names = self.scaling_rules.get("port_bucket", [])

        log_scale_idxs = [self._feature_idx_map[name] for name in log_scale_names if name in self._feature_idx_map]
        log_scale_no_divide_idxs = [
            self._feature_idx_map[name]
            for name in log_scale_no_divide
            if name in self._feature_idx_map
        ]
        interval_idxs = [self._feature_idx_map[name] for name in interval_names if name in self._feature_idx_map]
        length_idxs = [self._feature_idx_map[name] for name in length_names if name in self._feature_idx_map]
        port_idx = self._feature_idx_map.get(port_bucket_names[0]) if port_bucket_names else None

        if log_scale_idxs:
            scaled_window[:, log_scale_idxs] /= 1000
            scaled_window[:, log_scale_idxs] = np.log1p(scaled_window[:, log_scale_idxs])
        if log_scale_no_divide_idxs:
            scaled_window[:, log_scale_no_divide_idxs] = np.log1p(
                scaled_window[:, log_scale_no_divide_idxs]
            )
        if port_idx is not None:
            port_vals = scaled_window[:, port_idx]
            scaled_window[:, port_idx] = np.select(
                [port_vals <= 1023, port_vals <= 49151],
                [0.0, 0.5],
                default=1.0
            )
        if interval_idxs:
            scaled_window[:, interval_idxs] /= 60
        if length_idxs:
            scaled_window[:, length_idxs] /= 10000

        return scaled_window

class WindowManager:
    def __init__(self, model, configs, ensemble_method_code, feature_columns, scaling_rules):
        self.windows = [
            DetectionWindow(
                model,
                cfg.get("CURRENT_WIN_SIZE"),
                cfg.get("PAST_WIN_SIZE"),
                cfg.get("METHOD_CODE"),
                cfg.get("K"),
                cfg.get("THRESHOLD"),
                feature_columns,
                scaling_rules,
            )
            for cfg in configs
        ]
        self.y_pred_arr = [[] for _ in self.windows]
        self.ensemble_method_code = ensemble_method_code
        print('Detection Window Manager Activate: ')
        print(self.windows)

    def update_all(self, row, c_time):
        for w in self.windows:
            w.update(row, c_time)

    def ensemble_window_results(self):
        last_column = [last_column_x[-1] for last_column_x in self.y_pred_arr]
        ensemble_method_dict = {
            0: self._use_first_model_only(last_column),
            1: self._majority_vote(last_column),
        }
        method = ensemble_method_dict.get(self.ensemble_method_code)
        if method is None:
            raise ValueError(f"Invalid method_code: {self.ensemble_method_code}")
        return method

    def calc_first_wait_seconds(self):
        return max([w.cw_size + w.pw_size for w in self.windows])

    def _use_first_model_only(self, last_column):
        if not last_column:
            raise ValueError("last_column is empty")
        return int(last_column[0])

    def _majority_vote(self, last_column):
        return int(sum(last_column)>len(last_column)//2)


def cos_similarity(scaled_cw: np.ndarray, scaled_pw: np.ndarray, threshold: float, k: int) -> bool:
    """
    コサイン類似度行列をFAISSを使用して計算し，行ごとの上位k個の平均類似度を求める．
    平均類似度が閾値以下であるかを判定する．

    Args:
        c_window (np.ndarray): 比較するウィンドウ（2次元配列）．
        p_window (np.ndarray): 比較対象のウィンドウ（2次元配列）．
        threshold (float): 閾値．
        k (int): 上位k個の類似度を考慮する．

    Returns:
        tuple: 平均類似度 (`mean_similarity`) と閾値を超えているかの判定結果 (`True`/`False`)．
    """

    # L2正規化
    normed_cw = scaled_cw / np.linalg.norm(scaled_cw, axis=1, keepdims=True)
    normed_pw = scaled_pw / np.linalg.norm(scaled_pw, axis=1, keepdims=True)

    d = normed_pw.shape[1]
    index = faiss.IndexFlatIP(d)
    index.add(normed_pw.astype(np.float32))
    similarities, indices = index.search(normed_cw.astype(np.float32), k)
    mean_similarity = np.mean(similarities)

    return mean_similarity, mean_similarity < threshold


def euc_distance(scaled_cw: np.ndarray, scaled_pw: np.ndarray, threshold: float, k: int):
    """
    ユークリッド距離行列を計算し，行ごとの上位N個の平均ユークリッド距離を求める．
    平均類似度が閾値以下であるかを判定する．

    Args:
        c_window (np.ndarray): 比較するウィンドウ（2次元配列）．
        p_window (np.ndarray): 比較対象のウィンドウ（2次元配列）．
        threshold (float): 閾値．
        k (int): 上位k個の類似度を考慮する．

    Returns:
        tuple: 平均距離 (`mean_distance`) と閾値を超えているかの判定結果 (`True`/`False`)．
    """

    d = scaled_pw.shape[1]
    index = faiss.IndexFlatL2(d)
    index.add(scaled_pw.astype(np.float32))
    distances, indices = index.search(scaled_cw.astype(np.float32), k)
    mean_distance = np.mean(distances)
    print(f"mean: {mean_distance}")

    return mean_distance, mean_distance > threshold


def euc_distance_hnsw(scaled_cw: np.ndarray, scaled_pw: np.ndarray, threshold: float, k: int):
    """
    ユークリッド距離行列を計算し，行ごとの上位N個の平均ユークリッド距離を求める．
    平均類似度が閾値以下であるかを判定する．

    Args:
        c_window (np.ndarray): 比較するウィンドウ（2次元配列）．
        p_window (np.ndarray): 比較対象のウィンドウ（2次元配列）．
        threshold (float): 閾値．
        k (int): 上位k個の類似度を考慮する．

    Returns:
        tuple: 平均距離 (`mean_distance`) と閾値を超えているかの判定結果 (`True`/`False`)．
    """
    d = scaled_pw.shape[1]
    index = faiss.IndexHNSWFlat(d)
    index.add(scaled_pw.astype(np.float32))
    distances, indices = index.search(scaled_cw.astype(np.float32), k)
    mean_distance = np.mean(distances)
    print(f"mean: {mean_distance}")

    return mean_distance, mean_distance > threshold
