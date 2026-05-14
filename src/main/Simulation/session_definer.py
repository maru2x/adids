import os
import re
import tensorflow as tf

from .evaluator import evaluate
from .trainer import train
from .drift_detection import *

class NoRetrainSession:
    def __init__(self, loader, model_factory, tr_results_list, eval_results_list, output_path):
        self.y_trues = []
        self.y_preds = []
        self.y_pred_keys = []
        self.loader = loader
        self.model_factory = model_factory
        self.model_registry = {"default": self.model_factory.foundation_model}
        self.feature_schema = loader.settings.get("FeatureSchema", {})
        self.feature_mode = self.feature_schema.get("MODE", "legacy")
        self.label_column = self.feature_schema.get("LABEL_COLUMN", "label")
        self.feature_columns = self._resolve_feature_columns()
        self.scaling_rules = self._resolve_scaling_rules()
        self.label_features = self.feature_schema.get("LABEL_FEATURES", [])
        self.label_feature_indices = []
        self.feature_indices = []
        self.label_index = None
        self.key_output_paths = {}
        self.tr_results_list = {} if self.feature_mode == "zeek" else tr_results_list
        self.eval_results_list = eval_results_list
        self.output_path = output_path
        self.session_start_flag = True
        self.first_row_flag = True
        self.session_end_flag = False
        self.session_start_date = datetime.strptime(loader.get('SESSION_START_DATE'), "%Y-%m-%d %H:%M:%S")
        self.current_time = self.session_start_date
        self.rtr_int = loader.get('RETRAINING_INTERVAL')
        self.next_rtr_date = self.session_start_date + timedelta(seconds=self.rtr_int)
        self.eval_unit_int = loader.get('EVALUATE_UNIT_INTERVAL')
        self.next_eval_date = self.session_start_date + timedelta(seconds=self.eval_unit_int)
        self.epochs = loader.get('TrainingDefine')['EPOCHS']
        self.batch_size = loader.get('TrainingDefine')['BATCH_SIZE']
        target_range = timedelta(
            days=loader.get("TargetRange")["DAYS"],
            hours=loader.get("TargetRange")["HOURS"],
            minutes=loader.get("TargetRange")["MINUTES"],
            seconds=loader.get("TargetRange")["SECONDS"]
        )
        self.session_end_date = self.session_start_date + target_range
        self.row_headers = []

    def run(self):
        for d_file in sorted(os.listdir(self.loader.get('DATASETS_DIR_PATH'))):
            if self.session_end_flag: break
            f, reader = self._set_d_file(d_file)
            for row in reader:
                if self._handle_row(row):
                    return self.current_time
            f.close()
        return self.current_time

    def _set_d_file(self, d_file):
        d_file_path: str = f"{self.loader.get('DATASETS_DIR_PATH')}/{d_file}"
        print(f"- {d_file} set now")
        f = open(d_file_path, mode='r')
        reader = csv.reader(f)
        self.row_headers = next(reader)
        self._set_column_indices()
        return f,reader

    def _handle_row(self, row):
        self.current_time = datetime.strptime(row[self.row_headers.index("daytime")], "%Y-%m-%d %H:%M:%S")
        if self.session_start_flag and self._start_filtering():
            return False
        if self._end_filtering(): return True
        self._evaluate_if_needed()
        features = self._extract_features(row)
        label = self._extract_label(row)
        label_key = self._make_label_key(row)
        self.y_trues.append(label)
        self.y_pred_keys.append(label_key)
        model = self._get_or_create_model(label_key)
        self.y_preds.append(self._predict(model, features))
        self._retrain_if_needed(features, label, label_key)
        return False

    def _start_filtering(self): # return False then start processing
        if self.first_row_flag:
            self.first_row_flag=False
            if self.current_time > self.session_start_date:
                delta=self.current_time-self.session_start_date
                self.session_start_date=self.current_time
                self.session_end_date+=delta
                self.next_rtr_date+=delta
                self.next_eval_date+=delta
                self.s_flag=False
                return False
            elif self.current_time == self.session_start_date:
                self.s_flag = False
                return False
            elif self.current_time < self.session_start_date:
                self.s_flag = True
                return True
            else: pass
        elif self.current_time < self.session_start_date:
            return True
        else:
            self.s_flag = False
            return False

    def _end_filtering(self):# if False keep Processing
        if self.current_time > self.session_end_date:
            print("- < detected end_daytime >")
            self.end_flag = True
            return True
        return False

    def _evaluate_if_needed(self):
        if self.current_time > self.next_eval_date:
            with tf.device("/GPU:0"):
                print("--- evaluate model")
                evaluate_daytime = self.next_eval_date - timedelta(seconds=self.eval_unit_int / 2)
                eval_arr = [evaluate_daytime, self._summarize_label_keys()] + evaluate(self.y_trues, self.y_preds, tf)
                self.eval_results_list = np.vstack([self.eval_results_list, eval_arr])
                self.y_trues.clear()
                self.y_preds.clear()
                self.y_pred_keys.clear()
                self.next_eval_date += timedelta(seconds=self.eval_unit_int)

    def _predict(self, model, features):
        tensor_input = tf.convert_to_tensor([features], dtype=tf.float32)
        prediction_result = model(tensor_input,training=False)[0][0].numpy()
        return prediction_result

    def _retrain_if_needed(self, features, label, label_key):
        pass

    def _resolve_feature_columns(self):
        if self.feature_mode == "zeek":
            return self.feature_schema.get("VECTOR_FEATURES", [])
        if self.feature_mode == "legacy":
            return self.feature_schema.get("LEGACY_FEATURES", [])
        raise ValueError(f"Invalid FeatureSchema MODE: {self.feature_mode}")

    def _resolve_scaling_rules(self):
        if self.feature_mode != "legacy":
            return {
                "log_scale": [
                    "orig_bytes",
                    "resp_bytes",
                    "orig_ip_bytes",
                    "resp_ip_bytes",
                    "orig_pkts",
                    "resp_pkts",
                    "missed_bytes",
                ],
                "log_scale_no_divide": ["duration"],
                "port_bucket": [],
                "interval": [],
                "length": [],
            }
        return {
            "log_scale": [
                "rcv_packet_count",
                "snd_packet_count",
                "tcp_count",
                "udp_count",
                "port_count",
            ],
            "port_bucket": ["most_port"],
            "interval": [
                "rcv_max_interval",
                "rcv_min_interval",
                "snd_max_interval",
                "snd_min_interval",
            ],
            "length": [
                "rcv_max_length",
                "rcv_min_length",
                "snd_max_length",
                "snd_min_length",
            ],
        }

    def _set_column_indices(self):
        header_index = {name: idx for idx, name in enumerate(self.row_headers)}
        if not self.feature_columns:
            raise ValueError("FeatureSchema feature list is empty.")
        if len(set(self.feature_columns)) != len(self.feature_columns):
            raise ValueError("FeatureSchema feature list contains duplicates.")
        missing = [name for name in self.feature_columns if name not in header_index]
        if missing:
            raise ValueError(f"Missing feature columns in CSV: {missing}")
        if self.feature_mode == "zeek":
            label_features = self.feature_schema.get("LABEL_FEATURES", [])
            if len(set(label_features)) != len(label_features):
                raise ValueError("FeatureSchema LABEL_FEATURES contains duplicates.")
            missing_label_features = [
                name for name in label_features if name not in header_index
            ]
            if missing_label_features:
                raise ValueError(
                    f"Missing label feature columns in CSV: {missing_label_features}"
                )
            overlap = set(label_features) & set(self.feature_columns)
            if overlap:
                raise ValueError(
                    f"LABEL_FEATURES must not overlap VECTOR_FEATURES: {sorted(overlap)}"
                )
            self.label_feature_indices = [header_index[name] for name in label_features]
        self.feature_indices = [header_index[name] for name in self.feature_columns]
        if self.label_column not in header_index:
            raise ValueError(f"Missing label column in CSV: {self.label_column}")
        self.label_index = header_index[self.label_column]
        if self.label_index in self.feature_indices:
            raise ValueError("LABEL_COLUMN must not be included in feature columns.")

    def _extract_features(self, row):
        features = []
        for i in self.feature_indices:
            value = row[i]
            try:
                col_name = self.row_headers[i] if i < len(self.row_headers) else ""
                if value == "" and col_name in (
                    "duration",
                    "orig_bytes",
                    "resp_bytes",
                    "orig_pkts",
                    "resp_pkts",
                    "orig_ip_bytes",
                    "resp_ip_bytes",
                    "missed_bytes",
                ):
                    features.append(0.0)
                    continue
                if col_name in ("local_orig", "local_resp"):
                    features.append(float(self._coerce_bool(value)))
                else:
                    features.append(float(value))
            except (TypeError, ValueError):
                col_name = self.row_headers[i] if i < len(self.row_headers) else f"index {i}"
                raise ValueError(f"Non-numeric feature value in column '{col_name}': {value}")
        return features

    def _extract_label(self, row):
        value = row[self.label_index]
        try:
            return int(float(value))
        except (TypeError, ValueError):
            col_name = self.row_headers[self.label_index]
            raise ValueError(f"Non-numeric label value in column '{col_name}': {value}")

    def _coerce_bool(self, value):
        if isinstance(value, bool):
            return 1 if value else 0
        if value is None:
            raise ValueError("Missing boolean value.")
        normalized = str(value).strip().lower()
        if normalized in ("1", "true", "t", "yes", "y"):
            return 1
        if normalized in ("0", "false", "f", "no", "n"):
            return 0
        raise ValueError(f"Invalid boolean value: {value}")

    def _make_label_key(self, row):
        if self.feature_mode != "zeek":
            return "default"
        values = []
        for idx in self.label_feature_indices:
            value = row[idx]
            values.append("" if value is None else str(value))
        return "|".join(values) if values else "default"

    def _summarize_label_keys(self):
        if not self.y_pred_keys:
            return "none"
        unique = sorted(set(self.y_pred_keys))
        if len(unique) == 1:
            return unique[0]
        return f"mixed:{len(unique)}"

    def _sanitize_key(self, key):
        return re.sub(r"[^A-Za-z0-9._-]+", "_", key).strip("_") or "default"

    def _get_or_create_model(self, label_key):
        if self.feature_mode != "zeek":
            return self.model_registry["default"]
        if label_key not in self.model_registry:
            self.model_registry[label_key] = self.model_factory.create_model()
        return self.model_registry[label_key]

    def _get_output_dir_for_key(self, label_key, window_count=0):
        if self.feature_mode != "zeek":
            return self.output_path
        if label_key in self.key_output_paths:
            return self.key_output_paths[label_key]
        safe_key = self._sanitize_key(label_key)
        key_dir = os.path.join(self.output_path, "keys", safe_key)
        os.makedirs(key_dir, exist_ok=True)
        if window_count:
            for i in range(window_count):
                os.makedirs(os.path.join(key_dir, f"m{i}_weights"), exist_ok=True)
        else:
            os.makedirs(os.path.join(key_dir, "m1_weights"), exist_ok=True)
        self.key_output_paths[label_key] = key_dir
        return key_dir

    def _append_training_result(self, label_key, window_index, tr_results_array):
        if self.feature_mode != "zeek":
            while len(self.tr_results_list) <= window_index:
                self.tr_results_list.append([])
            self.tr_results_list[window_index].append(tr_results_array)
            return
        if label_key not in self.tr_results_list:
            self.tr_results_list[label_key] = []
        while len(self.tr_results_list[label_key]) <= window_index:
            self.tr_results_list[label_key].append([])
        self.tr_results_list[label_key][window_index].append(tr_results_array)

