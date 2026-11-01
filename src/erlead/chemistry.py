from __future__ import annotations
import numpy as np
from rdkit import Chem, DataStructs
from rdkit.Chem import Descriptors, rdFingerprintGenerator, rdMolDescriptors
from rdkit.Chem.MolStandardize import rdMolStandardize
from rdkit.Chem.Scaffolds import MurckoScaffold

FEATURE_SPEC = {"schema": 1, "radius": 2, "bits": 1024, "include_chirality": True,
                "descriptors": ["MW", "LogP", "HBD", "HBA", "TPSA", "RotBonds", "Rings", "FractionCSP3"]}
GENERATOR = rdFingerprintGenerator.GetMorganGenerator(radius=2, fpSize=1024, includeChirality=True)
SIMILARITY_GENERATOR = rdFingerprintGenerator.GetMorganGenerator(radius=2, fpSize=2048)


def standardize(smiles: str):
    if not isinstance(smiles, str) or not smiles.strip():
        raise ValueError("请输入非空SMILES字符串")
    mol = Chem.MolFromSmiles(smiles.strip())
    if mol is None or mol.GetNumHeavyAtoms() < 2:
        raise ValueError("SMILES无法解析为有效分子")
    mol = rdMolStandardize.Cleanup(mol)
    mol = rdMolStandardize.FragmentParent(mol)
    mol = rdMolStandardize.Uncharger().uncharge(mol)
    Chem.SanitizeMol(mol)
    return mol, Chem.MolToSmiles(mol, isomericSmiles=True, canonical=True)


def properties(mol):
    return {"MW": Descriptors.MolWt(mol), "LogP": Descriptors.MolLogP(mol),
            "HBD": float(rdMolDescriptors.CalcNumHBD(mol)), "HBA": float(rdMolDescriptors.CalcNumHBA(mol)),
            "TPSA": Descriptors.TPSA(mol), "RotBonds": float(rdMolDescriptors.CalcNumRotatableBonds(mol)),
            "Rings": float(rdMolDescriptors.CalcNumRings(mol)), "FractionCSP3": rdMolDescriptors.CalcFractionCSP3(mol)}


def featurize(smiles_list):
    rows = []
    for smiles in smiles_list:
        mol, _ = standardize(smiles)
        bits = np.zeros(FEATURE_SPEC["bits"], dtype=np.float32)
        DataStructs.ConvertToNumpyArray(GENERATOR.GetFingerprint(mol), bits)
        rows.append(np.concatenate((bits, list(properties(mol).values()))))
    result = np.asarray(rows, dtype=np.float32)
    if result.ndim != 2 or not np.isfinite(result).all():
        raise ValueError("分子特征为空或包含非有限数值")
    return result


def structural_groups(smiles_list, threshold=0.85):
    """Union identical scaffolds and close Morgan neighbours before any split."""
    parent = list(range(len(smiles_list)))
    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    def union(i, j):
        parent[find(i)] = find(j)
    scaffolds, fingerprints = {}, []
    for i, smiles in enumerate(smiles_list):
        mol, _ = standardize(smiles)
        scaffold = MurckoScaffold.MurckoScaffoldSmiles(mol=mol, includeChirality=False) or "ACYCLIC"
        if scaffold in scaffolds:
            union(i, scaffolds[scaffold])
        else:
            scaffolds[scaffold] = i
        fp = SIMILARITY_GENERATOR.GetFingerprint(mol)
        for j, similarity in enumerate(DataStructs.BulkTanimotoSimilarity(fp, fingerprints)):
            if similarity >= threshold:
                union(i, j)
        fingerprints.append(fp)
    return np.asarray([find(i) for i in range(len(parent))]), fingerprints
