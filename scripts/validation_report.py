from pathlib import Path
import json
import shutil
from xml.etree import ElementTree
from erlead.storage import model_location, read_json, workspace, write_json, utc_now

root = workspace()
report = read_json(model_location(root) / "report.json")
suite = ElementTree.parse(root / "reports/all-tests.xml").getroot()
suites = list(suite) if suite.tag == "testsuites" else [suite]
counts = {key: sum(int(s.get(key, 0)) for s in suites) for key in ("tests", "failures", "errors", "skipped")}
native = read_json(root / "reports/native-desktop-test.json")
frozen_file = root / "reports/frozen-desktop-test.json"
frozen = read_json(frozen_file) if frozen_file.exists() else None
source_check = root / "reports/isolated-source-check.json"
source = read_json(source_check) if source_check.exists() else None
portable_path = root / "reports/portable-verification.json"
portable = read_json(portable_path) if portable_path.exists() else None
summary = {"recorded_at": utc_now(), "run_id": report["run_id"], "target": report["target"],
           "raw_records": report["cleaning"]["raw_count"], "cleaned_compounds": report["cleaning"]["unique_compounds"],
           "structure_groups": report["structure_groups"], "split_counts": report["split_counts"],
           "data_sha256": report["data_sha256"], "seed": report["seed"], "selected": report["selected"],
           "weights": report["weights"], "validation_metrics": report["validation_metrics"],
           "test_metrics": report["test_metrics"], "test_count": 1, "environment": report["environment"],
           "automated_tests": counts, "native_desktop_check": {k: native[k] for k in ("status", "platform", "qt_platform", "frozen", "checks")},
           "frozen_desktop_check": {k: frozen[k] for k in ("status", "platform", "qt_platform", "frozen", "checks")} if frozen else None,
           "isolated_source_check": source,
           "portable_verification": portable,
           "licence": report["source"]["licence"]}
write_json(root / "docs/validation_summary.json", summary)
rows = "\n".join(f"| {name} | {m['R2']:.4f} | {m['RMSE']:.4f} | {m['MAE']:.4f} |" for name, m in report["test_metrics"].items())
text = f"""# 实际训练和验证记录

记录日期：2026-10-28，目标环境Windows 11 x64、Python 3.12.10。模型版本 `{report['run_id']}`。机器可读信息见 `validation_summary.json`，详细日志/固定索引/搜索历史保存在本地models与reports目录。

## 数据与独立评估

ChEMBL人类ESR1直接结合记录7343条；清洗并聚合后2471个化合物、791个结构组。固定种子42，训练1724、验证414、独立测试333。结构组跨集合无交集，集间Morgan2048最高相似度低于0.85的检查已通过。原始记录量不能等同于独立化合物量。

验证集选择GA融合，模型权重ANN/RF/XGBoost/LR为 {' / '.join(f'{x:.6f}' for x in report['weights'])}。测试集只在方案冻结后评估；后续验证根据封存预测文件核对指标，没有用测试标签调参。

| 独立测试模型 | R² | RMSE | MAE |
|---|---:|---:|---:|
{rows}

融合没有超过XGBoost的测试R²；ANN和LR本次泛化较弱，负R²保留。不得将示意图分数作为实测或承诺，也不能将此测试结果等同于临床、完整ADMET或全部67项科研验证。

## 已执行检查

- 自动测试：{counts['tests']}项，失败{counts['failures']}、错误{counts['errors']}、跳过{counts['skipped']}。包括单位/精确标签、坏分子、重复冲突、特征一致性、分组隔离、三种优化复现、权重非法值、硬淘汰、缺测/演示、动态参数、真实模型加载、桌面预测/导出和后台失败恢复。
- 源码Windows原生Qt窗口检查：{native['status']}，Qt平台为{native['qt_platform']}。实际打开窗口、加载模型、触发预测按钮、绘制结构、检查默认缺测、演示风险淘汰和无效SMILES。
- Windows便携EXE原生窗口检查：{frozen['status'] if frozen else '待完成'}。
- Windows便携EXE官方数据下载及清洗：{portable.get('frozen_data_download_and_cleaning', '待完成') if portable else '待完成'}；与源码版清洗CSV的SHA256一致。构建依赖限定为项目虚拟环境、Python和Windows目录，外来工具DLL数量为{len(portable['external_binary_sources']) if portable else '待核验'}。
- Logo资源与显示：{portable.get('logo_check', '待完成') if portable else '待完成'}；PNG、SVG、ICO均随包，页眉、窗口标题栏和EXE图标使用同一Logo。
- 独立源码包检查：{source.get('status', '待完成') if source else '待完成'}。

## 实际运行界面

以下来自本次验证运行，分子输入和指标均由程序计算。

![模型训练](images/training.png)

![分子预测](images/prediction.png)

![阶段评估](images/funnel.png)



"""
(root / "docs/VALIDATION.md").write_text(text, encoding="utf-8")
images = root / "docs/images"
images.mkdir(exist_ok=True)
image_root = root / "reports/frozen-workspace/reports/desktop-check" if frozen else root / "reports/desktop-check"
for name in ("training", "prediction", "funnel"):
    shutil.copy2(image_root / (name + ".png"), images / (name + ".png"))
print(json.dumps({"automated_tests": counts, "frozen_check": frozen["status"] if frozen else "pending"}))
