import numpy as np
import os

output_dir = os.path.join(os.path.dirname(__file__), '..', 'sample_data')
os.makedirs(output_dir, exist_ok=True)

def generate_exponential():
    t = np.linspace(0, 10, 50)
    r = 0.3
    x0 = 2.0
    x = x0 * np.exp(r * t)
    noise = np.random.normal(0, 0.1, len(t))
    x_noisy = x + noise
    data = np.column_stack([t, x_noisy])
    np.savetxt(os.path.join(output_dir, 'exponential_growth.csv'), data, delimiter=',', header='time,x', comments='', fmt='%.6f')
    print(f"生成指数增长数据: exponential_growth.csv (r={r})")

def generate_logistic():
    t = np.linspace(0, 20, 80)
    r = 0.5
    K = 100.0
    x0 = 2.0
    x = K / (1 + (K / x0 - 1) * np.exp(-r * t))
    noise = np.random.normal(0, 1.0, len(t))
    x_noisy = x + noise
    data = np.column_stack([t, x_noisy])
    np.savetxt(os.path.join(output_dir, 'logistic_growth.csv'), data, delimiter=',', header='time,x', comments='', fmt='%.6f')
    print(f"生成Logistic增长数据: logistic_growth.csv (r={r}, K={K})")

def generate_damped_oscillator():
    t = np.linspace(0, 10, 200)
    omega = 2.0
    zeta = 0.15
    x0 = 1.0
    v0 = 0.0
    
    omega_d = omega * np.sqrt(1 - zeta**2)
    x = x0 * np.exp(-zeta * omega * t) * (np.cos(omega_d * t) + (zeta * omega / omega_d) * np.sin(omega_d * t))
    
    noise = np.random.normal(0, 0.02, len(t))
    x_noisy = x + noise
    data = np.column_stack([t, x_noisy])
    np.savetxt(os.path.join(output_dir, 'damped_oscillation.csv'), data, delimiter=',', header='time,x', comments='', fmt='%.6f')
    print(f"生成阻尼振动数据: damped_oscillation.csv (omega={omega}, zeta={zeta})")

def generate_first_order_step():
    t = np.linspace(0, 10, 100)
    tau = 2.0
    K = 5.0
    x_final = K
    x0 = 0.0
    x = x_final + (x0 - x_final) * np.exp(-t / tau)
    noise = np.random.normal(0, 0.05, len(t))
    x_noisy = x + noise
    data = np.column_stack([t, x_noisy])
    np.savetxt(os.path.join(output_dir, 'first_order_step.csv'), data, delimiter=',', header='time,x', comments='', fmt='%.6f')
    print(f"生成一阶系统阶跃响应数据: first_order_step.csv (tau={tau}, K={K})")

def generate_linear_first_order():
    t = np.linspace(0, 5, 60)
    a = -0.5
    b = 2.0
    x0 = 1.0
    x = (x0 + b/a) * np.exp(a * t) - b/a
    noise = np.random.normal(0, 0.05, len(t))
    x_noisy = x + noise
    data = np.column_stack([t, x_noisy])
    np.savetxt(os.path.join(output_dir, 'linear_first_order.csv'), data, delimiter=',', header='time,x', comments='', fmt='%.6f')
    print(f"生成一阶线性数据: linear_first_order.csv (a={a}, b={b})")

if __name__ == '__main__':
    np.random.seed(42)
    generate_exponential()
    generate_logistic()
    generate_damped_oscillator()
    generate_first_order_step()
    generate_linear_first_order()
    print("\n所有示例数据已生成到 sample_data/ 目录")
