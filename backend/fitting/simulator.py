import numpy as np
from typing import Dict, List, Optional
import sympy as sp

from .equations import EQUATION_TEMPLATES, EquationTemplate, t_sym, x_sym
from .stability import safe_odeint, check_solution_stability, StabilityInfo


def get_template_by_name(name: str) -> Optional[EquationTemplate]:
    for t in EQUATION_TEMPLATES:
        if t.name == name:
            return t
    return None


def get_all_templates_info() -> List[Dict]:
    info_list = []
    for t in EQUATION_TEMPLATES:
        info_list.append({
            "name": t.name,
            "display_name": t.display_name,
            "order": t.order,
            "params": t.params,
            "param_bounds": [list(b) for b in t.param_bounds],
            "description": t.description
        })
    return info_list


def simulate_ode(
    equation_name: str,
    params: Dict[str, float],
    x0: List[float],
    time_points: List[float],
    generate_latex: bool = True
) -> Dict:
    template = get_template_by_name(equation_name)
    if template is None:
        return {
            "success": False,
            "error": f"Unknown equation: {equation_name}",
            "available_equations": [t.name for t in EQUATION_TEMPLATES]
        }
    
    param_values = []
    for p_name in template.params:
        if p_name not in params:
            return {
                "success": False,
                "error": f"Missing parameter: {p_name}",
                "required_params": template.params
            }
        param_values.append(float(params[p_name]))
    
    if len(x0) != template.order:
        return {
            "success": False,
            "error": f"Initial conditions x0 must have {template.order} elements (equation order), got {len(x0)}"
        }
    
    t = np.asarray(time_points, dtype=float)
    x0_list = [float(v) for v in x0]
    param_arr = np.asarray(param_values, dtype=float)
    
    y, stability = safe_odeint(template, param_arr, t, x0_list)
    
    if y is None:
        return {
            "success": False,
            "error": stability.message if stability else "Simulation failed",
            "is_stable": False,
            "stability_info": {
                "is_stable": False,
                "has_nan": stability.has_nan if stability else True,
                "has_inf": stability.has_inf if stability else False,
                "has_overflow": stability.has_overflow if stability else False,
                "message": stability.message if stability else "Unknown error"
            }
        }
    
    r2_score = None
    rmse_score = None
    
    latex_equation = None
    if generate_latex:
        latex_equation = _generate_latex(template, param_arr)
    
    return {
        "success": True,
        "equation_name": template.name,
        "display_name": template.display_name,
        "order": template.order,
        "params": params,
        "x0": x0_list,
        "time_points": t.tolist(),
        "simulated_values": y.tolist(),
        "is_stable": stability.is_stable,
        "stability_info": {
            "is_stable": stability.is_stable,
            "has_nan": stability.has_nan,
            "has_inf": stability.has_inf,
            "has_overflow": stability.has_overflow,
            "max_abs_value": stability.max_abs_value,
            "oscillation_detected": stability.oscillation_detected,
            "stiffness_ratio": stability.stiffness_ratio,
            "message": stability.message
        },
        "latex_equation": latex_equation
    }


def _generate_latex(template: EquationTemplate, params: np.ndarray) -> str:
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
    return _fractions_to_decimals(latex_str)


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
    return result


def compare_with_original(
    simulated_values: List[float],
    original_values: List[float]
) -> Dict:
    y_sim = np.asarray(simulated_values, dtype=float)
    y_orig = np.asarray(original_values, dtype=float)
    
    if len(y_sim) != len(y_orig):
        return {
            "success": False,
            "error": f"Length mismatch: simulated has {len(y_sim)}, original has {len(y_orig)}"
        }
    
    mask = np.isfinite(y_sim) & np.isfinite(y_orig)
    if not np.any(mask):
        return {"success": False, "error": "No valid values to compare"}
    
    y_sim_clean = y_sim[mask]
    y_orig_clean = y_orig[mask]
    
    ss_res = np.sum((y_orig_clean - y_sim_clean) ** 2)
    ss_tot = np.sum((y_orig_clean - np.mean(y_orig_clean)) ** 2)
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0
    r2 = max(0.0, min(1.0, r2))
    
    rmse = float(np.sqrt(np.mean((y_orig_clean - y_sim_clean) ** 2)))
    
    data_range = np.max(y_orig_clean) - np.min(y_orig_clean)
    nrmse = rmse / data_range if data_range > 1e-10 else 1.0
    
    mae = float(np.mean(np.abs(y_orig_clean - y_sim_clean)))
    
    return {
        "success": True,
        "r_squared": float(r2),
        "rmse": rmse,
        "normalized_rmse": float(nrmse),
        "mae": mae,
        "max_error": float(np.max(np.abs(y_orig_clean - y_sim_clean)))
    }
