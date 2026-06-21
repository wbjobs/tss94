import numpy as np
from scipy.integrate import odeint
from scipy.optimize import differential_evolution
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional
import sympy as sp
import warnings

from .equations import EQUATION_TEMPLATES, EquationTemplate, compile_ode_rhs, t_sym, x_sym


warnings.filterwarnings('ignore')


@dataclass
class FitResult:
    equation_name: str
    display_name: str
    params: Dict[str, float]
    x0: List[float]
    r_squared: float
    rmse: float
    aic: float
    bic: float
    fitted_curve: List[float]
    time_points: List[float]
    original_data: List[float]
    latex_equation: str
    description: str
    order: int
    is_best: bool = False
    confidence_score: float = 0.0


def compute_r_squared(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    ss_res = np.sum((y_true - y_pred) ** 2)
    ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
    if ss_tot == 0:
        return 0.0
    return 1 - ss_res / ss_tot


def compute_rmse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return np.sqrt(np.mean((y_true - y_pred) ** 2))


def compute_aic(y_true: np.ndarray, y_pred: np.ndarray, n_params: int) -> float:
    n = len(y_true)
    rss = np.sum((y_true - y_pred) ** 2)
    if rss <= 0:
        rss = 1e-10
    return n * np.log(rss / n) + 2 * n_params


def compute_bic(y_true: np.ndarray, y_pred: np.ndarray, n_params: int) -> float:
    n = len(y_true)
    rss = np.sum((y_true - y_pred) ** 2)
    if rss <= 0:
        rss = 1e-10
    return n * np.log(rss / n) + n_params * np.log(n)


def simulate_ode(
    template: EquationTemplate,
    params: np.ndarray,
    t: np.ndarray,
    x0: List[float]
) -> np.ndarray:
    ode_func = compile_ode_rhs(template)
    sol = odeint(ode_func, x0, t, args=tuple(params))
    return sol[:, 0]


def estimate_initial_conditions(
    template: EquationTemplate,
    t_data: np.ndarray,
    y_data: np.ndarray
) -> List[float]:
    x0 = [y_data[0]]
    if template.order == 2:
        if len(y_data) > 1 and len(t_data) > 1:
            dt = t_data[1] - t_data[0]
            if dt > 0:
                dx0 = (y_data[1] - y_data[0]) / dt
            else:
                dx0 = 0.0
        else:
            dx0 = 0.0
        x0.append(dx0)
    return x0


def fit_equation(
    template: EquationTemplate,
    t_data: np.ndarray,
    y_data: np.ndarray
) -> Optional[FitResult]:
    n_params = len(template.params)
    
    def objective(params):
        x0_guess = estimate_initial_conditions(template, t_data, y_data)
        try:
            y_pred = simulate_ode(template, params, t_data, x0_guess)
            if np.any(np.isnan(y_pred)) or np.any(np.isinf(y_pred)):
                return 1e10
            return np.sum((y_data - y_pred) ** 2)
        except Exception:
            return 1e10
    
    bounds = template.param_bounds
    
    try:
        result_de = differential_evolution(
            objective,
            bounds=bounds,
            maxiter=150,
            popsize=12,
            tol=1e-8,
            seed=42,
            polish=True,
            workers=1
        )
        best_params = result_de.x
        best_x0 = estimate_initial_conditions(template, t_data, y_data)
        best_y_pred = simulate_ode(template, best_params, t_data, best_x0)
    except Exception as e:
        return None
    
    if np.any(np.isnan(best_y_pred)) or np.any(np.isinf(best_y_pred)):
        return None
    
    r2 = compute_r_squared(y_data, best_y_pred)
    rmse = compute_rmse(y_data, best_y_pred)
    aic = compute_aic(y_data, best_y_pred, n_params)
    bic = compute_bic(y_data, best_y_pred, n_params)
    confidence = compute_confidence_score(r2, rmse, y_data, n_params)
    
    latex_eq = generate_latex_equation(template, best_params)
    
    params_dict = {name: float(val) for name, val in zip(template.params, best_params)}
    
    return FitResult(
        equation_name=template.name,
        display_name=template.display_name,
        params=params_dict,
        x0=[float(v) for v in best_x0],
        r_squared=float(r2),
        rmse=float(rmse),
        aic=float(aic),
        bic=float(bic),
        fitted_curve=best_y_pred.tolist(),
        time_points=t_data.tolist(),
        original_data=y_data.tolist(),
        latex_equation=latex_eq,
        description=template.description,
        order=template.order,
        confidence_score=float(confidence)
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


def compute_confidence_score(r2: float, rmse: float, y_data: np.ndarray, n_params: int) -> float:
    r2_score = max(0.0, min(1.0, r2))
    
    data_range = np.max(y_data) - np.min(y_data)
    if data_range > 0:
        rmse_norm = rmse / data_range
        rmse_score = max(0.0, 1.0 - rmse_norm * 5)
    else:
        rmse_score = 0.5
    
    n = len(y_data)
    if n_params > 0 and n > n_params + 1:
        adj_r2 = 1 - (1 - r2) * (n - 1) / (n - n_params - 1)
        adj_r2_score = max(0.0, min(1.0, adj_r2))
    else:
        adj_r2_score = r2_score
    
    score = 0.5 * r2_score + 0.3 * adj_r2_score + 0.2 * rmse_score
    return max(0.0, min(1.0, score))


def fit_all_equations(t_data: np.ndarray, y_data: np.ndarray) -> List[FitResult]:
    results = []
    
    for template in EQUATION_TEMPLATES:
        try:
            result = fit_equation(template, t_data, y_data)
            if result is not None:
                results.append(result)
        except Exception as e:
            print(f"Error fitting {template.name}: {e}")
    
    results.sort(key=lambda r: r.r_squared, reverse=True)
    
    if results:
        results[0].is_best = True
    
    return results
