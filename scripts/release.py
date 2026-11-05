from __future__ import annotations
import importlib.metadata
import shutil
import sys
import zipfile
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
from erlead import __version__
from erlead.storage import digest, model_location, read_json, utc_now, workspace, write_json

root = workspace()
dist = root / "dist" / "ERLeadPlatform"
if not (dist / "ERLeadPlatform.exe").exists():
    raise SystemExit("先执行build_windows.ps1生成Windows程序")
models = model_location(root)
seed = dist / "seed_models"
if not seed.exists():
    seed.mkdir()
shutil.copytree(models, seed / models.name, dirs_exist_ok=True)
write_json(seed / "current.json", {"run_id": models.name})
for name in ("README.md", "LICENSE", "THIRD_PARTY_NOTICES.md"):
    shutil.copy2(root / name, dist / name)
shutil.copytree(root / "docs", dist / "docs", dirs_exist_ok=True)
licences = dist / "THIRD_PARTY_LICENSES"
python_licence = Path(sys.base_prefix) / "LICENSE.txt"
if python_licence.exists():
    (licences / "Python").mkdir(parents=True, exist_ok=True)
    shutil.copy2(python_licence, licences / "Python/LICENSE.txt")
versions = {}
for distribution in importlib.metadata.distributions():
    name = distribution.metadata["Name"]
    versions[name] = {"version": distribution.version,
                      "licence": distribution.metadata.get("License-Expression") or distribution.metadata.get("License")}
    for relative in distribution.files or []:
        if any(term in str(relative).lower() for term in ("license", "licence", "copying", "copyright")):
            source = Path(distribution.locate_file(relative))
            if source.is_file() and source.suffix.lower() not in (".py", ".pyc", ".pyd"):
                target = licences / name / str(relative).replace("../", "").replace("..\\", "")
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
write_json(licences / "versions.json", versions)
release = root / "release"
release.mkdir(exist_ok=True)
tag = f"ERLeadPlatform-{__version__}-" + datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y%m%d-%H%M%S")
portable = release / (tag + "-Windows-x64.zip")
with zipfile.ZipFile(portable, "w", zipfile.ZIP_DEFLATED) as archive:
    for path in sorted(dist.rglob("*")):
        if path.is_file():
            archive.write(path, "ERLeadPlatform/" + path.relative_to(dist).as_posix())
source_zip = release / (tag + "-Source.zip")
allow_files = ["README.md", "LICENSE", "THIRD_PARTY_NOTICES.md", "requirements.lock.txt", "pyproject.toml", "run.py", "启动平台.cmd", "build_windows.ps1", "build_installer.ps1", ".gitignore"]
with zipfile.ZipFile(source_zip, "w", zipfile.ZIP_DEFLATED) as archive:
    for name in allow_files:
        archive.write(root / name, name)
    for directory in ("assets", "src", "tests", "scripts", "docs"):
        for path in sorted((root / directory).rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc" and ".egg-info" not in str(path):
                archive.write(path, path.relative_to(root).as_posix())
exe_checksum = digest(dist / "ERLeadPlatform.exe")
proof_path = root / "reports/portable-verification.json"
proof = read_json(proof_path) if proof_path.exists() else None
verified = bool(proof and proof.get("status") == "passed" and proof.get("executable_sha256") == exe_checksum)
manifest = {"created_at": utc_now(), "version": __version__, "model_version": models.name,
            "executable_sha256": exe_checksum, "tested_executable_matches": verified,
            "packages": {p.name: {"sha256": digest(p), "bytes": p.stat().st_size} for p in (portable, source_zip)}}
write_json(release / "manifest.json", manifest)
print(portable)
print(source_zip)
