"""Readable views of saved results. No model inference or screening rules live here."""
from __future__ import annotations
import base64
import csv
import io
import json
from html import escape
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
from . import APP_NAME, MODEL_NAMES, __version__
from .storage import write_json

SCOPE_TEXT = ("阶段1使用已训练的ERα / ESR1活性回归模型。阶段2按外部提供的5项ADMET数据执行门槛判定，"
              "阶段3按外部提供的完整67项约束判定执行统计；本版本未内置ADMET或67项多输出预测模型。"
              "分子式、MW、LogP、TPSA为RDKit计算的描述符，不代表阶段3全部评估完成。"
              "缺测阶段保留“未评估”，仅三阶段数据齐全时计算综合分；演示数据不作为科研结论。")
MODEL_HEADERS = ["模型 / 方案", "验证 R²", "验证 RMSE", "验证 MAE", "测试 R²", "测试 RMSE", "测试 MAE"]
STAGE_HEADERS = ["阶段", "状态", "输入 / 来源", "判定条件", "输出", "原因", "流转"]
FIELD_NAMES = {"logS": "logS", "F_percent": "F（%）", "PPB_percent": "PPB（%）",
               "hepatotoxic": "肝毒性风险", "CYP3A4_inhibitor": "CYP3A4高抑制风险"}


