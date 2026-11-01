from __future__ import annotations
import importlib.metadata
import logging
import platform
import sys
import warnings
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GroupShuffleSplit
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBRegressor
from threadpoolctl import threadpool_limits
from . import APP_NAME, MODEL_NAMES, TARGET, __version__
from .chemistry import FEATURE_SPEC, featurize, structural_groups
from .optimization import optimize, validate_weights
from .storage import digest, read_json, utc_now, write_json


def metrics(y, prediction):
    if len(y) < 2 or np.std(y) < 1e-10 or not np.isfinite(prediction).all():
        raise ValueError("评估集太小、标签无方差或预测异常，不能计算可靠指标")
    return {"R2": float(r2_score(y, prediction)), "RMSE": float(np.sqrt(mean_squared_error(y, prediction))),
            "MAE": float(mean_absolute_error(y, prediction)), "n": len(y)}


def split_data(frame, seed=42):
    if len(frame) < 60 or frame.pIC50.std() < 0.1:
        raise ValueError("需要至少60个有效化合物且pIC50有足够变化；不使用随机标签补样本")
    groups, _ = structural_groups(frame.canonical_smiles.tolist())
    if len(set(groups)) < 10:
        raise ValueError("独立结构组少于10组，无法可靠拆分，请增加真实数据")
    train, held = next(GroupShuffleSplit(n_splits=1, test_size=0.30, random_state=seed).split(frame, groups=groups))
    valid_local, test_local = next(GroupShuffleSplit(n_splits=1, test_size=0.5, random_state=seed + 1).split(held, groups=groups[held]))
    valid, test = held[valid_local], held[test_local]
    for indices in (train, valid, test):
        if len(indices) < 10 or frame.iloc[indices].pIC50.std() < 0.05:
            raise ValueError("结构拆分后某集合过小或标签无方差，需复核真实数据；未开始训练")
    assert not set(groups[train]) & set(groups[valid])
    assert not set(groups[train]) & set(groups[test])
    assert not set(groups[valid]) & set(groups[test])
    return {"train": train, "validation": valid, "test": test}, groups


