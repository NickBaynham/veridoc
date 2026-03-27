"""CLI entry point for veridoc."""

from __future__ import annotations

import argparse
import os

from veridoc import __version__


def main() -> None:
    parser = argparse.ArgumentParser(prog="veridoc", description="Document Intelligence Platform")
    parser.add_argument(
        "--config-dir",
        default=os.environ.get("VERIDOC_CONFIG_DIR", "config"),
        help=(
            "Directory containing application configuration (default: config or VERIDOC_CONFIG_DIR)"
        ),
    )
    args = parser.parse_args()
    print(f"veridoc {__version__} (config dir: {args.config_dir})")


if __name__ == "__main__":
    main()
