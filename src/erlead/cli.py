from __future__ import annotations
import argparse
import json
from pathlib import Path
from .storage import model_location, workspace, write_json


def main():
    parser = argparse.ArgumentParser(description="ERalpha real activity training and screening")
    parser.add_argument("command", choices=("prepare", "train", "predict", "gui", "self-test", "desktop-test"), nargs="?", default="gui")
    parser.add_argument("--workspace", type=Path)
    parser.add_argument("--csv", type=Path)
    parser.add_argument("--source", default="")
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--smiles", default="CCO")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = args.workspace.resolve() if args.workspace else workspace()
    if args.command == "prepare":
        from .data import prepare
        result = prepare(root, csv_path=args.csv, source_note=args.source, refresh=args.refresh)
    elif args.command == "train":
        from .training import train
        result = {"model_directory": str(train(root))}
    elif args.command == "predict":
        from .training import load_bundle, predict
        from .screening import screen
        result = predict(args.smiles, load_bundle(model_location(root)))
        result["screening"] = screen(result["ensemble_pIC50"])
    elif args.command == "self-test":
        from .selftest import self_test
        result = self_test(root)
    elif args.command == "desktop-test":
        from .desktopcheck import run_check
        result = run_check(root)
    else:
        from .ui import launch
        return launch(root)
    if args.output:
        write_json(args.output, result)
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
