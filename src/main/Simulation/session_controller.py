import time
import re

import pandas as pd
import pytz
from sklearn.preprocessing import MinMaxScaler

from .session_definer import *


class SessionController:
    def __init__(self, loader):
        self.loader = loader
        self.jst = pytz.timezone("Asia/Tokyo")
        self.init_time = datetime.now(self.jst).strftime("%Y%m%d%H%M%S")
        self.output_path = self._create_output_dir()
        self.tr_results_col = ["daytime", "accuracy", "loss", "training_time", "benign_count", "malicious_count", "flow_num"]
        self.tr_results_list = []
        # tr_results_list = (model num, step num, col num)
        self.eval_results_col = ["daytime", "label_key", "TP", "FN", "FP", "TN", "flow_num", "TP_rate", "FN_rate", "FP_rate", "TN_rate",
                            "accuracy", "precision", "f1_score", "loss", "benign_rate"]
        self.eval_results_list = np.empty((0, len(self.eval_results_col)), dtype=object)

    def _create_output_dir(self):
        d_dir = os.path.basename(self.loader.get("DATASETS_DIR_PATH"))
        path = f"{self.loader.get('USER_DIR')}/exp/{self.init_time}_{d_dir}_{self.loader.get('RETRAINING_MODE')}_{self.loader.get('MODEL_CODE')}"
        os.makedirs(path)
        os.makedirs(f"{path}/m1_weights")
        return path

    def _finalize(self, current_time, session):
        self.loader.append_log('INIT_TIME', self.init_time)
        self.loader.append_log('SESSION_END_DAYTIME', current_time.isoformat())
        elapsed_time = time.time() - self.jst.localize(datetime.strptime(self.init_time, "%Y%m%d%H%M%S")).timestamp()
        self.loader.append_log('ELAPSED_TIME', elapsed_time)
        self.loader.save(f"{self.output_path}/settings_log.json")

        # --- Results processing
        add_results_col = ["nmr_fn_rate", "nmr_benign_rate"]
        add_results_list = np.empty((0, len(add_results_col)))

        flow_idx = self.eval_results_col.index("flow_num")
        benign_rate_idx = self.eval_results_col.index("benign_rate")
        if session.eval_results_list.size:
            sum_fn = np.sum(session.eval_results_list[:, flow_idx].astype(float))

            # nmr_flow_num_ratio
            min_max_scaler = MinMaxScaler()
            fn_rate = session.eval_results_list[:, flow_idx].astype(float) / sum_fn
            reshaped_fn_rate = fn_rate.reshape(-1, 1)
            scaled_fn_rate = min_max_scaler.fit_transform(reshaped_fn_rate)

            # nmr_benign_ratio
            reshaped_ben_ratio = session.eval_results_list[:, benign_rate_idx].astype(float).reshape(-1, 1)
            scaled_ben_ratio = min_max_scaler.fit_transform(reshaped_ben_ratio)
            add_results_list = np.column_stack(
                [scaled_fn_rate.flatten(), scaled_ben_ratio.flatten()]
            )

        # training results
        if isinstance(session.tr_results_list, dict):
            for key, window_lists in session.tr_results_list.items():
                safe_key = self._sanitize_key(key)
                if not window_lists:
                    continue
                if window_lists and isinstance(window_lists[0], list):
                    for i, result_list in enumerate(window_lists):
                        if not result_list:
                            continue
                        df = pd.DataFrame(result_list, columns=self.tr_results_col)
                        df.to_csv(os.path.join(self.output_path, f"res_train_{safe_key}_m{i}.csv"), index=False)
                else:
                    df = pd.DataFrame(window_lists, columns=self.tr_results_col)
                    df.to_csv(os.path.join(self.output_path, f"res_train_{safe_key}.csv"), index=False)
        else:
            for i, result_list in enumerate(session.tr_results_list):
                df = pd.DataFrame(result_list, columns=self.tr_results_col)
                df.to_csv(os.path.join(self.output_path, f"res_train_m{i}.csv"), index=False)

        # evaluate results
        eval_results = pd.DataFrame(session.eval_results_list, columns=self.eval_results_col)
        add_results = pd.DataFrame(add_results_list, columns=add_results_col)

        # Combine evaluate_results with additional_results
        eval_results = pd.concat([eval_results, add_results], axis=1)
        eval_results.to_csv(os.path.join(self.output_path, "res_eval.csv"), index=False)

    def _sanitize_key(self, key):
        return re.sub(r"[^A-Za-z0-9._-]+", "_", key).strip("_") or "default"


    def run(self, model_factory):
        mode_map = {
            "dy": DynamicSession,
            "st": StaticSession,
            "nt": NoRetrainSession
        }
        mode = self.loader.get("RETRAINING_MODE")
        session_cls = mode_map.get(mode)
        if not session_cls:
            raise ValueError(f"Invalid RETRAINING_MODE: {mode}")

        session = session_cls(self.loader, model_factory, self.tr_results_list, self.eval_results_list, self.output_path)
        current_time = session.run()
        self._finalize(current_time, session)
