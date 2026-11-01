from __future__ import annotations
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def workspace() -> Path:
    if os.environ.get("ERLEAD_WORKSPACE"):
        return Path(os.environ["ERLEAD_WORKSPACE"]).resolve()
    if getattr(sys, "frozen", False):
        return Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "ERLeadPlatform"
    return Path(__file__).resolve().parents[2]


def asset_location(name: str) -> Path:
    """Locate a packaged read-only asset in source and frozen layouts."""
    if Path(name).name != name or not name:
        raise ValueError("asset name must be a single file name")
    candidates = []
    if getattr(sys, "frozen", False):
        candidates.extend((Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)) / "assets" / name,
                          Path(sys.executable).parent / "assets" / name))
    candidates.append(workspace() / "assets" / name)
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"找不到程序资源：{name}")


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    os.replace(temp, path)


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def model_location(root: Path | None = None) -> Path:
    root = root or workspace()
    pointer = root / "models" / "current.json"
    if not pointer.exists() and getattr(sys, "frozen", False):
        pointer = Path(sys.executable).parent / "seed_models" / "current.json"
    if not pointer.exists():
        raise ValueError("尚无模型，请先准备数据并完成训练，或选择已验证的模型目录。")
    run_id = read_json(pointer)["run_id"]
    if Path(run_id).name != run_id or run_id in (".", ".."):
        raise ValueError("模型版本索引无效")
    return pointer.parent / run_id
