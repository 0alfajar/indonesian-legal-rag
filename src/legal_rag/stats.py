"""Uncertainty and significance for small retrieval benchmarks.

With 40 questions a single question moves hit@k by 0.025, so point estimates alone
cannot tell a real improvement from noise. Everything here works on per-question
ranks (1-based, ``None`` = not retrieved) and is seeded for reproducibility.
"""

import numpy as np

CUTOFFS = (1, 3, 5)
METRICS = tuple(f"hit@{k}" for k in CUTOFFS) + ("mrr@5",)


def per_question(ranks: list[int | None]) -> dict[str, np.ndarray]:
    """Per-question scores whose means are the reported metrics."""
    if not ranks:
        raise ValueError("Evaluation needs at least one question")
    r = np.array([np.inf if x is None else x for x in ranks], dtype=float)
    scores = {f"hit@{k}": (r <= k).astype(float) for k in CUTOFFS}
    scores["mrr@5"] = np.where(r <= 5, 1 / r, 0.0)
    return scores


def bootstrap_ci(values: np.ndarray, n_resamples: int = 10_000, seed: int = 0,
                 level: float = 0.95) -> tuple[float, float]:
    """Percentile bootstrap interval for the mean of ``values``."""
    values = np.asarray(values, dtype=float)
    rng = np.random.default_rng(seed)
    means = values[rng.integers(0, len(values), (n_resamples, len(values)))].mean(axis=1)
    alpha = (1 - level) / 2
    return float(np.quantile(means, alpha)), float(np.quantile(means, 1 - alpha))


def summarize(ranks: list[int | None], n_resamples: int = 10_000, seed: int = 0) -> dict:
    """Point estimate and 95 % bootstrap interval for every metric."""
    return {name: {"mean": float(v.mean()), "ci95": bootstrap_ci(v, n_resamples, seed)}
            for name, v in per_question(ranks).items()}


def paired_permutation_test(a: np.ndarray, b: np.ndarray, n_permutations: int = 10_000,
                            seed: int = 0) -> dict:
    """Two-sided sign-flip test of mean(a - b) = 0 for paired per-question scores.

    Under the null the two systems are exchangeable on each question, so the sign of
    each difference is random. The +1 correction keeps p strictly positive.
    """
    diff = np.asarray(a, dtype=float) - np.asarray(b, dtype=float)
    if diff.ndim != 1 or not len(diff):
        raise ValueError("Paired scores must be equal-length, nonempty vectors")
    observed = abs(diff.mean())
    rng = np.random.default_rng(seed)
    signs = rng.choice((-1.0, 1.0), size=(n_permutations, len(diff)))
    null = np.abs((signs * diff).mean(axis=1))
    return {
        "mean_difference": float(diff.mean()),
        "ci95": bootstrap_ci(diff, n_permutations, seed),
        "p_value": float((np.sum(null >= observed - 1e-12) + 1) / (n_permutations + 1)),
        "wins": int((diff > 0).sum()), "losses": int((diff < 0).sum()), "ties": int((diff == 0).sum()),
    }


def holm(p_values: dict[str, float]) -> dict[str, float]:
    """Holm–Bonferroni adjusted p-values (controls family-wise error)."""
    ordered = sorted(p_values.items(), key=lambda item: item[1])
    adjusted, running = {}, 0.0
    for i, (name, p) in enumerate(ordered):
        running = max(running, min(1.0, (len(ordered) - i) * p))
        adjusted[name] = running
    return adjusted


def spearman(x: np.ndarray, y: np.ndarray) -> float:
    """Spearman rank correlation with average ranks for ties (no SciPy dependency)."""
    def ranks(v):
        v = np.asarray(v, dtype=float)
        order = np.argsort(v, kind="stable")
        r = np.empty(len(v))
        r[order] = np.arange(len(v), dtype=float)
        for value in np.unique(v):
            mask = v == value
            r[mask] = r[mask].mean()
        return r
    rx, ry = ranks(x), ranks(y)
    if rx.std() == 0 or ry.std() == 0:
        return float("nan")
    return float(np.corrcoef(rx, ry)[0, 1])
