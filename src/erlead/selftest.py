from __future__ import annotations
import io
import numpy as np
from rdkit.Chem import Draw
from .chemistry import standardize
from .screening import Rules, screen
from .storage import model_location, utc_now
from .training import load_bundle, predict


def self_test(root):
    bundle = load_bundle(model_location(root))
    # Estradiol is a fixed chemical input; all predicted values come from the saved models.
    smiles = "C[C@]12CC[C@H]3[C@@H](CCc4cc(O)ccc43)[C@@H]1CC[C@@H]2O"
    result = predict(smiles, bundle)
    mol, canonical = standardize(smiles)
    image = Draw.MolToImage(mol, size=(420, 240))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    assert len(buffer.getvalue()) > 1000
    assert np.isclose(result["ensemble_pIC50"], np.asarray(list(result["predictions"].values())) @ result["weights"])
    try:
        predict("invalid_SMILES", bundle)
    except ValueError:
        pass
    else:
        raise AssertionError("无效SMILES未被拒绝")
    missing = screen(result["ensemble_pIC50"])
    assert missing["adjusted_score"] is None and missing["stages"][1]["status"] == "未评估"
    assert "淘汰" in screen(5.99)["conclusion"]
    assert screen(6.0)["stages"][0]["status"] == "通过"
    return {"status": "passed", "time": utc_now(), "model_version": result["model_version"],
            "canonical_smiles": canonical, "prediction": result, "structure_png_bytes": len(buffer.getvalue()),
            "checks": ["reload_four_models", "feature_inference", "simplex_fusion", "rdkit_2d", "invalid_smiles", "missing_stages", "hard_threshold"]}