def train(root: Path, seed=42, log=print):
    data_path = root / "data" / "processed" / "cleaned.csv"
    if not data_path.exists():
        raise ValueError("请先获取或导入并清洗真实数据")
    audit = read_json(data_path.parent / "audit.json")
    if digest(data_path) != audit["cleaned_sha256"]:
        raise ValueError("清洗数据校验失败，请重新执行清洗")
    data_hash = digest(data_path)
    version = "v" + __version__ + "-" + data_hash[:12] + f"-s{seed}"
    folder = root / "models" / version
    if (folder / "report.json").exists():
        log("加载相同数据、参数与版本的已完成运行；不重复评估独立测试集")
        load_bundle(folder)
        write_json(root / "models" / "current.json", {"run_id": version})
        return folder
    if folder.exists() and (folder / "evaluation_started.json").exists():
        raise ValueError("该运行已进入独立测试阶段但未完成；请核查异常日志，不重复使用测试集调参")
    folder.mkdir(parents=True, exist_ok=True)
    report_dir = root / "reports" / version
    report_dir.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(folder / "training.log", encoding="utf-8")
    logger = logging.getLogger(version)
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    def progress(message):
        logger.info(message)
        handler.flush()
        log(message)
    try:
        frame = pd.read_csv(data_path)
        progress("按骨架和Morgan相似度≥0.85合并结构组，生成固定拆分")
        splits, groups = split_data(frame, seed)
        assignments = frame.copy()
        assignments["structure_group"] = groups
        assignments["split"] = ""
        for name, indices in splits.items():
            assignments.loc[indices, "split"] = name
        assignments.to_csv(report_dir / "split.csv", index=False, encoding="utf-8-sig")
        write_json(folder / "split_indices.json", {k: v.tolist() for k, v in splits.items()})
        progress("生成统一Morgan1024位+8项理化特征；缩放仅拟合训练集")
        x = featurize(frame.canonical_smiles)
        y = frame.pIC50.to_numpy()
        tr, va, te = (splits[k] for k in ("train", "validation", "test"))
        models = {
            "ANN": make_pipeline(StandardScaler(), MLPRegressor(hidden_layer_sizes=(64, 32), max_iter=300,
                       early_stopping=True, validation_fraction=0.12, n_iter_no_change=25, alpha=0.1, random_state=seed)),
            "RF": RandomForestRegressor(n_estimators=240, min_samples_leaf=2, max_features=0.7, n_jobs=2, random_state=seed),
            "XGBoost": XGBRegressor(n_estimators=350, max_depth=4, learning_rate=0.035, subsample=0.85,
                         colsample_bytree=0.8, reg_lambda=3, tree_method="hist", n_jobs=2, random_state=seed, objective="reg:squarederror"),
            "LR": make_pipeline(StandardScaler(), LinearRegression()),
        }
        validation, valid_metrics, params = [], {}, {}
        for name, model in models.items():
            progress(f"开始真实训练：{name}，训练{len(tr)} / 验证{len(va)} / 独立测试{len(te)}")
            with warnings.catch_warnings(record=True) as captured:
                warnings.simplefilter("always")
                with threadpool_limits(limits=2):
                    model.fit(x[tr], y[tr])
                for warning in captured:
                    progress(f"{name}警告：{warning.message}")
            joblib.dump(model, folder / f"{name}.joblib")
            pred = model.predict(x[va])
            validation.append(pred)
            valid_metrics[name] = metrics(y[va], pred)
            params[name] = {k: repr(v) for k, v in model.get_params(deep=True).items()}
            progress(f"{name}验证：{valid_metrics[name]}")
        validation = np.column_stack(validation)
        optimizers = {}
        for method in ("GA", "SA", "TS"):
            progress(f"在验证集上运行{method}权重搜索")
            result = optimize(validation, y[va], method, seed=seed)
            optimizers[method] = result
            valid_metrics[method] = metrics(y[va], validation @ result["weights"])
            write_json(report_dir / f"{method}_history.json", result)
        selected = min(optimizers, key=lambda k: optimizers[k]["validation_mse"])
        weights = optimizers[selected]["weights"]
        validate_weights(weights)
        pd.DataFrame({"truth": y[va], **{name: validation[:, i] for i, name in enumerate(MODEL_NAMES)}}).to_csv(
            report_dir / "validation_predictions.csv", index=False, encoding="utf-8-sig")
        write_json(folder / "ensemble.json", {"method": selected, "model_order": MODEL_NAMES, "weights": weights})
        progress(f"已依据验证集冻结融合方案：{selected}，现在执行一次独立测试评估")
        write_json(folder / "evaluation_started.json", {"time": utc_now(), "selected_on": "validation", "selected": selected})
        test_pred = np.column_stack([models[name].predict(x[te]) for name in MODEL_NAMES])
        test_metrics = {name: metrics(y[te], test_pred[:, i]) for i, name in enumerate(MODEL_NAMES)}
        test_metrics["ensemble"] = metrics(y[te], test_pred @ weights)
        pd.DataFrame({"canonical_smiles": frame.iloc[te].canonical_smiles.to_numpy(), "truth": y[te],
                      **{name: test_pred[:, i] for i, name in enumerate(MODEL_NAMES)}, "ensemble": test_pred @ weights}).to_csv(
            report_dir / "test_predictions.csv", index=False, encoding="utf-8-sig")
        versions = {pkg: importlib.metadata.version(pkg) for pkg in ("rdkit", "numpy", "pandas", "scikit-learn", "xgboost", "joblib")}
        report = {"app": APP_NAME, "app_version": __version__, "run_id": version, "created_at": utc_now(), "target": TARGET,
                  "seed": seed, "data_sha256": data_hash, "source": audit["source"], "cleaning": audit,
                  "features": FEATURE_SPEC, "split_counts": {k: len(v) for k, v in splits.items()},
                  "split_strategy": "GroupShuffleSplit 70/15/15 approximately; identical Murcko scaffolds and Morgan2048 Tanimoto>=0.85 united before splitting",
                  "structure_groups": len(set(groups)), "validation_metrics": valid_metrics, "test_metrics": test_metrics,
                  "selected": selected, "weights": weights, "optimizers": optimizers,
                  "model_parameters": params, "environment": {"python": sys.version, "os": platform.platform(), "versions": versions},
                  "independent_test_evaluations": 1,
                  "limitations": ["测定来自多个直接结合实验，仍可能存在实验异质性", "结构分组测试代表本次数据，不能保证新化学空间表现",
                                  "模型预测用于科研初筛，不替代实验", "未训练ADMET及67输出模型"]}
        checksums = {f"{name}.joblib": digest(folder / f"{name}.joblib") for name in MODEL_NAMES}
        report["artifact_sha256"] = checksums
        write_json(folder / "report.json", report)
        write_json(report_dir / "report.json", report)
        pd.DataFrame([{"set": dataset, "model": name, **values} for dataset, table in (("validation", valid_metrics), ("test", test_metrics))
                      for name, values in table.items()]).to_csv(report_dir / "metrics.csv", index=False, encoding="utf-8-sig")
        write_json(root / "models" / "current.json", {"run_id": version})
        progress(f"训练完成；独立测试融合指标：{test_metrics['ensemble']}")
        return folder
    except Exception:
        logger.exception("训练失败；未将未完成模型设为当前版本")
        raise
    finally:
        logger.removeHandler(handler)
        handler.close()


def load_bundle(folder: Path):
    report = read_json(folder / "report.json")
    if report["target"] != TARGET or report["features"] != FEATURE_SPEC:
        raise ValueError("模型靶点或特征配置不兼容")
    if set(report["artifact_sha256"]) != {f"{name}.joblib" for name in MODEL_NAMES}:
        raise ValueError("模型校验清单不完整，必须包含4个回归器")
    for filename, checksum in report["artifact_sha256"].items():
        if Path(filename).name != filename or digest(folder / filename) != checksum:
            raise ValueError("模型校验失败，文件可能损坏")
    models = [joblib.load(folder / f"{name}.joblib") for name in MODEL_NAMES]
    validate_weights(report["weights"])
    return models, report


def predict(smiles, bundle):
    models, report = bundle
    features = featurize([smiles])
    values = np.asarray([float(model.predict(features)[0]) for model in models])
    if not np.isfinite(values).all():
        raise ValueError("模型产生非有限预测值")
    return {"input_smiles": smiles, "predictions": dict(zip(MODEL_NAMES, values.tolist())),
            "ensemble_pIC50": float(values @ report["weights"]), "weights": report["weights"],
            "method": report["selected"], "model_version": report["run_id"], "data_sha256": report["data_sha256"],
            "source": report["source"], "predicted_at": utc_now()}
