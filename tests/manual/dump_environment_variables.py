import json
import os
from pathlib import Path


def dump_environment_variables():
    output_path = Path(__file__).with_name("environment_variables.json")
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(dict(os.environ), f, indent=4)


if __name__ == "__main__":
    dump_environment_variables()

