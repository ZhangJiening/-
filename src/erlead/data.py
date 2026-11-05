from __future__ import annotations
import hashlib
import json
import math
import shutil
import time
from collections import Counter
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import numpy as np
import pandas as pd
from . import TARGET
from .chemistry import standardize
from .storage import digest, read_json, utc_now, write_json

API = "https://www.ebi.ac.uk/chembl/api/data/"
LICENCE = {"name": "CC BY-SA 3.0", "url": "https://creativecommons.org/licenses/by-sa/3.0/",
           "source": "https://chembl.gitbook.io/chembl-interface-documentation/about",
           "attribution": "ChEMBL, EMBL-EBI. Data retrieved and filtered for human ESR1 IC50 binding assays."}


def request_json(url):
    for attempt in range(3):
        try:
            with urlopen(Request(url, headers={"User-Agent": "ERLeadPlatform/0.1 research data client"}), timeout=45) as response:
                return json.load(response)
        except Exception:
            if attempt == 2:
                raise
            time.sleep(1 + attempt)


def fetch_pages(resource, params, log):
    rows, urls, offset = [], [], 0
    while True:
        url = API + resource + ".json?" + urlencode({**params, "limit": 1000, "offset": offset})
        page = request_json(url)
        batch = page[{"assay": "assays", "activity": "activities"}[resource]]
        rows.extend(batch)
        urls.append(url)
        total = page["page_meta"]["total_count"]
        log(f"下载{resource}：{len(rows)}/{total}")
        if len(rows) >= total:
            break
        if not batch:
            raise ValueError("数据接口提前返回空页，请重试；不使用不完整数据训练")
        offset += len(batch)
    return rows, urls


def download(root: Path, log=print, refresh=False):
    raw = root / "data" / "raw"
    manifest_path = raw / "source.json"
    if manifest_path.exists() and not refresh:
        manifest = read_json(manifest_path)
        if all((raw / name).exists() and digest(raw / name) == checksum for name, checksum in manifest["files"].items()):
            log("使用已校验SHA256的ChEMBL数据缓存")
            return manifest
        raise ValueError("原始数据缓存校验失败，请选择重新下载，保留旧文件供排查")
    target = request_json(API + f"target/{TARGET}.json")
    symbols = {s["component_synonym"] for c in target.get("target_components", []) for s in c.get("target_component_synonyms", [])}
    if target.get("organism") != "Homo sapiens" or "ESR1" not in symbols:
        raise ValueError("官方目标元数据不再匹配人类ESR1，已停止下载")
    assays, assay_urls = fetch_pages("assay", {"target_chembl_id": TARGET, "assay_type": "B", "confidence_score": 9}, log)
    activities, activity_urls = fetch_pages("activity", {"target_chembl_id": TARGET, "standard_type": "IC50", "assay_type": "B"}, log)
    status = request_json(API + "status.json")
    if manifest_path.exists():
        backup = raw / "snapshots" / utc_now().replace(":", "-")
        backup.mkdir(parents=True, exist_ok=False)
        for name in ("source.json", "target.json", "assays.json", "activities.json"):
            if (raw / name).exists():
                shutil.copy2(raw / name, backup / name)
    write_json(raw / "target.json", target)
    write_json(raw / "assays.json", assays)
    write_json(raw / "activities.json", activities)
    manifest = {"retrieved_at": utc_now(), "database": status, "target": TARGET, "gene": "ESR1", "organism": "Homo sapiens",
                "urls": assay_urls + activity_urls, "licence": LICENCE, "raw_count": len(activities), "assay_count": len(assays),
                "filters": "Human ESR1; binding assays; direct single protein confidence 9; non-mutant assays; exact positive IC50",
                "files": {name: digest(raw / name) for name in ("target.json", "assays.json", "activities.json")}}
    write_json(manifest_path, manifest)
    return manifest


