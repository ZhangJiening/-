import csv
from erlead.reporting import export_prediction_file, prediction_html
from erlead.screening import Rules, screen


def result(pic50=7.1, **kwargs):
    return {"canonical_smiles": "CCO", "predictions": dict(ANN=7.0, RF=7.2, XGBoost=7.1, LR=6.9),
            "ensemble_pIC50": pic50, "weights": [.25] * 4, "method": "GA",
            "model_version": "test-fixture", "predicted_at": "2026-11-01T00:00:00+00:00",
            "data_sha256": "fixture", "screening": screen(pic50, **kwargs), "stage_evidence": None}


def test_missing_stage_exports_keep_blank_score_and_readable_reasons(tmp_path):
    r = result()
    path = tmp_path / "result.csv"
    export_prediction_file(path, "csv", r)
    with path.open(encoding="utf-8-sig", newline="") as stream:
        row = next(csv.DictReader(stream))
    assert row["score"] == ""
    assert row["stage2_status"] == row["stage3_status"] == "未评估"
    assert "5项" in row["stage2_reason"] and "67项" in row["stage3_reason"]
    assert "尚未完成" in row["score_explanation"]
    html = prediction_html(r)
    assert "分子筛选报告" in html and "data:image/png;base64," in html
    assert "未评估" in html and "不代表阶段3全部评估完成" in html
    assert "7.100" in html and "test-fixture" in html


def test_demo_hard_elimination_is_explicit_in_every_format(tmp_path):
    admet = dict(logS=-2.0, F_percent=50, PPB_percent=90, hepatotoxic=False, CYP3A4_inhibitor=False)
    r = result(5.9, rules=Rules(), admet=admet, structure=[True] * 67, demo=True)
    for kind in ("html", "csv", "json"):
        path = tmp_path / ("demo." + kind)
        export_prediction_file(path, kind, r)
        text = path.read_text(encoding="utf-8-sig")
        assert "流程演示" in text and "淘汰：活性不达标" in text
        assert "优先推荐候选" not in text


def test_external_evidence_is_escaped_in_readable_report():
    admet = dict(logS=-2.0, F_percent=50, PPB_percent=90, hepatotoxic=False, CYP3A4_inhibitor=False)
    r = result(admet=admet, evidence='</pre><script>alert("x")</script>')
    html = prediction_html(r)
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_partial_export_respects_choices_in_csv_and_embedded_json(tmp_path):
    import json
    from erlead.reporting import selected_prediction_data
    r = result()
    r["formula"] = "C2H6O"
    r["properties"] = dict(MW=46.07, LogP=-.001, TPSA=20.23)
    for kind in ("html", "csv", "json"):
        path = tmp_path / ("molecule-only." + kind)
        export_prediction_file(path, kind, r, {"molecule"})
        text = path.read_text(encoding="utf-8-sig")
        assert "ensemble_pIC50" not in text
        assert "stage2_status" not in text
        assert "本次筛选参数" not in text
        assert "test-fixture" in text and "未内置ADMET" in text
    row = next(csv.DictReader((tmp_path / "molecule-only.csv").open(encoding="utf-8-sig", newline="")))
    assert row["formula"] == "C2H6O"
    selected = json.loads(row["provenance_and_rules_json"])
    assert "predictions" not in selected and "stages" not in selected["screening"]
    assert selected_prediction_data(r) == r


def test_training_csv_trace_is_compact_while_json_keeps_full_history(tmp_path):
    import json
    from erlead.reporting import export_training_file
    report = {
        "app": "test-fixture", "target": "CHEMBL206", "run_id": "csv-fixture", "data_sha256": "fixture",
        "selected": "GA", "weights": [.25] * 4,
        "optimizers": {name: {"weights": [.25] * 4, "validation_mse": 1., "history": [1.] * 20000}
                       for name in ("GA", "SA", "TS")},
    }
    csv_path, json_path = tmp_path / "weights.csv", tmp_path / "weights.json"
    export_training_file(csv_path, "csv", report, {"weights"})
    export_training_file(json_path, "json", report, {"weights"})
    with csv_path.open(encoding="utf-8-sig", newline="") as stream:
        row = next(csv.DictReader(stream))
    assert max(len(value) for value in row.values()) < 32767
    assert float(row["weight_RF"]) == .25
    trace = json.loads(row["provenance_json"])
    assert trace["run_id"] == "csv-fixture" and trace["selected_optimizer"] == "GA"
    assert len(json.loads(json_path.read_text(encoding="utf-8"))["optimizers"]["GA"]["history"]) == 20000
