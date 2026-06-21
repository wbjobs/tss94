import urllib.request
import json
import time
import os


def test_api():
    csv_path = os.path.join(os.path.dirname(__file__), '..', 'sample_data', 'exponential_growth.csv')
    print('正在上传文件:', csv_path)

    boundary = '----TestBoundary123'

    with open(csv_path, 'rb') as f:
        csv_data = f.read()

    body_parts = []
    body_parts.append(f'--{boundary}'.encode())
    body_parts.append(f'Content-Disposition: form-data; name="file"; filename="exponential_growth.csv"'.encode())
    body_parts.append(f'Content-Type: text/csv'.encode())
    body_parts.append(b'')
    body_parts.append(csv_data)
    body_parts.append(f'--{boundary}--'.encode())
    body_parts.append(b'')

    body = b'\r\n'.join(body_parts)

    headers = {
        'Content-Type': f'multipart/form-data; boundary={boundary}'
    }

    req = urllib.request.Request(
        'http://localhost:8000/api/fit',
        data=body,
        headers=headers,
        method='POST'
    )

    response = urllib.request.urlopen(req)
    result = json.loads(response.read())
    print('任务提交成功:', result)

    task_id = result['task_id']

    print('\n轮询任务状态...')
    for i in range(40):
        time.sleep(2)
        req = urllib.request.Request(f'http://localhost:8000/api/tasks/{task_id}')
        response = urllib.request.urlopen(req)
        status = json.loads(response.read())
        print(f'  第{i+1}次查询: {status["status"]}')
        
        if status['status'] == 'completed':
            print('\n✅ 任务完成！')
            req = urllib.request.Request(f'http://localhost:8000/api/tasks/{task_id}/results')
            response = urllib.request.urlopen(req)
            results = json.loads(response.read())
            
            best = results['results'][0]
            print(f'\n🏆 最佳方程: {best["display_name"]}')
            print(f'   R² = {best["r_squared"]:.6f}')
            print(f'   置信度 = {best["confidence_score"]*100:.1f}%')
            print(f'   LaTeX: {best["latex_equation"][:100]}...')
            print(f'   参数: {best["params"]}')
            
            print(f'\n共拟合 {len(results["results"])} 个方程:')
            for j, r in enumerate(results['results']):
                print(f'  {j+1}. {r["display_name"]} - R²: {r["r_squared"]:.6f}')
            
            return True
        elif status['status'] == 'failed':
            print(f'❌ 任务失败: {status.get("error_message", "未知错误")}')
            return False
    
    print('⏱️ 超时，任务仍在处理中')
    return False


def test_history():
    print('\n' + '='*60)
    print('测试历史任务列表')
    print('='*60)
    
    req = urllib.request.Request('http://localhost:8000/api/tasks?limit=10')
    response = urllib.request.urlopen(req)
    data = json.loads(response.read())
    
    print(f'历史任务数: {data["count"]}')
    for task in data['tasks'][:5]:
        print(f'  - {task["filename"]} ({task["status"]}) - {task["best_equation"] or "N/A"}')
    
    return data["count"] > 0


if __name__ == '__main__':
    success1 = test_api()
    success2 = test_history()
    
    print('\n' + '='*60)
    if success1 and success2:
        print('✅ 所有测试通过！')
    else:
        print('⚠️ 部分测试未通过')
    print('='*60)