def ic50_to_pic50(value, units="nM"):
    factors = {"M": 1e9, "mM": 1e6, "uM": 1e3, "µM": 1e3, "μM": 1e3, "nM": 1.0, "pM": 1e-3}
    if units not in factors:
        raise ValueError("unsupported_unit")
    number = float(value) * factors[units]
    if not math.isfinite(number) or number <= 0:
        raise ValueError("nonpositive_or_nonfinite_ic50")
    return 9.0 - math.log10(number)


def clean_records(records, allowed_assays=None, log=None):
    progress = log or (lambda _: None)
    progress("清洗步骤 1/2/3：进行中")
    accepted, rejected, reasons = [], [], Counter()
    for index, row in enumerate(records):
        try:
            if row.get("target_chembl_id", TARGET) != TARGET:
                raise ValueError("wrong_target")
            if row.get("standard_type", "IC50") != "IC50":
                raise ValueError("not_ic50")
            if allowed_assays is not None and row.get("assay_chembl_id") not in allowed_assays:
                raise ValueError("ineligible_assay")
            if row.get("standard_relation", "=") != "=":
                raise ValueError("non_exact_relation")
            if row.get("data_validity_comment") not in (None, "", "Manually validated"):
                raise ValueError("data_validity_flag")
            if row.get("potential_duplicate") in (True, 1, "1"):
                raise ValueError("potential_duplicate")
            if row.get("assay_type", "B") != "B":
                raise ValueError("non_binding_assay")
            if row.get("target_organism", "Homo sapiens") != "Homo sapiens":
                raise ValueError("wrong_organism")
            pic50 = ic50_to_pic50(row.get("standard_value"), row.get("standard_units", "nM"))
            _, smiles = standardize(row.get("canonical_smiles", ""))
            accepted.append({"canonical_smiles": smiles, "pIC50": pic50,
                             "record_id": str(row.get("activity_id", index)),
                             "molecule_id": str(row.get("molecule_chembl_id", "imported")),
                             "assay_id": str(row.get("assay_chembl_id", "imported"))})
        except (ValueError, TypeError, OverflowError, RuntimeError) as error:
            reason = str(error) if isinstance(error, ValueError) else type(error).__name__
            reasons[reason] += 1
            rejected.append({"row": index, "record_id": row.get("activity_id", index), "reason": reason})
    if not accepted:
        raise ValueError("清洗后没有有效化合物；请检查SMILES、精确IC50、单位和测定条件")
    progress("清洗步骤 1/2/3：完成")
    progress("清洗步骤 4/5：进行中")
    frame = pd.DataFrame(accepted)
    grouped = []
    conflicts = 0
    for smiles, group in frame.groupby("canonical_smiles", sort=True):
        spread = float(group["pIC50"].max() - group["pIC50"].min())
        if spread > 1.0:
            conflicts += len(group)
            rejected.extend({"record_id": r, "reason": "replicate_spread_gt_1_log"} for r in group["record_id"])
            continue
        grouped.append({"canonical_smiles": smiles, "pIC50": float(group["pIC50"].median()),
                        "record_count": len(group), "pIC50_spread": spread,
                        "record_ids": "|".join(group["record_id"]), "molecule_ids": "|".join(sorted(set(group["molecule_id"]))),
                        "assay_ids": "|".join(sorted(set(group["assay_id"])))})
    if not grouped:
        raise ValueError("重复测定冲突过大，无可用于回归的数据")
    result = pd.DataFrame(grouped)
    audit = {"raw_count": len(records), "accepted_records_before_aggregation": len(frame),
             "rejected_records": len(records) - len(frame) + conflicts, "reasons": dict(reasons),
             "replicate_conflict_records": conflicts, "unique_compounds": len(result),
             "duplicate_records_aggregated": len(frame) - conflicts - len(result),
             "replicate_policy": "Canonical standardized isomeric molecule; median pIC50; exclude groups with spread >1 log unit",
             "standardization": "RDKit Cleanup + FragmentParent + Uncharger; canonical isomeric SMILES",
             "pIC50_range": [float(result.pIC50.min()), float(result.pIC50.max())],
             "pIC50_std": float(result.pIC50.std(ddof=0))}
    progress("清洗步骤 4/5：完成")
    return result, audit, rejected


