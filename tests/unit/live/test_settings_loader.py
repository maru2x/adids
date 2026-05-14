import json
from pathlib import Path

from src.main.Live.settings_loader import LiveSettingsLoader


def test_live_settings_loader_supports_external_settings_path(tmp_path):
    settings_path = tmp_path / "live_settings.json"
    settings_path.write_text(
        json.dumps(
            {
                "OS": {
                    "TF_CPP_MIN_LOG_LEVEL": "3",
                    "TF_FORCE_GPU_ALLOW_GROWTH": "true",
                    "CUDA_VISIBLE_DEVICES": "-1",
                },
                "FeatureSchema": {
                    "VECTOR_FEATURES": ["duration", "orig_bytes"],
                },
                "FEATURE_EXPORT_INPUT_DIR_PATH": "data/logs/zeek/live/local_iot/current",
            }
        ),
        encoding="utf-8",
    )

    loader = LiveSettingsLoader(path=str(settings_path))

    assert loader.settings_path == settings_path.resolve()
    assert loader.resolve_input_dim() == 2
    assert loader.resolve_path("FEATURE_EXPORT_INPUT_DIR_PATH") == (
        Path("/home/mnl/adids") / "data/logs/zeek/live/local_iot/current"
    )
