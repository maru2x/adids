from __future__ import annotations

import sys
import time
from dataclasses import dataclass
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_DIR.parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.util.FeatureExtract.Zeek import feature_exporter

from .csv_cursor import LiveCsvCursor
from .demo_model import ensure_demo_model


NUMERIC_ZERO_DEFAULT_COLUMNS = {
    "duration",
    "orig_bytes",
    "resp_bytes",
    "orig_pkts",
    "resp_pkts",
    "orig_ip_bytes",
    "resp_ip_bytes",
    "missed_bytes",
}
BOOLEAN_COLUMNS = {"local_orig", "local_resp"}


@dataclass
class LiveAlert:
    event_time: str
    src_ip: str
    dst_ip: str
    dst_port: str
    proto: str
    conn_state: str
    score: float
    label_key: str
    source_type: str


class LiveRuntime:
    def __init__(self, loader):
        self.loader = loader
        self.feature_schema = loader.get("FeatureSchema", {})
        self.vector_features = self.feature_schema.get("VECTOR_FEATURES", [])
        self.label_features = self.feature_schema.get("LABEL_FEATURES", [])
        self.label_column = self.feature_schema.get("LABEL_COLUMN", "label")
        self.input_dir = loader.resolve_path("FEATURE_EXPORT_INPUT_DIR_PATH")
        self.output_dir = loader.resolve_path("FEATURE_EXPORT_OUTPUT_DIR_PATH")
        self.export_state_path = loader.resolve_path("FEATURE_EXPORT_STATE_PATH")
        self.cursor_state_path = loader.resolve_path("LIVE_CURSOR_STATE_PATH")
        self.runtime_settings_path = loader.resolve_optional_path("SIMULATION_SETTINGS_PATH")
        self.output_chunk_size = int(loader.get("FEATURE_EXPORT_OUTPUT_CHUNK_SIZE", 200))
        self.fixed_label = int(loader.get("FEATURE_EXPORT_LABEL", 0))
        self.validate_output = bool(loader.get("FEATURE_EXPORT_VALIDATE_OUTPUT", False))
        self.initial_position = str(loader.get("INITIAL_POSITION", "end")).lower()
        self.poll_interval_seconds = float(loader.get("POLL_INTERVAL_SECONDS", 1.0))
        self.max_polls = loader.get("MAX_POLLS")
        self.alert_threshold = float(loader.get("ALERT_THRESHOLD", 0.5))
        self.idle_log_every_polls = int(loader.get("IDLE_LOG_EVERY_POLLS", 30))
        self.source_type = str(loader.get("SOURCE_TYPE", "local_iot_demo"))
        self.target_ports = {
            int(port)
            for port in loader.get("TARGET_PORTS", [])
        }
        self.target_protocols = {
            str(proto).lower()
            for proto in loader.get("TARGET_PROTOCOLS", [])
        }
        self.target_conn_states = {
            str(conn_state)
            for conn_state in loader.get("TARGET_CONN_STATES", [])
        }
        self.cursor = LiveCsvCursor(
            self.output_dir,
            self.cursor_state_path,
            initial_position=self.initial_position,
        )
        self.poll_count = 0
        self.total_scored_rows = 0
        self.total_alert_count = 0
        self._prepare_model()

    def _prepare_model(self) -> None:
        import tensorflow as tf
        try:
            from Simulation.model_factory import ModelFactory
        except ModuleNotFoundError:
            from src.main.Simulation.model_factory import ModelFactory

        self.tf = tf
        foundation_model_path = self.loader.resolve_path("FOUNDATION_MODEL_PATH")
        if not foundation_model_path.exists():
            if not self.loader.get("AUTO_CREATE_DEMO_MODEL", True):
                raise FileNotFoundError(f"Live foundation model not found: {foundation_model_path}")
            ensure_demo_model(
                foundation_model_path,
                model_code=int(self.loader.get("MODEL_CODE")),
                input_dim=self.loader.resolve_input_dim(),
            )
        self.loader.settings["FOUNDATION_MODEL_PATH"] = str(foundation_model_path)
        self.loader.settings["USER_DIR"] = str(PROJECT_ROOT)
        self.model_factory = ModelFactory(
            model_code=int(self.loader.get("MODEL_CODE")),
            user_dir_path=str(PROJECT_ROOT),
            foundation_model_path=str(foundation_model_path),
            input_dim=self.loader.resolve_input_dim(),
        )
        self.model = self.model_factory.foundation_model

    def run(self) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.export_state_path.parent.mkdir(parents=True, exist_ok=True)
        self.cursor_state_path.parent.mkdir(parents=True, exist_ok=True)
        self._prime_export_state_if_needed()

        print(
            "[run-live] 開始: "
            f"入力={self.input_dir} / 出力={self.output_dir} / threshold={self.alert_threshold} "
            f"/ ports={sorted(self.target_ports)} / protos={sorted(self.target_protocols)}"
        )

        try:
            while True:
                self.poll_count += 1
                export_stats = self._poll_feature_export()
                new_rows = self.cursor.collect_new_rows()
                scored_rows = 0
                alert_count = 0

                for row in new_rows:
                    if not self._row_matches_target(row):
                        continue
                    scored_rows += 1
                    score = self._predict_row(row)
                    if score < self.alert_threshold:
                        continue
                    alert_count += 1
                    self.total_alert_count += 1
                    alert = self._build_alert(row, score)
                    self._print_alert(alert)

                self.total_scored_rows += scored_rows
                if scored_rows or export_stats.emitted_row_count or alert_count:
                    print(
                        "[run-live] poll 完了: "
                        f"poll={self.poll_count} / export_rows={export_stats.emitted_row_count} "
                        f"/ new_csv_rows={len(new_rows)} / scored={scored_rows} / alerts={alert_count}"
                    )
                elif self.poll_count % self.idle_log_every_polls == 0:
                    print(
                        "[run-live] idle: "
                        f"poll={self.poll_count} / total_scored={self.total_scored_rows} "
                        f"/ total_alerts={self.total_alert_count}"
                    )

                if self.max_polls is not None and self.poll_count >= int(self.max_polls):
                    print("[run-live] MAX_POLLS に到達したため終了します")
                    break
                time.sleep(self.poll_interval_seconds)
        except KeyboardInterrupt:
            print("[run-live] Ctrl-C を受けたため終了します")

    def _prime_export_state_if_needed(self) -> None:
        if self.initial_position != "end":
            return
        if self.export_state_path.exists():
            return
        if any(self.output_dir.glob("*.csv")):
            raise SystemExit(
                f"Live feature output dir already has CSV files but no export state: {self.output_dir}. "
                "Remove the stale CSVs or restore the paired state file first."
            )
        conn_log_path = self.input_dir / feature_exporter.CONN_LOG_NAME
        if not conn_log_path.exists():
            return
        stat = conn_log_path.stat()
        initial_state = feature_exporter.LiveExportState(
            source_inode=stat.st_ino,
            offset=stat.st_size,
        )
        feature_exporter.save_live_state(self.export_state_path, initial_state)

    def _poll_feature_export(self):
        stats = feature_exporter.export_live_conn_log_with_state(
            self.input_dir,
            self.output_dir,
            fixed_label=self.fixed_label,
            output_chunk_size=self.output_chunk_size,
            state_path=self.export_state_path,
        )
        if self.validate_output and stats.emitted_row_count > 0 and self.runtime_settings_path is not None:
            feature_exporter.validate_runtime_csv_output(
                self.output_dir,
                runtime_settings_path=self.runtime_settings_path,
                caller_tag="[run-live]",
            )
        return stats

    def _row_matches_target(self, row: dict[str, str]) -> bool:
        if self.target_protocols:
            proto = str(row.get("proto", "")).lower()
            if proto not in self.target_protocols:
                return False
        if self.target_ports:
            try:
                dst_port = int(float(row.get("id.resp_p", "")))
            except (TypeError, ValueError):
                return False
            if dst_port not in self.target_ports:
                return False
        if self.target_conn_states:
            conn_state = str(row.get("conn_state", ""))
            if conn_state not in self.target_conn_states:
                return False
        return True

    def _predict_row(self, row: dict[str, str]) -> float:
        features = []
        for column in self.vector_features:
            value = row.get(column, "")
            if value == "" and column in NUMERIC_ZERO_DEFAULT_COLUMNS:
                features.append(0.0)
                continue
            if column in BOOLEAN_COLUMNS:
                features.append(float(self._coerce_bool(value)))
                continue
            try:
                features.append(float(value))
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Non-numeric live feature value in column '{column}': {value}") from exc
        tensor_input = self.tf.convert_to_tensor([features], dtype=self.tf.float32)
        return float(self.model(tensor_input, training=False)[0][0].numpy())

    def _coerce_bool(self, value) -> int:
        if isinstance(value, bool):
            return 1 if value else 0
        normalized = str(value).strip().lower()
        if normalized in ("1", "true", "t", "yes", "y"):
            return 1
        if normalized in ("0", "false", "f", "no", "n"):
            return 0
        raise ValueError(f"Invalid boolean value: {value}")

    def _build_alert(self, row: dict[str, str], score: float) -> LiveAlert:
        label_key = self._build_label_key(row)
        return LiveAlert(
            event_time=str(row.get("daytime", "")),
            src_ip=str(row.get("id.orig_h", "")),
            dst_ip=str(row.get("id.resp_h", "")),
            dst_port=str(row.get("id.resp_p", "")),
            proto=str(row.get("proto", "")),
            conn_state=str(row.get("conn_state", "")),
            score=score,
            label_key=label_key,
            source_type=self.source_type,
        )

    def _build_label_key(self, row: dict[str, str]) -> str:
        if not self.label_features:
            return "default"
        values = [str(row.get(column, "")) for column in self.label_features]
        return "|".join(values) if values else "default"

    def _print_alert(self, alert: LiveAlert) -> None:
        print(
            "[ALERT] "
            f"event_time={alert.event_time} src_ip={alert.src_ip} dst_ip={alert.dst_ip} "
            f"dst_port={alert.dst_port} proto={alert.proto} conn_state={alert.conn_state} "
            f"score={alert.score:.4f} label_key={alert.label_key} source_type={alert.source_type}"
        )
