import numpy as np
from typing import Optional, Tuple
from dataclasses import dataclass

from .preprocess import PreprocessResult
from .stability import StabilityInfo, compute_stability_penalty


@dataclass
class QualityScores:
    r_squared: float
    adjusted_r_squared: float
    rmse: float
    normalized_rmse: float
    aic: float
    aic_c: float
    bic: float
    mallows_cp: float
    complexity_penalty: float
    stability_penalty: float
    noise_penalty: float
    composite_score: float
    confidence_score: float


def compute_adjusted_r_squared(
    r2: float,
    n: int,
    k: int
) -> float:
    if n <= k + 1 or k <= 0:
        return max(0.0, r2)
    return 1 - (1 - r2) * (n - 1) / (n - k - 1)


def compute_aic_c(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    n_params: int
) -> float:
    n = len(y_true)
    k = n_params
    rss = np.sum((y_true - y_pred) ** 2)
    if rss <= 0:
        rss = 1e-10
    
    aic = n * np.log(rss / n) + 2 * k
    
    if n <= k + 2:
        return aic + 100
    
    correction = 2 * k * (k + 1) / (n - k - 1)
    return aic + correction


def compute_mallows_cp(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    n_params: int,
    full_model_rss: Optional[float] = None,
    full_model_params: Optional[int] = None
) -> float:
    n = len(y_true)
    rss_p = np.sum((y_true - y_pred) ** 2)
    k_p = n_params
    
    if rss_p <= 0:
        rss_p = 1e-10
    
    if full_model_rss is None or full_model_params is None:
        sigma_sq_est = rss_p / (n - max(1, k_p))
        cp = rss_p / sigma_sq_est - n + 2 * k_p
    else:
        p_full = full_model_params
        sigma_sq_est = full_model_rss / (n - p_full - 1)
        if sigma_sq_est <= 0:
            sigma_sq_est = 1e-10
        cp = rss_p / sigma_sq_est - n + 2 * k_p
    
    return float(cp)


def compute_complexity_penalty(
    n_params: int,
    order: int,
    n_data: int
) -> float:
    base_penalty = n_params / max(1, n_data) * 10
    
    order_penalty = (order - 1) * 0.05
    
    total_penalty = base_penalty + order_penalty
    
    return min(0.5, total_penalty)


def compute_noise_penalty(
    noise_level: float,
    r2: float,
    n_params: int
) -> float:
    if noise_level < 0.02:
        return 0.0
    
    overfit_risk = noise_level * 2.0 * (1 + n_params * 0.1)
    
    if r2 > 1 - noise_level:
        overfit_risk *= (1 + (r2 - (1 - noise_level)) * 10)
    
    return min(0.4, overfit_risk)


def normalize_scores_across_models(
    all_results: list,
    score_key: str = "composite_score"
) -> None:
    if len(all_results) == 0:
        return
    
    aic_values = [r.get("aic", 0) for r in all_results if "aic" in r]
    bic_values = [r.get("bic", 0) for r in all_results if "bic" in r]
    
    if len(aic_values) > 1:
        aic_min = min(aic_values)
        aic_max = max(aic_values)
        aic_range = aic_max - aic_min if aic_max > aic_min else 1.0
        
        for r in all_results:
            if "aic" in r:
                r["aic_normalized"] = 1 - (r["aic"] - aic_min) / aic_range
    
    if len(bic_values) > 1:
        bic_min = min(bic_values)
        bic_max = max(bic_values)
        bic_range = bic_max - bic_min if bic_max > bic_min else 1.0
        
        for r in all_results:
            if "bic" in r:
                r["bic_normalized"] = 1 - (r["bic"] - bic_min) / bic_range


def compute_quality_scores(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    n_params: int,
    order: int,
    preprocess: PreprocessResult,
    stability: Optional[StabilityInfo] = None,
    all_results_rss: Optional[list] = None
) -> QualityScores:
    n = len(y_true)
    
    ss_res = np.sum((y_true - y_pred) ** 2)
    ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
    
    if ss_tot == 0:
        r2 = 0.0
    else:
        r2 = 1 - ss_res / ss_tot
    
    r2 = max(0.0, min(1.0, r2))
    adj_r2 = compute_adjusted_r_squared(r2, n, n_params)
    
    rmse = np.sqrt(np.mean((y_true - y_pred) ** 2))
    data_range = np.max(y_true) - np.min(y_true)
    if data_range > 1e-10:
        nrmse = rmse / data_range
    else:
        nrmse = 1.0
    
    aic = compute_aic_c(y_true, y_pred, n_params)
    aic_c = compute_aic_c(y_true, y_pred, n_params)
    bic = n * np.log(ss_res / n if ss_res > 0 else 1e-10) + n_params * np.log(n)
    
    full_rss = None
    full_params = None
    if all_results_rss is not None and len(all_results_rss) > 0:
        full_rss = min(all_results_rss)
        full_params = max(n_params, 5)
    
    mallows_cp = compute_mallows_cp(y_true, y_pred, n_params, full_rss, full_params)
    
    complexity_pen = compute_complexity_penalty(n_params, order, n)
    noise_pen = compute_noise_penalty(preprocess.noise_level, r2, n_params)
    
    stab_pen = 0.0
    if stability is not None:
        stab_pen = compute_stability_penalty(stability) / 100.0
        stab_pen = min(0.5, stab_pen)
    
    adj_r2_score = max(0.0, min(1.0, adj_r2))
    nrmse_score = max(0.0, 1.0 - nrmse * 3)
    
    composite = (
        0.35 * adj_r2_score +
        0.25 * nrmse_score +
        0.20 * (1.0 - complexity_pen) +
        0.15 * (1.0 - noise_pen) +
        0.05 * (1.0 - stab_pen)
    )
    composite = max(0.0, min(1.0, composite))
    
    if stability is not None and not stability.is_stable:
        composite *= 0.3
    
    if preprocess.noise_level > 0.15:
        base_confidence = 0.6
    elif preprocess.noise_level > 0.05:
        base_confidence = 0.8
    else:
        base_confidence = 0.95
    
    confidence = base_confidence * composite
    
    if adj_r2 < 0.5:
        confidence *= 0.5
    elif adj_r2 < 0.7:
        confidence *= 0.8
    elif adj_r2 < 0.85:
        confidence *= 0.9
    
    confidence = max(0.0, min(1.0, confidence))
    
    return QualityScores(
        r_squared=float(r2),
        adjusted_r_squared=float(adj_r2),
        rmse=float(rmse),
        normalized_rmse=float(nrmse),
        aic=float(aic),
        aic_c=float(aic_c),
        bic=float(bic),
        mallows_cp=float(mallows_cp),
        complexity_penalty=float(complexity_pen),
        stability_penalty=float(stab_pen),
        noise_penalty=float(noise_pen),
        composite_score=float(composite),
        confidence_score=float(confidence)
    )
