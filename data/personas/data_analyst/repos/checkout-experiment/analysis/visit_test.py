import numpy as np
from scipy import stats


def two_proportion_test(wins_a: int, n_a: int, wins_b: int, n_b: int) -> dict:
    p_a, p_b = wins_a / n_a, wins_b / n_b
    pooled = (wins_a + wins_b) / (n_a + n_b)
    standard_error = np.sqrt(pooled * (1 - pooled) * (1 / n_a + 1 / n_b))
    z = (p_b - p_a) / standard_error
    return {"lift": p_b / p_a - 1, "z": z, "p_value": 2 * (1 - stats.norm.cdf(abs(z)))}


def bootstrap_difference(a: np.ndarray, b: np.ndarray, rounds: int = 5000, seed: int = 11) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    diffs = [rng.choice(b, len(b)).mean() - rng.choice(a, len(a)).mean() for _ in range(rounds)]
    return float(np.percentile(diffs, 2.5)), float(np.percentile(diffs, 97.5))


def required_sample_size(base_rate: float, minimum_lift: float, alpha=0.05, power=0.8) -> int:
    effect = base_rate * minimum_lift
    z_alpha, z_power = stats.norm.ppf(1 - alpha / 2), stats.norm.ppf(power)
    return int(np.ceil(2 * base_rate * (1 - base_rate) * ((z_alpha + z_power) / effect) ** 2))