class DynamicSession(NoRetrainSession):
    def __init__(self, loader, model_factory, tr_results_list, eval_results_list, output_path):
        super().__init__(loader, model_factory, tr_results_list, eval_results_list, output_path)
        self.dd_settings = loader.get('DriftDetection')
        self.window_managers = {}
        self.default_wm = WindowManager(
            self.model_registry["default"],
            self.dd_settings.get('WindowConfig'),
            self.dd_settings.get("ENSEMBLE_METHOD_CODE"),
            self.feature_columns,
            self.scaling_rules,
        )
        self.window_managers["default"] = self.default_wm
        for i in range(len(self.default_wm.windows)):
            os.makedirs(f"{self.output_path}/m{i}_weights", exist_ok=True)
        first_wait = self.default_wm.calc_first_wait_seconds()
        self.next_dd_date_by_key = {"default": self.session_start_date + timedelta(seconds=first_wait)}

    def _handle_row(self, row):
        self.current_time = datetime.strptime(row[self.row_headers.index("daytime")], "%Y-%m-%d %H:%M:%S")
        if self.session_start_flag and self._start_filtering():
            return False
        if self._end_filtering(): return True
        self._evaluate_if_needed()
        features = self._extract_features(row)
        label = self._extract_label(row)
        self.y_trues.append(label)
        label_key = self._make_label_key(row)
        self.y_pred_keys.append(label_key)
        wm = self._get_or_create_window_manager(label_key)
        for i, window in enumerate(wm.windows):
            wm.y_pred_arr[i].append(self._predict(window.model, features))
            self._retrain_if_needed_for_dd(features, label, window, i, label_key)
        self.y_preds.append(wm.ensemble_window_results())
        return False

    def _retrain_if_needed_for_dd(self, features, label, window, i, label_key):
        next_dd_date = self.next_dd_date_by_key.get(label_key)
        if next_dd_date is None:
            next_dd_date = self.session_start_date + timedelta(
                seconds=self.window_managers[label_key].calc_first_wait_seconds()
            )
            self.next_dd_date_by_key[label_key] = next_dd_date
        if self.current_time > next_dd_date:
            with tf.device("/GPU:0"):
                if window.detect():
                    output_dir = self._get_output_dir_for_key(
                        label_key, window_count=len(self.default_wm.windows)
                    )
                    window.model, tr_results_array = train(
                        window.model, window.cw, output_dir,
                        self.epochs, self.batch_size, self.current_time, i
                    )
                    self._append_training_result(label_key, i, tr_results_array)
            self.next_dd_date_by_key[label_key] = next_dd_date + timedelta(
                seconds=self.dd_settings.get('DRIFT_DETECTION_UNIT_INTERVAL')
            )
        self.window_managers[label_key].update_all(features + [label], self.current_time)

    def _get_or_create_window_manager(self, label_key):
        if self.feature_mode != "zeek":
            return self.default_wm
        if label_key not in self.window_managers:
            model = self._get_or_create_model(label_key)
            wm = WindowManager(
                model,
                self.dd_settings.get('WindowConfig'),
                self.dd_settings.get("ENSEMBLE_METHOD_CODE"),
                self.feature_columns,
                self.scaling_rules,
            )
            self.window_managers[label_key] = wm
            self._get_output_dir_for_key(label_key, window_count=len(wm.windows))
            self.next_dd_date_by_key[label_key] = self.session_start_date + timedelta(
                seconds=wm.calc_first_wait_seconds()
            )
        return self.window_managers[label_key]