def read_import_csv(path, **kwargs):
    try:
        return pd.read_csv(path, encoding="utf-8-sig", **kwargs)
    except UnicodeDecodeError:
        return pd.read_csv(path, encoding="gb18030", **kwargs)


def map_import_columns(frame, mapping, default_unit=None):
    """Map explicitly selected columns, preserving assay/target filters."""
    if not isinstance(mapping, dict) or not mapping.get("smiles") or not mapping.get("ic50"):
        raise ValueError("请选择SMILES和IC50字段")
    columns = [mapping.get(key) for key in ("smiles", "ic50", "unit") if mapping.get(key)]
    if len(columns) != len(set(columns)) or any(column not in frame for column in columns):
        raise ValueError("映射字段不存在或重复")
    if not mapping.get("unit"):
        if default_unit is None:
            raise ValueError("需要选择单位列或明确固定单位")
        ic50_to_pic50(1, default_unit)
    result = frame.copy()
    # Read from the original frame so mappings cannot overwrite one another.
    result["canonical_smiles"] = frame[mapping["smiles"]]
    result["standard_value"] = frame[mapping["ic50"]]
    result["standard_units"] = frame[mapping["unit"]] if mapping.get("unit") else default_unit
    return result


def prepare(root: Path, log=print, csv_path: Path | None = None, source_note="", refresh=False,
            column_mapping=None, default_unit=None):
    if csv_path is None:
        source = download(root, log, refresh)
        raw = root / "data" / "raw"
        records = read_json(raw / "activities.json")
        assays = read_json(raw / "assays.json")
        eligible = {a["assay_chembl_id"] for a in assays if a.get("confidence_score") == 9
                    and a.get("assay_organism") in (None, "Homo sapiens") and not a.get("variant_sequence")}
    else:
        if not source_note.strip():
            raise ValueError("导入数据必须填写ERα实验数据来源说明")
        frame = read_import_csv(csv_path)
        if column_mapping is not None:
            frame = map_import_columns(frame, column_mapping, default_unit)
        if "IC50_nM" not in frame and "standard_units" not in frame and "units" not in frame:
            raise ValueError("未声明IC50单位：请使用IC50_nM列，或提供units/standard_units列")
        aliases = {"SMILES": "canonical_smiles", "smiles": "canonical_smiles", "IC50": "standard_value",
                   "IC50_nM": "standard_value", "units": "standard_units", "relation": "standard_relation"}
        frame = frame.rename(columns={k: v for k, v in aliases.items() if k in frame and v not in frame})
        if not {"canonical_smiles", "standard_value"}.issubset(frame.columns):
            raise ValueError("CSV需要SMILES和IC50_nM列，或canonical_smiles与standard_value列")
        frame = frame.astype(object).where(pd.notna(frame), None)
        records = frame.to_dict("records")
        source = {"type": "user_import", "sha256": digest(csv_path), "filename": csv_path.name,
                  "source_note": source_note, "target": TARGET, "target_check": "user_declared_ESR1_binding_data",
                  "retrieved_at": utc_now(), "licence": "用户负责核验其提供数据的授权"}
        if column_mapping is not None:
            source["column_mapping"] = dict(column_mapping)
            source["default_unit"] = default_unit
        eligible = None
        snapshot = root / "data" / "raw" / ("imported-" + source["sha256"] + ".csv")
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        if not snapshot.exists():
            shutil.copy2(csv_path, snapshot)
        source["raw_snapshot"] = snapshot.name
    cleaned, audit, rejected = clean_records(records, eligible, log)
    output = root / "data" / "processed"
    output.mkdir(parents=True, exist_ok=True)
    cleaned.to_csv(output / "cleaned.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(rejected).to_csv(output / "rejections.csv", index=False, encoding="utf-8-sig")
    audit.update({"source": source, "cleaned_sha256": digest(output / "cleaned.csv"), "prepared_at": utc_now()})
    write_json(output / "audit.json", audit)
    log(f"清洗完成：原始{len(records)}条 → {len(cleaned)}个有效化合物")
    return audit
