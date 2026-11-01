from __future__ import annotations
from collections import deque
import numpy as np


def validate_weights(weights, size=4):
    weights = np.asarray(weights, dtype=float)
    if weights.shape != (size,) or not np.isfinite(weights).all() or (weights < 0).any() or not np.isclose(weights.sum(), 1, atol=1e-8):
        raise ValueError(f"需要{size}个非负有限权重，且总和为1")
    return weights


def simplex(vector):
    # Euclidean projection onto the probability simplex.
    ordered = np.sort(vector)[::-1]
    shifts = (np.cumsum(ordered) - 1) / np.arange(1, len(ordered) + 1)
    rho = np.nonzero(ordered > shifts)[0][-1]
    result = np.maximum(vector - shifts[rho], 0)
    return result / result.sum()


def optimize(predictions, y, method, seed=42, iterations=250):
    predictions, y = np.asarray(predictions), np.asarray(y)
    if predictions.ndim != 2 or predictions.shape != (len(y), 4) or not np.isfinite(predictions).all() or not np.isfinite(y).all():
        raise ValueError("融合优化需要同一验证集的4列有限预测值")
    if method not in ("GA", "SA", "TS") or iterations < 1:
        raise ValueError("未知优化算法或无效迭代次数")
    rng = np.random.default_rng(seed)
    def loss(w):
        return float(np.mean((predictions @ w - y) ** 2))
    initial = np.vstack([np.eye(4), np.full(4, 0.25)])
    best = min(initial, key=loss).copy()
    score = loss(best)
    history = [{"iteration": 0, "mse": score, "weights": best.tolist()}]
    current, current_loss = best.copy(), score
    population = np.vstack([initial, rng.dirichlet(np.ones(4), size=35)])
    tabu = deque(maxlen=25)
    for step in range(iterations):
        if method == "GA":
            ranks = sorted(population, key=loss)
            elite = np.asarray(ranks[:10])
            children = [elite[0]]
            for _ in range(39):
                a, b = elite[rng.integers(0, len(elite), size=2)]
                mix = rng.random()
                children.append(simplex(mix * a + (1 - mix) * b + rng.normal(0, 0.06, 4)))
            population = np.asarray(children)
            candidate = min(population, key=loss)
        elif method == "SA":
            temperature = max(0.001, 0.25 * (0.98 ** step))
            proposal = simplex(current + rng.normal(0, max(0.005, 0.15 * (0.99 ** step)), 4))
            proposal_loss = loss(proposal)
            if proposal_loss <= current_loss or rng.random() < np.exp(np.clip((current_loss - proposal_loss) / temperature, -700, 0)):
                current, current_loss = proposal, proposal_loss
            candidate = current
        else:
            neighbours = [simplex(current + rng.normal(0, 0.06, 4)) for _ in range(24)]
            legal = [w for w in neighbours if tuple(w.round(3)) not in tabu or loss(w) < score]
            if not legal:
                continue
            current = min(legal, key=loss)
            tabu.append(tuple(current.round(3)))
            candidate = current
        candidate_score = loss(candidate)
        if candidate_score < score:
            best, score = candidate.copy(), candidate_score
        history.append({"iteration": step + 1, "mse": score, "weights": best.tolist()})
    validate_weights(best)
    return {"method": method, "seed": seed, "iterations": iterations, "weights": best.tolist(),
            "validation_mse": score, "history": history,
            "parameters": {"population": 40, "elite": 10, "mutation_sigma": 0.06} if method == "GA" else
            {"initial_temperature": 0.25, "cooling": 0.98, "proposal_sigma": 0.15} if method == "SA" else
            {"tabu_length": 25, "neighbours": 24, "round_decimals": 3}}
