import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from backend.fitting import fit_all_equations, EQUATION_TEMPLATES


def test_high_noise_logistic():
    print("\n" + "="*70)
    print("测试: 高噪声Logistic增长数据 (噪声水平 ~15%)")
    print("="*70)
    
    np.random.seed(42)
    t = np.linspace(0, 20, 80)
    r_true = 0.5
    K_true = 100.0
    x0 = 2.0
    x_clean = K_true / (1 + (K_true / x0 - 1) * np.exp(-r_true * t))
    
    noise_std = K_true * 0.15
    noise = np.random.normal(0, noise_std, len(t))
    x_noisy = x_clean + noise
    
    print(f"真实方程: Logistic (r={r_true}, K={K_true})")
    print(f"噪声水平: {noise_std / (K_true - x0) * 100:.1f}%")
    print(f"数据点数: {len(t)}")
    
    results = fit_all_equations(t, x_noisy)
    
    if not results:
        print("❌ 没有成功拟合的方程！")
        return False
    
    print(f"\n成功拟合 {len(results)} 个方程")
    print("\n排名结果 (按综合评分排序):")
    for i, r in enumerate(results[:5]):
        stability = "✓" if r.is_stable else "⚠️"
        print(f"  {i+1}. {stability} {r.display_name}")
        print(f"       R²={r.r_squared:.4f}, Adj-R²={r.adjusted_r_squared:.4f}")
        print(f"       综合评分={r.composite_score:.4f}, 置信度={r.confidence_score*100:.1f}%")
        print(f"       复杂度惩罚={r.complexity_penalty:.3f}, 噪声惩罚={r.noise_penalty:.3f}, 稳定性惩罚={r.stability_penalty:.3f}")
        if i == 0:
            print(f"       预测参数: {r.params}")
    
    print(f"\n数据质量分析:")
    best = results[0]
    print(f"  噪声水平: {best.noise_level*100:.2f}%")
    print(f"  信噪比: {best.signal_to_noise:.2f}")
    print(f"  平滑方法: {best.smooth_method}")
    
    best_correct = 'logistic' in best.equation_name
    print(f"\n最佳方程是否正确: {'✅ 是' if best_correct else '❌ 否'} (最佳: {best.display_name})")
    
    if best.r_squared < 0.5:
        print("❌ R²过低，拟合失败")
        return False
    
    if best.confidence_score > 0.9 and best.noise_level > 0.1:
        print(f"⚠️ 警告: 高噪声下置信度虚高 ({best.confidence_score*100:.1f}%)")
    
    return True


def test_second_order_stability():
    print("\n" + "="*70)
    print("测试: 二阶方程数值稳定性")
    print("="*70)
    
    np.random.seed(42)
    t = np.linspace(0, 10, 200)
    omega_true = 2.0
    zeta_true = 0.15
    x0 = 1.0
    
    omega_d = omega_true * np.sqrt(1 - zeta_true**2)
    x_clean = x0 * np.exp(-zeta_true * omega_true * t) * np.cos(omega_d * t)
    
    noise = np.random.normal(0, 0.01, len(t))
    x_noisy = x_clean + noise
    
    print(f"真实方程: 阻尼振动 (omega={omega_true}, zeta={zeta_true})")
    print(f"数据点数: {len(t)}")
    
    results = fit_all_equations(t, x_noisy)
    
    if not results:
        print("❌ 没有成功拟合的方程！")
        return False
    
    print(f"\n成功拟合 {len(results)} 个方程")
    
    unstable_count = 0
    for r in results:
        if not r.is_stable:
            unstable_count += 1
            print(f"  ⚠️ {r.display_name}: 不稳定 - {r.stability_message}")
    
    if unstable_count > 0:
        print(f"\n共 {unstable_count}/{len(results)} 个方程被检测为不稳定并剔除")
    
    print("\n排名结果:")
    for i, r in enumerate(results[:5]):
        stability = "✓" if r.is_stable else "⚠️"
        print(f"  {i+1}. {stability} {r.display_name}")
        print(f"       R²={r.r_squared:.4f}, 综合={r.composite_score:.4f}, 置信度={r.confidence_score*100:.1f}%")
        if 'oscillator' in r.equation_name or 'damped' in r.equation_name:
            print(f"       参数: {r.params}")
    
    best = results[0]
    if best.r_squared > 0.9:
        print("\n✅ 拟合质量良好")
        return True
    else:
        print(f"\n❌ 拟合质量不足 (R²={best.r_squared:.4f})")
        return False


def test_confidence_not_overconfident():
    print("\n" + "="*70)
    print("测试: 高噪声下置信度是否虚高")
    print("="*70)
    
    np.random.seed(99)
    t = np.linspace(0, 10, 50)
    
    x = np.cumsum(np.random.normal(0, 1, len(t)))
    x = x - np.mean(x)
    
    noise_std = np.std(x) * 0.5
    x_noisy = x + np.random.normal(0, noise_std, len(t))
    
    print("输入: 纯随机游走数据 (无真实微分方程结构)")
    print(f"数据点数: {len(t)}")
    
    results = fit_all_equations(t, x_noisy)
    
    if not results:
        print("✅ 没有拟合结果（这是正确的）")
        return True
    
    best = results[0]
    print(f"\n最佳拟合: {best.display_name}")
    print(f"R² = {best.r_squared:.4f}")
    print(f"置信度 = {best.confidence_score*100:.1f}%")
    print(f"噪声水平 = {best.noise_level*100:.1f}%")
    
    if best.confidence_score > 0.7:
        print("❌ 警告: 纯随机数据置信度过高！")
        return False
    elif best.confidence_score > 0.5:
        print("⚠️ 置信度中等，需要谨慎")
        return True
    else:
        print("✅ 置信度合理降低")
        return True


if __name__ == '__main__':
    all_pass = True
    
    all_pass &= test_high_noise_logistic()
    all_pass &= test_second_order_stability()
    all_pass &= test_confidence_not_overconfident()
    
    print("\n" + "="*70)
    if all_pass:
        print("✅ 所有测试通过！")
    else:
        print("⚠️ 部分测试需要关注")
    print("="*70)
