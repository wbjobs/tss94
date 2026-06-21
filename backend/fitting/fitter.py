import numpy as np
from scipy.optimize import differential_evolution
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional
import sympy as sp
import warnings

from .equations import EQUATION_TEMPLATES, EquationTemplate, t_sym, x_sym
from .preprocess import auto_smooth, PreprocessResult, estimate_derivatives
from .stability import safe_odeint, StabilityInfo, compute_stability_penalty
from .scoring import compute_quality_scores, QualityScores, normalize_scores_across_models


warnings.filterwarnings('ignore')


@dataclass
class FitResult:
    equation_name: str
    display_name: str
    params: Dict[str, float]
    x0: List[float]
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
    fitted_curve: List[float]
    time_points: List[float]
    original_data: List[float]
    smoothed_data: List[float]
    latex_equation: str
    description: str
    order: int
    noise_level: float
    signal_to_noise: float
    smooth_method: str
    is_stable: bool
    stability_message: str
    is_best: bool = False
    confidence_score: float = 0.0


def estimate_initial_conditions(
    template: EquationTemplate,
    t_data: np.ndarray,
    y_data: np.ndarray,
    dy_data: Optional[np.ndarray] = None
) -> List[float]:
    x0 = [float(y_data[0])]
    if template.order == 2:
        if dy_data is not None and len(dy_data) > 0:
            dx0 = float(dy_data[0])
        elif len(y_data) > 1 and len(t_data) > 1:
            dt = t_data[1] - t_data[0]
            if dt > 0:
                dx0 = float((y_data[1] - y_data[0]) / dt)
            else:
                dx0 = 0.0
        else:
            dx0 = 0.0
        x0.append(float(dx0))
    return x0


def fit_equation(
    template: EquationTemplate,
    t_data: np.ndarray,
    y_data: np.ndarray,
    y_smoothed: np.ndarray,
    dy_smoothed: Optional[np.ndarray],
    preprocess: PreprocessResult
) -> Optional[FitResult]:
    n_params = len(template.params)
    
    def objective(params):
        x0_guess = estimate_initial_conditions(template, t_data, y_smoothed, dy_smoothed)
        
        y_pred, stability = safe_odeint(template, params, t_data, x0_guess)
        
        if y_pred is None:
            penalty = compute_stability_penalty(stability) if stability else 100
            return np.sum((y_smoothed - np.mean(y_smoothed)) ** 2) * 10 + penalty
        
        stab_pen = compute_stability_penalty(stability) * 0.1
        
        residuals = y_smoothed - y_pred
        weighted_residuals = residuals
        
        return float(np.sum(weighted_residuals ** 2) + stab_pen)
    
    bounds = template.param_bounds
    
    try:
        result_de = differential_evolution(
            objective,
            bounds=bounds,
            maxiter=200,
            popsize=15,
            tol=1e-9,
            seed=42,
            polish=True,
            workers=1,
            mutation=(0.5, 1.5),
            recombination=0.7,
            strategy='best1bin'
        )
        best_params = result_de.x
    except Exception as e:
        return None
    
    best_x0 = estimate_initial_conditions(template, t_data, y_smoothed, dy_smoothed)
    best_y_pred, stability = safe_odeint(template, best_params, t_data, best_x0)
    
    if best_y_pred is None:
        return None
    
    if not stability.is_stable and stability.has_overflow:
        return None
    
    all_rss = None
    
    scores = compute_quality_scores(
        y_true=y_smoothed,
        y_pred=best_y_pred,
        n_params=n_params,
        order=template.order,
        preprocess=preprocess,
        stability=stability,
        all_results_rss=all_rss
    )
    
    latex_eq = generate_latex_equation(template, best_params)
    
    params_dict = {name: float(val) for name, val in zip(template.params, best_params)}
    
    return FitResult(
        equation_name=template.name,
        display_name=template.display_name,
        params=params_dict,
        x0=[float(v) for v in best_x0],
        r_squared=scores.r_squared,
        adjusted_r_squared=scores.adjusted_r_squared,
        rmse=scores.rmse,
        normalized_rmse=scores.normalized_rmse,
        aic=scores.aic,
        aic_c=scores.aic_c,
        bic=scores.bic,
        mallows_cp=scores.mallows_cp,
        complexity_penalty=scores.complexity_penalty,
        stability_penalty=scores.stability_penalty,
        noise_penalty=scores.noise_penalty,
        composite_score=scores.composite_score,
        fitted_curve=best_y_pred.tolist(),
        time_points=t_data.tolist(),
        original_data=preprocess.y_original.tolist(),
        smoothed_data=y_smoothed.tolist(),
        latex_equation=latex_eq,
        description=template.description,
        order=template.order,
        noise_level=preprocess.noise_level,
        signal_to_noise=preprocess.signal_to_noise,
        smooth_method=preprocess.smooth_method,
        is_stable=stability.is_stable,
        stability_message=stability.message,
        confidence_score=scores.confidence_score
    )


