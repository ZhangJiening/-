"""Run real Windows binaries with separate test data; preserve verification evidence."""
import argparse
import os
import subprocess
import shutil
from pathlib import Path
from erlead import __version__
from erlead.storage import digest, read_json, utc_now, write_json

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("--install", action="store_true", help="Install and check the exact local installer")
parser.add_argument("--headless", action="store_true", help="Check real binaries without desktop input or visible windows")
args = parser.parse_args()
expected_platform = "offscreen" if args.headless else "windows"
exe = root / "dist/ERLeadPlatform/ERLeadPlatform.exe"
run_id = utc_now().replace(":", "-")
runtime = root / "reports" / ("ui-runtime-" + __version__ + "-" + run_id)
runtime.mkdir(parents=True)
environment = dict(os.environ, QT_QPA_PLATFORM=expected_platform)
if args.headless:
    # The offscreen plugin does not enumerate the Windows font registry. Stage
    # local system faces for QA; none of these files enter the distribution.
    font_source = Path(os.environ.get("SystemRoot", "C:/Windows")) / "Fonts"
    font_directory = runtime / "qa-system-fonts"
    font_directory.mkdir()
    for filename in ("msyh.ttc", "msyhbd.ttc", "segoeui.ttf", "segoeuib.ttf", "seguisym.ttf"):
        source = font_source / filename
        if source.exists():
            shutil.copy2(source, font_directory / (source.stem + ".ttf"))
    environment["QT_QPA_FONTDIR"] = str(font_directory)


def run(binary, command, output):
    subprocess.run([str(binary), command, "--workspace", str(runtime), "--output", str(output)],
                   env=environment, check=True, timeout=180)
    proof = read_json(output)
    if proof["status"] != "passed":
        raise RuntimeError(str(proof))
    if args.headless and command == "desktop-test":
        fonts = proof.get("fonts", {})
        if "YaHei" not in fonts.get("body", "") or "YaHei" not in fonts.get("mixed_caption", ""):
            raise RuntimeError("后台中文字体未正确加载，不能交付此渲染图")
    proof["verification_mode"] = "headless_Qt_business_check" if args.headless else "native_windows_Qt"
    if args.headless:
        proof["checks"] = ["offscreen_Qt_window" if check == "native_Qt_window" else check for check in proof.get("checks", [])]
    return proof


if args.install:
    installer = root / "release/installer" / f"ERLeadPlatform-Setup-{__version__}.exe"
    installed = root / "reports/installer-test" / __version__ / "app"
    install_log = root / "reports" / f"ui-{__version__}-install.log"
    subprocess.run([str(installer), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/NOICONS",
                    "/DIR=" + str(installed), "/LOG=" + str(install_log)], check=True, timeout=180)
    installed_exe = installed / "ERLeadPlatform.exe"
    if not installed_exe.exists() or digest(installed_exe) != digest(exe):
        raise RuntimeError("安装版EXE缺失或与待交付EXE不一致")
    for name in (f"使用说明-{__version__}.md", "ERLeadPlatform-User-Guide.pdf", "ERLeadPlatform-User-Guide.docx"):
        if not (installed / "docs/user-guide" / name).is_file():
            raise RuntimeError("安装说明缺失：" + name)
    output = root / "reports" / f"ui-{__version__}-installer.json"
    proof = run(installed_exe, "desktop-test", output)
    if proof["app_version"] != __version__ or not proof["frozen"] or proof["qt_platform"] != expected_platform:
        raise RuntimeError("未验证到当前Windows安装版本或指定Qt运行模式")
    model = installed / "seed_models" / proof["model_version"]
    report = read_json(model / "report.json")
    checksums = {name: digest(model / name) for name in report["artifact_sha256"]}
    if checksums != report["artifact_sha256"]:
        raise RuntimeError("安装后的模型文件校验失败")
    proof.update(executable_sha256=digest(installed_exe), installer_sha256=digest(installer),
                 installed_directory=str(installed), model_checksums=checksums)
    write_json(output, proof)
else:
    output = root / "reports" / f"ui-{__version__}-frozen.json"
    proof = run(exe, "desktop-test", output)
    if proof["app_version"] != __version__ or not proof["frozen"] or proof["qt_platform"] != expected_platform:
        raise RuntimeError("未验证到当前Windows发行版本或指定Qt运行模式")
    proof["executable_sha256"] = digest(exe)
    write_json(output, proof)
    write_json(root / "reports/portable-verification.json", proof)
    run(exe, "self-test", root / "reports" / f"ui-{__version__}-self-test.json")
print(proof["status"], output)
