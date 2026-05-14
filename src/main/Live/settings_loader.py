from __future__ import annotations

import json
import os
from pathlib import Path


class LiveSettingsLoader:
    def __init__(self, path: str | None = None):
        self.package_dir = Path(__file__).resolve().parent
        self.project_root = self.package_dir.parents[2]
        if path is None:
            path = str(self.package_dir / "settings.json")
        with open(path, "r", encoding="utf-8") as fh:
            self.settings = json.load(fh)
        self.settings_path = Path(path).resolve()
        self._configure_environment()

    def _configure_environment(self) -> None:
        os_settings = self.settings.get("OS", {})
        for key in ("TF_CPP_MIN_LOG_LEVEL", "TF_FORCE_GPU_ALLOW_GROWTH", "CUDA_VISIBLE_DEVICES"):
            value = os_settings.get(key)
            if value is not None:
                os.environ[key] = str(value)

    def get(self, key: str, default=None):
        return self.settings.get(key, default)

    def resolve_path(self, key: str) -> Path:
        raw_value = self.settings[key]
        path = Path(raw_value).expanduser()
        if path.is_absolute():
            return path
        return (self.project_root / path).resolve()

    def resolve_optional_path(self, key: str) -> Path | None:
        raw_value = self.settings.get(key)
        if raw_value in (None, ""):
            return None
        path = Path(raw_value).expanduser()
        if path.is_absolute():
            return path
        return (self.project_root / path).resolve()

    def resolve_input_dim(self) -> int:
        feature_schema = self.settings.get("FeatureSchema", {})
        vector_features = feature_schema.get("VECTOR_FEATURES", [])
        if not vector_features:
            raise ValueError("Live FeatureSchema VECTOR_FEATURES is empty.")
        return len(vector_features)