def generate_latex_equation(template: EquationTemplate, params: np.ndarray) -> str:
    param_symbols = {}
    for atom in template.ode_rhs.atoms(sp.Symbol):
        if str(atom) in template.params:
            param_symbols[str(atom)] = atom
    
    substitutions = {}
    for i, p_name in enumerate(template.params):
        if p_name in param_symbols:
            p_sym = param_symbols[p_name]
        else:
            p_sym = sp.Symbol(p_name)
        val = float(params[i])
        substitutions[p_sym] = sp.Float(val, 6)
    
    rhs = template.ode_rhs.subs(substitutions)
    
    if template.order == 1:
        lhs = sp.diff(x_sym, t_sym)
    else:
        lhs = sp.diff(x_sym, t_sym, 2)
    
    equation = sp.Eq(lhs, rhs)
    latex_str = sp.latex(equation, mul_symbol='\\cdot ')
    
    latex_str = _fractions_to_decimals(latex_str)
    
    return latex_str


def _fractions_to_decimals(latex_str: str) -> str:
    import re
    
    pattern = r'\\frac\{(-?\d+\.?\d*)\}\{(-?\d+\.?\d*)\}'
    
    def replace_frac(match):
        num = float(match.group(1))
        den = float(match.group(2))
        if den == 0:
            return match.group(0)
        result = num / den
        if abs(result) >= 1000 or (abs(result) < 0.001 and result != 0):
            return f"{result:.4e}"
        else:
            formatted = f"{result:.4f}"
            formatted = formatted.rstrip('0').rstrip('.') if '.' in formatted else formatted
            return formatted
    
    result = re.sub(pattern, replace_frac, latex_str)
    
    pattern2 = r'\\frac\{(-?\d+\.?\d*) \\cdot \(([^)]+)\)\}\{(-?\d+\.?\d*)\}'
    def replace_frac2(match):
        num = float(match.group(1))
        den = float(match.group(3))
        inner = match.group(2)
        if den == 0:
            return match.group(0)
        coeff = num / den
        if abs(coeff) >= 1000 or (abs(coeff) < 0.001 and coeff != 0):
            coeff_str = f"{coeff:.4e}"
        else:
            coeff_str = f"{coeff:.4f}"
            coeff_str = coeff_str.rstrip('0').rstrip('.') if '.' in coeff_str else coeff_str
        return f"{coeff_str} \\cdot ({inner})"
    
    result = re.sub(pattern2, replace_frac2, result)
    
    return result


def fit_all_equations(t_data: np.ndarray, y_data: np.ndarray) -> List[FitResult]:
    t_data = np.asarray(t_data, dtype=float)
    y_data = np.asarray(y_data, dtype=float)
    
    valid_mask = ~(np.isnan(t_data) | np.isnan(y_data) | np.isinf(t_data) | np.isinf(y_data))
    t_data = t_data[valid_mask]
    y_data = y_data[valid_mask]
    
    sort_idx = np.argsort(t_data)
    t_data = t_data[sort_idx]
    y_data = y_data[sort_idx]
    
    preprocess = auto_smooth(t_data, y_data)
    
    dy_smoothed, d2y_smoothed = estimate_derivatives(
        preprocess.t_smoothed, preprocess.y_smoothed, smooth=True
    )
    
    results = []
    
    for template in EQUATION_TEMPLATES:
        try:
            result = fit_equation(
                template, t_data, y_data,
                preprocess.y_smoothed, dy_smoothed, preprocess
            )
            if result is not None:
                results.append(result)
        except Exception as e:
            print(f"Error fitting {template.name}: {e}")
    
    if not results:
        return []
    
    results_dicts = []
    for r in results:
        results_dicts.append({
            "aic": r.aic,
            "bic": r.bic,
            "composite_score": r.composite_score,
            "r_squared": r.r_squared
        })
    normalize_scores_across_models(results_dicts)
    
    results.sort(key=lambda r: r.composite_score, reverse=True)
    
    if results:
        results[0].is_best = True
    
    return results
