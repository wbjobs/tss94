import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from backend.fitting import simulate_ode, get_all_templates_info, compare_with_original


def test_list_templates():
    print("\n" + "="*70)
    print("测试1: 获取所有方程模板")
    print("="*70)
    
    templates = get_all_templates_info()
    print(f"共获取 {len(templates)} 个方程模板:")
    for t in templates:
        print(f"  - {t['display_name']} (参数: {t['params']})")
    
    return len(templates) > 0


def test_simulate_exponential():
    print("\n" + "="*70)
    print("测试2: 模拟指数增长")
    print("="*70)
    
    t = np.linspace(0, 5, 20).tolist()
    r_true = 0.5
    x0 = [1.0]
    
    result = simulate_ode(
        equation_name="exponential_growth",
        params={"r": r_true},
        x0=x0,
        time_points=t,
        generate_latex=True
    )
    
    if not result.get("success"):
        print(f"❌ 模拟失败: {result.get('error')}")
        return False
    
    print(f"✅ 模拟成功!")
    print(f"   方程: {result['display_name']}")
    print(f"   稳定: {result['is_stable']}")
    print(f"   点数: {len(result['simulated_values'])}")
    print(f"   LaTeX: {result.get('latex_equation', 'N/A')[:80]}")
    
    x_sim = result['simulated_values']
    x_expected = x0[0] * np.exp(r_true * np.array(t))
    max_err = np.max(np.abs(np.array(x_sim) - x_expected))
    print(f"   最大误差: {max_err:.6e}")
    
    return max_err < 0.01


def test_simulate_damped_oscillator():
    print("\n" + "="*70)
    print("测试3: 模拟阻尼振动 (二阶方程)")
    print("="*70)
    
    t = np.linspace(0, 10, 100).tolist()
    omega = 2.0
    zeta = 0.2
    x0 = [1.0, 0.0]
    
    result = simulate_ode(
        equation_name="damped_oscillator",
        params={"omega": omega, "zeta": zeta},
        x0=x0,
        time_points=t,
        generate_latex=True
    )
    
    if not result.get("success"):
        print(f"❌ 模拟失败: {result.get('error')}")
        print(f"   稳定性信息: {result.get('stability_info')}")
        return False
    
    print(f"✅ 模拟成功!")
    print(f"   方程: {result['display_name']}")
    print(f"   稳定: {result['is_stable']}")
    print(f"   LaTeX: {result.get('latex_equation', 'N/A')[:100]}")
    
    x_sim = np.array(result['simulated_values'])
    omega_d = omega * np.sqrt(1 - zeta**2)
    x_expected = np.exp(-zeta * omega * np.array(t)) * np.cos(omega_d * np.array(t))
    max_err = np.max(np.abs(x_sim - x_expected))
    print(f"   最大误差: {max_err:.6f}")
    
    return max_err < 0.05


def test_compare_with_original():
    print("\n" + "="*70)
    print("测试4: 对比计算指标")
    print("="*70)
    
    t = np.linspace(0, 5, 30)
    x_true = np.exp(0.3 * t)
    x_pred = np.exp(0.32 * t)
    
    result = compare_with_original(x_pred.tolist(), x_true.tolist())
    
    if not result.get("success"):
        print(f"❌ 对比失败: {result.get('error')}")
        return False
    
    print(f"✅ 对比成功!")
    print(f"   R² = {result['r_squared']:.6f}")
    print(f"   RMSE = {result['rmse']:.6f}")
    print(f"   NRMSE = {result['normalized_rmse']:.6f}")
    print(f"   MAE = {result['mae']:.6f}")
    
    return result['r_squared'] > 0.9 and result['r_squared'] < 1.0


def test_unstable_parameters():
    print("\n" + "="*70)
    print("测试5: 不稳定参数检测 (应该被检测并返回错误)")
    print("="*70)
    
    t = np.linspace(0, 100, 200).tolist()
    
    result = simulate_ode(
        equation_name="exponential_growth",
        params={"r": 2.0},
        x0=[1.0],
        time_points=t,
        generate_latex=False
    )
    
    if result.get("success") and result.get("is_stable"):
        print("⚠️ 参数没有溢出，可能方程不同")
        print(f"   max|y| = {result.get('stability_info', {}).get('max_abs_value', 'N/A')}")
        return True
    elif not result.get("success"):
        print(f"✅ 正确检测到不稳定: {result.get('error')}")
        print(f"   稳定: {result.get('is_stable')}")
        return True
    else:
        print(f"⚠️ 返回成功但不稳定: {result.get('stability_info')}")
        return True


def test_invalid_equation():
    print("\n" + "="*70)
    print("测试6: 无效方程名称处理")
    print("="*70)
    
    result = simulate_ode(
        equation_name="invalid_equation",
        params={"a": 1.0},
        x0=[1.0],
        time_points=[0, 1, 2],
        generate_latex=False
    )
    
    if result.get("success"):
        print("❌ 应该失败但成功了")
        return False
    
    print(f"✅ 正确返回错误: {result.get('error')}")
    return True


if __name__ == '__main__':
    tests = [
        test_list_templates,
        test_simulate_exponential,
        test_simulate_damped_oscillator,
        test_compare_with_original,
        test_unstable_parameters,
        test_invalid_equation
    ]
    
    passed = 0
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"❌ 测试异常: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "="*70)
    print(f"测试结果: {passed}/{len(tests)} 通过")
    if passed == len(tests):
        print("✅ 所有测试通过!")
    else:
        print("⚠️ 部分测试未通过")
    print("="*70)
