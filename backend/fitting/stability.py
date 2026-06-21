import numpy as np
from scipy.integrate import odeint
from typing import Tuple, Optional, List
from dataclasses import dataclass

from .equations import EquationTemplate, compile_ode_rhs


@dataclass
class StabilityInfo:
    is_stable: bool
    has_nan: bool
    has_inf: bool
    has_overflow: bool
    max_abs_value: float
    max_derivative: float
    oscillation_detected: bool
    stiffness_ratio: float
    message: str = ""


def check_solution_stability(
    y: np.ndarray,
    t: np.ndarray,
    threshold_magnitude: float = 1e8,
    threshold_derivative: float = 1e10
) -> StabilityInfo:
    has_nan = bool(np.any(np.isnan(y)))
    has_inf = bool(np.any(np.isinf(y)))
    
    finite_mask = np.isfinite(y)
    if not np.any(finite_mask):
        return StabilityInfo(
            is_stable=False,
            has_nan=has_nan,
            has_inf=has_inf,
            has_overflow=True,
            max_abs_value=float('inf'),
            max_derivative=float('inf'),
            oscillation_detected=False,
            stiffness_ratio=0.0,
            message="All values are NaN or Inf"
        )
    
    y_finite = y[finite_mask]
    max_abs = float(np.max(np.abs(y_finite))) if len(y_finite) > 0 else 0.0
    
    has_overflow = max_abs > threshold_magnitude
    
    dy_dt = np.gradient(y, t) if len(y) >= 2 else np.array([0.0])
    dy_finite = dy_dt[np.isfinite(dy_dt)]
    max_dy = float(np.max(np.abs(dy_finite))) if len(dy_finite) > 0 else 0.0
    
    oscillation_detected = False
    if len(y) >= 10:
        sign_changes = 0
        for i in range(1, len(dy_dt)):
            if np.isfinite(dy_dt[i]) and np.isfinite(dy_dt[i-1]):
                if dy_dt[i] * dy_dt[i-1] < 0:
                    sign_changes += 1
        if sign_changes > len(y) * 0.3:
            oscillation_detected = True
    
    stiffness_ratio = 0.0
    if len(y) >= 3 and max_abs > 1e-10:
        second_diff = np.diff(y, n=2)
        if np.all(np.isfinite(second_diff)) and len(second_diff) > 0:
            max_second = np.max(np.abs(second_diff))
            dt = t[1] - t[0] if len(t) > 1 else 1.0
            if dt > 0 and max_abs > 0:
                stiffness_ratio = float(max_second * dt / max_abs)
    
    is_stable = not (has_nan or has_inf or has_overflow)
    
    message = ""
    if has_nan:
        message += "NaN detected; "
    if has_inf:
        message += "Inf detected; "
    if has_overflow:
        message += f"Overflow (|y|={max_abs:.2e} > {threshold_magnitude:.0e}); "
    if oscillation_detected:
        message += "High oscillation detected; "
    if stiffness_ratio > 100:
        message += f"High stiffness ratio ({stiffness_ratio:.1f}); "
    
    message = message.rstrip("; ")
    
    return StabilityInfo(
        is_stable=is_stable,
        has_nan=has_nan,
        has_inf=has_inf,
        has_overflow=has_overflow,
        max_abs_value=max_abs,
        max_derivative=max_dy,
        oscillation_detected=oscillation_detected,
        stiffness_ratio=stiffness_ratio,
        message=message
    )


def safe_odeint(
    template: EquationTemplate,
    params: np.ndarray,
    t: np.ndarray,
    x0: List[float],
    max_step: Optional[float] = None,
    rtol: float = 1e-8,
    atol: float = 1e-10
) -> Tuple[Optional[np.ndarray], StabilityInfo]:
    if len(params) == 0:
        return None, StabilityInfo(
            is_stable=False, has_nan=True, has_inf=False, has_overflow=False,
            max_abs_value=0.0, max_derivative=0.0, oscillation_detected=False,
            stiffness_ratio=0.0, message="Empty parameters"
        )
    
    if np.any(np.isnan(params)) or np.any(np.isinf(params)):
        return None, StabilityInfo(
            is_stable=False, has_nan=True, has_inf=False, has_overflow=False,
            max_abs_value=0.0, max_derivative=0.0, oscillation_detected=False,
            stiffness_ratio=0.0, message="Invalid parameters"
        )
    
    for i, xi in enumerate(x0):
        if np.isnan(xi) or np.isinf(xi):
            x0[i] = 0.0
    
    t_max = t[-1] - t[0]
    if t_max <= 0:
        return None, StabilityInfo(
            is_stable=False, has_nan=False, has_inf=False, has_overflow=False,
            max_abs_value=0.0, max_derivative=0.0, oscillation_detected=False,
            stiffness_ratio=0.0, message="Invalid time range"
        )
    
    if max_step is None:
        dt_min = np.min(np.diff(t)) if len(t) > 1 else t_max
        max_step = max(dt_min * 10, t_max / 100)
    
    ode_func = compile_ode_rhs(template)
    
    try:
        with np.errstate(over='raise', under='ignore', divide='raise', invalid='raise'):
            sol = odeint(
                ode_func,
                x0,
                t,
                args=tuple(params),
                mxstep=5000,
                rtol=rtol,
                atol=atol,
                hmax=max_step,
                full_output=False
            )
    except Warning:
        return None, StabilityInfo(
            is_stable=False, has_nan=True, has_inf=False, has_overflow=False,
            max_abs_value=0.0, max_derivative=0.0, oscillation_detected=False,
            stiffness_ratio=0.0, message="ODE solver warning"
        )
    except FloatingPointError as e:
        return None, StabilityInfo(
            is_stable=False, has_nan=False, has_inf=False, has_overflow=True,
            max_abs_value=0.0, max_derivative=0.0, oscillation_detected=False,
            stiffness_ratio=0.0, message=f"Floating point error: {str(e)}"
        )
    except Exception as e:
        error_msg = str(e)
        is_overflow = "overflow" in error_msg.lower() or "larger" in error_msg.lower()
        return None, StabilityInfo(
            is_stable=False,
            has_nan="nan" in error_msg.lower(),
            has_inf="inf" in error_msg.lower(),
            has_overflow=is_overflow,
            max_abs_value=0.0,
            max_derivative=0.0,
            oscillation_detected=False,
            stiffness_ratio=0.0,
            message=f"Solver error: {error_msg[:100]}"
        )
    
    if sol is None:
        return None, StabilityInfo(
            is_stable=False, has_nan=True, has_inf=False, has_overflow=False,
            max_abs_value=0.0, max_derivative=0.0, oscillation_detected=False,
            stiffness_ratio=0.0, message="No solution"
        )
    
    y = sol[:, 0]
    stability = check_solution_stability(y, t)
    
    if not stability.is_stable:
        return None, stability
    
    return y, stability


def compute_stability_penalty(stability: StabilityInfo) -> float:
    penalty = 0.0
    
    if not stability.is_stable:
        penalty += 100.0
    
    if stability.has_overflow:
        penalty += 50.0
    
    if stability.has_nan or stability.has_inf:
        penalty += 100.0
    
    if stability.oscillation_detected:
        penalty += 5.0
    
    if stability.stiffness_ratio > 100:
        penalty += min(20.0, np.log10(stability.stiffness_ratio + 1) * 3)
    
    if stability.max_abs_value > 1e5:
        penalty += min(10.0, np.log10(stability.max_abs_value / 1e5) * 2)
    
    return penalty