def display_time(value):
    return datetime.fromisoformat(value).astimezone(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M:%S（北京时间）")


def stage_reason(stage, screening):
    if stage["status"] == "未评估":
        return ("缺少完整5项ADMET测量或外部模型数据。" if stage["stage"] == 2 else
                "缺少完整67项约束定义及对应判定数据。")
    if stage["stage"] == 1:
        value = stage["input"]["pIC50"]
        threshold = screening["rules"]["activity_threshold"]
        return f"预测 pIC50 {value:.3f} {'≥' if value >= threshold else '<'} 门槛 {threshold:.2f}。" + (
            "活性达标，后续状态见阶段2/3。" if value >= threshold else "触发活性硬性淘汰，其他阶段加分不能放行。")
    if stage["stage"] == 2:
        failures = [FIELD_NAMES[k] for k, ok in (stage.get("checks") or {}).items() if not ok]
        if not failures:
            return "提供的5项数据均满足当前门槛。"
        return "未满足：" + "、".join(failures) + ("；关键风险触发硬性淘汰。" if stage["status"] == "淘汰" else "；需进一步复核。")
    count = stage["passed_count"]
    return f"提供的67项约束中，{count}项满足、{67 - count}项未满足。"


def stage_rows(result):
    screening = result["screening"]
    rows = []
    for stage in screening["stages"]:
        number = stage["stage"]
        demo = screening["demo"] and number > 1 and stage["input"] is not None
        status = ("演示 · " if demo else "") + stage["status"]
        if stage["input"] is None:
            inputs = "未提供"
        elif number == 1:
            inputs = f"pIC50 {stage['input']['pIC50']:.3f}"
        elif number == 2:
            inputs = "；".join(f"{FIELD_NAMES[k]}：{('有' if v else '无') if type(v) is bool else f'{v:g}'}"
                              for k, v in stage["input"].items())
        else:
            inputs = f"67项判定，满足{stage['passed_count']}项"
        inputs += "\n来源：" + str(stage["source"])
        output = "未评估" if stage["score"] is None else f"S{number} = {stage['score']:.3f}"
        if stage.get("passed_count") is not None:
            output += f"（{stage['passed_count']}/{'5' if number == 2 else '67'}）"
        rows.append([f"{number:02d} · {stage['name']}", status, inputs, stage["criterion"],
                     output, stage_reason(stage, screening), stage["flow"]])
    return rows


def score_text(result):
    screening = result["screening"]
    if screening["adjusted_score"] is None:
        missing = "、".join(str(s["stage"]) for s in screening["stages"] if s["score"] is None)
        return f"综合评分尚未完成：阶段{missing}未评估。"
    return f"{screening['score_label']} {screening['adjusted_score']:.4f}（基础分 {screening['base_score']:.4f}）。硬性淘汰优先。"


def training_rows(report):
    rows = []
    for name in (*MODEL_NAMES, "ensemble"):
        validation = report["validation_metrics"][report["selected"] if name == "ensemble" else name]
        test = report["test_metrics"][name]
        rows.append([f"融合（{report['selected']}）" if name == "ensemble" else name,
                     *[f"{values[metric]:.4f}" for values in (validation, test) for metric in ("R2", "RMSE", "MAE")]])
    return rows


def write_csv(path, headers, rows):
    with Path(path).open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(headers)
        writer.writerows(rows)


PREDICTION_SECTIONS = frozenset(("molecule", "activity", "stages", "parameters"))
TRAINING_SECTIONS = frozenset(("models", "data", "weights", "run"))


def _selection(sections, allowed):
    chosen = allowed if sections is None else frozenset(sections)
    if not chosen or not chosen.issubset(allowed):
        raise ValueError("导出内容为空或包含不支持的项目")
    return chosen


def selected_prediction_data(result, sections=None):
    chosen = _selection(sections, PREDICTION_SECTIONS)
    if chosen == PREDICTION_SECTIONS:
        return result
    selected = {key: result[key] for key in ("canonical_smiles", "model_version", "predicted_at", "data_sha256")}
    selected["scope"] = SCOPE_TEXT
    selected["screening"] = {key: result["screening"][key] for key in ("conclusion", "demo")}
    if "molecule" in chosen:
        selected.update({key: result[key] for key in ("input_smiles", "formula", "properties") if key in result})
    if "activity" in chosen:
        selected.update({key: result[key] for key in ("predictions", "ensemble_pIC50", "weights", "method")})
    if "stages" in chosen:
        selected["screening"].update({key: result["screening"][key] for key in (
            "stages", "adjusted_score", "base_score", "score_label") if key in result["screening"]})
    if "parameters" in chosen:
        selected["screening"]["rules"] = result["screening"]["rules"]
        selected.update({key: result[key] for key in ("stage_evidence", "source") if key in result})
    return selected


def selected_training_data(report, sections=None):
    chosen = _selection(sections, TRAINING_SECTIONS)
    if chosen == TRAINING_SECTIONS:
        return report
    selected = {key: report[key] for key in ("app", "target", "run_id", "data_sha256")}
    selected["scope"] = SCOPE_TEXT
    field_sets = {
        "models": ("test_metrics", "validation_metrics", "selected", "limitations"),
        "data": ("seed", "split_counts", "split_strategy", "structure_groups", "cleaning", "features"),
        "weights": ("selected", "weights", "optimizers"),
        "run": ("created_at", "app_version", "source", "environment", "independent_test_evaluations"),
    }
    for section in chosen:
        selected.update({key: report[key] for key in field_sets[section] if key in report})
    return selected


def prediction_csv_row(result, sections=None):
    chosen = _selection(sections, PREDICTION_SECTIONS)
    screening = result["screening"]
    row = {"smiles": result["canonical_smiles"], "model_version": result["model_version"],
           "predicted_at": result["predicted_at"], "data_sha256": result["data_sha256"],
           "conclusion": screening["conclusion"], "demo": screening["demo"]}
    if "molecule" in chosen:
        row.update({"formula": result.get("formula", ""), **{key: result.get("properties", {}).get(key, "") for key in ("MW", "LogP", "TPSA")}})
    if "activity" in chosen:
        row.update({**result["predictions"], "ensemble_pIC50": result["ensemble_pIC50"],
                    **{"weight_" + name: weight for name, weight in zip(MODEL_NAMES, result["weights"])}})
    if "stages" in chosen:
        row.update(score=screening["adjusted_score"], score_explanation=score_text(result))
        for stage, view in zip(screening["stages"], stage_rows(result)):
            prefix = f"stage{stage['stage']}_"
            row.update({prefix + key: value for key, value in
                        (("status", view[1]), ("input", view[2]), ("criterion", view[3]), ("output", view[4]),
                         ("reason", view[5]), ("flow", view[6]), ("source", stage["source"]))})
    if "parameters" in chosen:
        rules = screening["rules"]
        row.update(activity_threshold=rules["activity_threshold"], reward=rules["reward"], penalty=rules["penalty"])
        row.update({f"stage_weight_{i}": weight for i, weight in enumerate(rules["stage_weights"], 1)})
    row["scope"] = SCOPE_TEXT
    # Preserve the original column; partial exports contain only selected data.
    row["provenance_and_rules_json"] = json.dumps(selected_prediction_data(result, chosen), ensure_ascii=False, allow_nan=False)
    return row


def _text(value):
    return escape(str(value)).replace("\n", "<br>")


def _table(headers, rows, css_class=""):
    def cell(value):
        try:
            float(str(value).strip().rstrip("%"))
            numeric = True
        except ValueError:
            numeric = False
        return ('<td class="numeric">' if numeric else "<td>") + _text(value) + "</td>"
    return (f'<table class="{css_class}"><thead><tr>' + "".join(f"<th>{_text(h)}</th>" for h in headers) +
            "</tr></thead><tbody>" + "".join("<tr>" + "".join(cell(value) for value in row) +
                                            "</tr>" for row in rows) + "</tbody></table>")


def _document(title, body, raw):
    return """<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>""" + escape(title) + """</title><style>
*{box-sizing:border-box}body{margin:0;background:#f1f6fc;color:#303844;font:14px/1.65 "Microsoft YaHei UI","Microsoft YaHei","Noto Sans CJK SC","Segoe UI",sans-serif}
main{max-width:1140px;margin:32px auto;background:white;padding:36px 44px;border:1px solid #e4e7eb;border-radius:12px}
header{border-bottom:1px solid #dfe5e9;margin-bottom:24px;padding-bottom:18px}h1{font-size:24px;margin:4px 0}h2{font-size:18px;margin:28px 0 12px}
p{margin:8px 0}.muted{color:#667281}.eyebrow{font-size:12px;color:#1766bc;letter-spacing:1px}
.hero{display:flex;gap:32px;align-items:center}.molecule{width:52%;max-height:290px;object-fit:contain}
.result{flex:1}.value{font:600 48px/1.2 "Segoe UI",sans-serif;color:#1476ee;margin:12px 0}
.callout{background:#eaf3ff;border-left:3px solid #1977ed;padding:12px 16px}.demo{color:#875017;background:#fff5df;border-left-color:#ad6f20}
table{width:100%;border-collapse:collapse;font-size:13px;margin:12px 0}th,td{text-align:left;vertical-align:top;border-bottom:1px solid #e5e8ec;padding:10px 9px;overflow-wrap:anywhere}th{background:#f5f7f8;color:#52616e}.numeric{text-align:right;font-family:"Segoe UI",sans-serif;font-variant-numeric:tabular-nums}
.stages{table-layout:fixed}.stages th:nth-child(1){width:10%}.stages th:nth-child(2){width:8%}.stages th:nth-child(3){width:18%}.stages th:nth-child(4){width:21%}.stages th:nth-child(5){width:11%}.stages th:nth-child(6){width:25%}.stages th:nth-child(7){width:7%}.stages td:nth-child(2),.stages td:nth-child(7){white-space:nowrap}\npre{white-space:pre-wrap;word-break:break-all;background:#f6f7f8;padding:16px;font-size:12px}
.meta{overflow-wrap:anywhere;font-size:12px;color:#637b97}details{margin-top:24px}summary{cursor:pointer}
footer{margin-top:28px;border-top:1px solid #e5e8ec;padding-top:14px;color:#637b97;font-size:12px}
@media(max-width:700px){main{padding:20px;margin:8px}.hero{display:block}.molecule{width:100%}table{font-size:12px}}
@media print{@page{size:A4 landscape;margin:12mm}body{background:white;font-size:12px;line-height:1.45}main{border:0;margin:0;padding:0;max-width:none}header{margin-bottom:14px;padding-bottom:12px}h1{font-size:22px}details{display:none}tr,img{break-inside:avoid}h2{font-size:16px;margin:16px 0 6px;break-after:avoid}p{margin:6px 0}table{font-size:12px;margin:8px 0;break-inside:avoid}th,td{padding:6px 8px}.molecule{max-height:220px}.value{font-size:40px}.callout{padding:10px 14px}footer{margin-top:10px;padding-top:7px;font-size:10px;line-height:1.4;break-inside:avoid}}
</style><main><header><div class="eyebrow">ERα / ESR1 · 科研初筛</div><h1>""" + escape(title) + (
        '</h1><div class="muted">' + escape(APP_NAME) + "</div></header>" + body +
        "<details><summary>高级详情 · 原始 JSON</summary><pre>" +
        escape(json.dumps(raw, ensure_ascii=False, indent=2, allow_nan=False)) +
        "</pre></details><footer>软件 v" + __version__ +
        " · 本报告用于科研初筛，预测结果需实验验证。模型评估指标不代表临床效果。</footer></main></html>")


def prediction_html(result, sections=None):
    chosen = _selection(sections, PREDICTION_SECTIONS)
    s = result["screening"]
    body = '<div class="callout' + (' demo' if s["demo"] else '') + '">' + _text(s["conclusion"]) + "</div>"
    if "molecule" in chosen:
        from rdkit.Chem import Draw, rdMolDescriptors
        from .chemistry import standardize
        mol, _ = standardize(result["canonical_smiles"])
        buffer = io.BytesIO()
        Draw.MolToImage(mol, size=(1000, 560)).save(buffer, format="PNG")
        image = base64.b64encode(buffer.getvalue()).decode("ascii")
        body += '<section class="hero"><img class="molecule" alt="RDKit二维分子结构" src="data:image/png;base64,' + image + '">'
        if "activity" in chosen:
            body += _activity_block(result)
        body += "</section>"
        props = result.get("properties", {})
        body += _table(["分子式", "MW", "LogP", "TPSA"], [[rdMolDescriptors.CalcMolFormula(mol),
            *[f"{props[key]:.2f}" if key in props else "未提供" for key in ("MW", "LogP", "TPSA")]]])
    elif "activity" in chosen:
        body += _activity_block(result)
    body += '<p class="meta">标准化 SMILES：' + _text(result["canonical_smiles"]) + "</p>"
    if "stages" in chosen:
        body += "<h2>三级筛选 · 状态与原因</h2>" + _table(STAGE_HEADERS, stage_rows(result), "stages")
    if "activity" in chosen:
        body += "<h2>单模型结果与融合</h2>" + _table(["回归器", "预测 pIC50", "融合权重"],
            [[name, f"{result['predictions'][name]:.3f}", f"{weight:.1%}"] for name, weight in zip(MODEL_NAMES, result["weights"])])
    if "parameters" in chosen:
        rules = s["rules"]
        body += "<h2>本次筛选参数</h2>" + _table(["活性门槛", "阶段1 / 2 / 3权重", "奖励系数", "惩罚系数"],
            [[rules["activity_threshold"], " / ".join(f"{x:.2f}" for x in rules["stage_weights"]), rules["reward"], rules["penalty"]]])
    body += "<h2>功能范围与结果解释</h2><p>" + _text(SCOPE_TEXT) + "</p>"
    body += '<p class="meta">模型版本：' + _text(result["model_version"]) + "<br>预测时间：" + _text(display_time(result["predicted_at"]))
    body += "<br>数据 SHA256：" + _text(result["data_sha256"]) + "</p>"
    return _document("分子筛选报告" + (" · 流程演示" if s["demo"] else ""), body, selected_prediction_data(result, chosen))


def _activity_block(result):
    return ('<div class="result"><p class="muted">融合预测 · pIC50</p><div class="value">'
            + f"{result['ensemble_pIC50']:.3f}" + "</div><p>" + _text(score_text(result))
            + '</p><p class="muted">pIC50 = −log10(IC50 [mol/L])</p></div>')


def training_html(report, sections=None):
    chosen = _selection(sections, TRAINING_SECTIONS)
    body = '<div class="callout">训练评估报告 · 固定ERα / ESR1活性回归；与单个分子的筛选结果分别记录。</div>'
    if "data" in chosen:
        counts, clean = report["split_counts"], report["cleaning"]
        body += "<h2>数据与实验设置</h2>" + _table(["原始记录", "清洗后化合物", "训练 / 验证 / 测试", "随机种子"],
            [[clean["raw_count"], clean["unique_compounds"], " / ".join(str(counts[key]) for key in ("train", "validation", "test")), report["seed"]]])
    body += "<p>GA / SA / TS仅在验证集搜索融合权重，冻结后对独立测试集评估一次。</p>"
    if "models" in chosen:
        body += "<h2>模型评估</h2>" + _table(MODEL_HEADERS, training_rows(report))
        body += "<p class='muted'>R²越高越好，RMSE和MAE越低越好（pIC50单位）。负R²如实保留；融合不保证优于每个单模型。</p>"
    if "weights" in chosen:
        body += "<h2>融合方案</h2>" + _table(["选择方法", *MODEL_NAMES],
            [[report["selected"], *[f"{weight:.1%}" for weight in report["weights"]]]])
        body += _table(["优化器", "ANN", "RF", "XGBoost", "LR", "验证 RMSE"], [
            [method + ("（已选）" if method == report["selected"] else ""),
             *[f"{weight:.1%}" for weight in report["optimizers"][method]["weights"]],
             f"{report['validation_metrics'][method]['RMSE']:.4f}"] for method in ("GA", "SA", "TS")])
    if "run" in chosen:
        body += "<h2>数据来源与限制</h2><p>" + _text("\n".join(report.get("limitations", []))) + "</p>"
        source_name = report["source"].get("database", {}).get("chembl_db_version", "外部实验数据；完整来源见高级详情")
        body += '<p class="meta">训练时间：' + _text(display_time(report["created_at"])) + "<br>数据来源：" + _text(source_name) + "</p>"
    body += "<p>" + _text(SCOPE_TEXT) + "</p>"
    body += '<p class="meta">训练版本：' + _text(report["run_id"]) + "<br>数据 SHA256：" + _text(report["data_sha256"]) + "</p>"
    return _document("模型训练报告", body, selected_training_data(report, chosen))


def export_prediction_file(path, kind, result, sections=None):
    path = Path(path)
    chosen = _selection(sections, PREDICTION_SECTIONS)
    if kind == "json":
        write_json(path, selected_prediction_data(result, chosen))
    elif kind == "csv":
        row = prediction_csv_row(result, chosen)
        write_csv(path, list(row), [list(row.values())])
    elif kind == "html":
        path.write_text(prediction_html(result, chosen), encoding="utf-8")
    else:
        raise ValueError("不支持的报告格式")


def export_training_file(path, kind, report, sections=None):
    path = Path(path)
    chosen = _selection(sections, TRAINING_SECTIONS)
    selected = selected_training_data(report, chosen)
    if kind == "json":
        write_json(path, selected)
    elif kind == "html":
        path.write_text(training_html(report, chosen), encoding="utf-8")
    elif kind == "csv":
        metadata = {"run_id": report["run_id"], "data_sha256": report["data_sha256"]}
        if "data" in chosen:
            metadata.update(seed=report["seed"], structure_groups=report["structure_groups"])
            metadata.update({name + "_count": count for name, count in report["split_counts"].items()})
        if "weights" in chosen:
            metadata.update(selected_optimizer=report["selected"])
            metadata.update({"weight_" + name: weight for name, weight in zip(MODEL_NAMES, report["weights"])})
        if "run" in chosen:
            metadata.update(created_at=report["created_at"], target=report["target"], source_json=json.dumps(report["source"], ensure_ascii=False))
        metadata["scope"] = SCOPE_TEXT
        # CSV carries compact traceability; complete search histories stay in JSON.
        metadata["provenance_json"] = json.dumps(metadata, ensure_ascii=False, allow_nan=False)
        if "models" in chosen:
            write_csv(path, [*MODEL_HEADERS, *metadata], [row + list(metadata.values()) for row in training_rows(report)])
        else:
            write_csv(path, list(metadata), [list(metadata.values())])
    else:
        raise ValueError("不支持的报告格式")