class StaticSession(NoRetrainSession):
    def __init__(self, loader, model_factory, tr_results_list, eval_results_list, output_path):
        super().__init__(loader, model_factory, tr_results_list, eval_results_list, output_path)
        self.rtr_list = {} if self.feature_mode == "zeek" else []

    def _retrain_if_needed(self, features, label, label_key):
        if self.current_time > self.next_rtr_date:
            with tf.device("/GPU:0"):
                if self.feature_mode == "zeek":
                    for key, rows in list(self.rtr_list.items()):
                        if not rows:
                            continue
                        model = self._get_or_create_model(key)
                        output_dir = self._get_output_dir_for_key(key)
                        model, tr_results_array = train(
                            model, rows, output_dir, self.epochs, self.batch_size, self.current_time
                        )
                        self._append_training_result(key, 0, tr_results_array)
                    self.rtr_list = {}
                else:
                    self.model_registry["default"], tr_results_array = train(
                        self.model_registry["default"], self.rtr_list, self.output_path, self.epochs,
                        self.batch_size, self.current_time
                    )
                    self.rtr_list = []
                    # 動的にリストを拡張（最初だけ）
                    if len(self.tr_results_list) == 0:
                        self.tr_results_list.append([])
                    self.tr_results_list[0].append(tr_results_array)
            self.next_rtr_date += timedelta(seconds=self.rtr_int)
        if self.feature_mode == "zeek":
            self.rtr_list.setdefault(label_key, []).append(np.array(features + [label], dtype=float))
        else:
            self.rtr_list.append(np.array(features + [label], dtype=float))
