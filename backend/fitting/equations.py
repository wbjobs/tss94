import sympy as sp
import numpy as np
from scipy.integrate import odeint
from scipy.optimize import curve_fit, differential_evolution
from dataclasses import dataclass, field
from typing import Callable, List, Dict, Tuple


@dataclass
class EquationTemplate:
    name: str
    display_name: str
    order: int
    params: List[str]
    param_bounds: List[Tuple[float, float]]
    ode_rhs: sp.Expr
    x0_guess: List[float]
    description: str = ""


t_sym = sp.Symbol('t')
x_sym = sp.Function('x')(t_sym)
dx_sym = sp.diff(x_sym, t_sym)
d2x_sym = sp.diff(dx_sym, t_sym)

a_sym, b_sym, c_sym, k_sym, r_sym, K_sym, omega_sym, zeta_sym, tau_sym = sp.symbols(
    'a b c k r K omega zeta tau', real=True
)

EQUATION_TEMPLATES: List[EquationTemplate] = [
    EquationTemplate(
        name="linear_first_order",
        display_name="一阶线性 (dx/dt = a·x + b)",
        order=1,
        params=["a", "b"],
        param_bounds=[(-10, 10), (-100, 100)],
        ode_rhs=a_sym * x_sym + b_sym,
        x0_guess=[1.0],
        description="最简单的一阶线性微分方程"
    ),
    EquationTemplate(
        name="exponential_growth",
        display_name="指数增长/衰减 (dx/dt = r·x)",
        order=1,
        params=["r"],
        param_bounds=[(-5, 5)],
        ode_rhs=r_sym * x_sym,
        x0_guess=[1.0],
        description="指数增长或衰减模型"
    ),
    EquationTemplate(
        name="logistic_growth",
        display_name="Logistic增长 (dx/dt = r·x·(1 - x/K))",
        order=1,
        params=["r", "K"],
        param_bounds=[(0.01, 10), (0.1, 1000)],
        ode_rhs=r_sym * x_sym * (1 - x_sym / K_sym),
        x0_guess=[1.0],
        description="S型增长曲线，有环境容纳量K"
    ),
    EquationTemplate(
        name="first_order_with_time_constant",
        display_name="一阶系统 (τ·dx/dt = -x + K·u)",
        order=1,
        params=["tau", "K"],
        param_bounds=[(0.01, 100), (-100, 100)],
        ode_rhs=(-x_sym + K_sym) / tau_sym,
        x0_guess=[1.0],
        description="一阶惯性系统，阶跃响应"
    ),
    EquationTemplate(
        name="second_order_oscillator",
        display_name="二阶无阻尼振荡 (d²x/dt² + ω²·x = 0)",
        order=2,
        params=["omega"],
        param_bounds=[(0.01, 50)],
        ode_rhs=-omega_sym**2 * x_sym,
        x0_guess=[1.0, 0.0],
        description="简谐振动"
    ),
    EquationTemplate(
        name="damped_oscillator",
        display_name="二阶阻尼振荡 (d²x/dt² + 2ζω·dx/dt + ω²·x = 0)",
        order=2,
        params=["omega", "zeta"],
        param_bounds=[(0.01, 50), (0, 2)],
        ode_rhs=-2 * zeta_sym * omega_sym * dx_sym - omega_sym**2 * x_sym,
        x0_guess=[1.0, 0.0],
        description="有阻尼的自由振动"
    ),
    EquationTemplate(
        name="second_order_linear",
        display_name="二阶一般线性 (d²x/dt² + a·dx/dt + b·x = c)",
        order=2,
        params=["a", "b", "c"],
        param_bounds=[(-20, 20), (-100, 100), (-100, 100)],
        ode_rhs=-a_sym * dx_sym - b_sym * x_sym + c_sym,
        x0_guess=[1.0, 0.0],
        description="二阶常系数线性非齐次微分方程"
    ),
    EquationTemplate(
        name="linear_time_varying",
        display_name="一阶时变 (dx/dt = a·t + b·x + c)",
        order=1,
        params=["a", "b", "c"],
        param_bounds=[(-10, 10), (-10, 10), (-100, 100)],
        ode_rhs=a_sym * t_sym + b_sym * x_sym + c_sym,
        x0_guess=[1.0],
        description="含时变项的一阶线性方程"
    ),
]


def compile_ode_rhs(template: EquationTemplate) -> Callable:
    params_sym = [sp.Symbol(p) for p in template.params]
    rhs = template.ode_rhs
    
    if template.order == 1:
        state_vars = [x_sym]
        func = sp.lambdify((t_sym, x_sym, *params_sym), rhs, modules='numpy')
        def ode_func(state, t, *params):
            x = state[0]
            return [float(func(t, x, *params))]
    else:
        state_vars = [x_sym, dx_sym]
        func = sp.lambdify((t_sym, x_sym, dx_sym, *params_sym), rhs, modules='numpy')
        def ode_func(state, t, *params):
            x, dx = state
            d2x = float(func(t, x, dx, *params))
            return [dx, d2x]
    
    return ode_func


def get_analytical_solution(template: EquationTemplate):
    try:
        if template.order == 1:
            sol = sp.dsolve(dx_sym - template.ode_rhs, x_sym)
        else:
            sol = sp.dsolve(d2x_sym - template.ode_rhs, x_sym)
        return sol
    except Exception:
        return None
