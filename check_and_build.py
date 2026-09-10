"""Legacy Nimbus build command."""

import argparse
from font_match.cli import main as cli


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="Rebuild local outputs")
    parser.add_argument("--work-dir", default="build_temp")
    parser.add_argument("--out-dir", default="dist")
    args = parser.parse_args()
    inputs = args.work_dir + "/inputs.json"
    cli(["resolve", "--out", inputs])
    cli(
        [
            "build",
            "--family",
            "nimbus-match",
            "--inputs",
            inputs,
            "--out-dir",
            args.out_dir,
        ]
    )


if __name__ == "__main__":
    main()
