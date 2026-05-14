from __future__ import annotations

import argparse

from .runtime import LiveRuntime
from .settings_loader import LiveSettingsLoader


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the no-retrain live IDS PoC.")
    parser.add_argument(
        "--settings",
        help="Path to src/main/Live/settings.json. Defaults to the package-local settings file.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    loader = LiveSettingsLoader(path=args.settings)
    runtime = LiveRuntime(loader)
    runtime.run()


if __name__ == "__main__":
    main()
