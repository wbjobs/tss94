import urllib.request
import json
import numpy as np


def test_get_equations():
    print("=== GET /api/equations ===")
    req = urllib.request.Request('http://localhost:8000/api/equations')
    response = urllib.request.urlopen(req)
    data = json.loads(response.read())
    print('方程数量:', data['count'])
    for t in data['equations'][:3]:
        print(' -', t['display_name'])
    return True


def test_post_simulate():
    print("\n=== POST /api/simulate ===")
    t = np.linspace(0, 5, 10).tolist()
    payload = {
        'equation_name': 'exponential_growth',
        'params': {'r': 0.5},
        'x0': [1.0],
        'time_points': t,
        'original_data': [1.0, 1.6, 2.7, 4.5, 7.4, 12.2, 20.1, 33.1, 54.6, 90.0],
        'generate_latex': True
    }

    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(
        'http://localhost:8000/api/simulate',
        data=data,
        headers={'Content-Type': 'application/json'},
        method='POST'
    )
    response = urllib.request.urlopen(req)
    result = json.loads(response.read())
    
    print('success:', result['success'])
    print('is_stable:', result['is_stable'])
    print('模拟值前3个:', result['simulated_values'][:3])
    if 'comparison' in result:
        print('R²对比:', round(result['comparison']['r_squared'], 4))
    latex = result.get('latex_equation', 'N/A')
    print('LaTeX:', latex[:80] + '...' if len(latex) > 80 else latex)
    return True


def test_simulate_logistic():
    print("\n=== POST /api/simulate (Logistic) ===")
    t = np.linspace(0, 20, 30).tolist()
    payload = {
        'equation_name': 'logistic_growth',
        'params': {'r': 0.5, 'K': 100.0},
        'x0': [2.0],
        'time_points': t,
        'generate_latex': True
    }

    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(
        'http://localhost:8000/api/simulate',
        data=data,
        headers={'Content-Type': 'application/json'},
        method='POST'
    )
    response = urllib.request.urlopen(req)
    result = json.loads(response.read())
    
    print('success:', result['success'])
    print('is_stable:', result['is_stable'])
    print('最后一个值:', round(result['simulated_values'][-1], 2))
    print('LaTeX:', result.get('latex_equation', 'N/A')[:80])
    return True


if __name__ == '__main__':
    all_pass = True
    for test_func in [test_get_equations, test_post_simulate, test_simulate_logistic]:
        try:
            if not test_func():
                all_pass = False
        except Exception as e:
            print('❌ 失败:', str(e))
            all_pass = False
    
    print('\n' + '='*50)
    if all_pass:
        print('✅ 所有HTTP API测试通过')
    else:
        print('⚠️ 部分测试未通过')
