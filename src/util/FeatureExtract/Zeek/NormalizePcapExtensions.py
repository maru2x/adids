#!/usr/bin/env python3
"""Recursively append .pcap to extensionless files under a directory."""

from __future__ import annotations

import argparse
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Recursively rename extensionless files under the given directory "
            "by appending .pcap."
        )
    )
    parser.add_argument(
        "root_dir",
        help="Directory to scan recursively.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned renames without modifying files.",
    )
    return parser.parse_args()


def resolve_root_dir(path_str: str) -> Path:
    root_dir = Path(path_str).expanduser().resolve()
    if not root_dir.exists():
        raise SystemExit(f"Input path not found: {root_dir}")
    if not root_dir.is_dir():
        raise SystemExit(f"Expected a directory: {root_dir}")
    return root_dir


def collect_extensionless_files(root_dir: Path) -> list[Path]:
    return sorted(
        path
        for path in root_dir.rglob("*")
        if path.is_file() and path.suffix == ""
    )


def build_rename_pairs(files: list[Path]) -> list[tuple[Path, Path]]:
    pairs: list[tuple[Path, Path]] = []
    seen_targets: set[Path] = set()

    for source in files:
        target = source.with_name(f"{source.name}.pcap")
        if target.exists():
            raise SystemExit(f"Target already exists: {target}")
        if target in seen_targets:
            raise SystemExit(f"Duplicate target would be created: {target}")
        seen_targets.add(target)
        pairs.append((source, target))

    return pairs


def rename_files(pairs: list[tuple[Path, Path]], *, dry_run: bool) -> int:
    for source, target in pairs:
        print(f"{source} -> {target}")
        if not dry_run:
            source.rename(target)
    return len(pairs)


def main() -> None:
    args = parse_args()
    root_dir = resolve_root_dir(args.root_dir)
    files = collect_extensionless_files(root_dir)
    pairs = build_rename_pairs(files)

    if not pairs:
        print(f"No extensionless files found under {root_dir}")
        return

    count = rename_files(pairs, dry_run=args.dry_run)
    action = "Would rename" if args.dry_run else "Renamed"
    print(f"{action} {count} files under {root_dir}")


if __name__ == "__main__":
    main()
