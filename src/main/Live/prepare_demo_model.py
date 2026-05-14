from __future__ import annotations

import argparse

from .demo_model import ensure_demo_model
from .settings_loader import LiveSettingsLoader


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create the default live demo model file.")
    parser.add_argument(
        "--settings",
        help="Path to src/main/Live/settings.json. Defaults to the package-local settings file.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    loader = LiveSettingsLoader(path=args.settings)
    model_path = loader.resolve_path("FOUNDATION_MODEL_PATH")
    ensure_demo_model(
        model_path,
        model_code=int(loader.get("MODEL_CODE")),
        input_dim=loader.resolve_input_dim(),
    )
    print(f"[prepare-live-demo-model] model ready: {model_path}")


if __name__ == "__main__":
    main()
