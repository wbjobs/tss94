from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Optional
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from .database import init_db
from .task_manager import task_manager
from .fitting import get_all_templates_info, simulate_ode, compare_with_original


app = FastAPI(title="微分方程拟合工具", description="自动拟合实验数据的微分方程")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

init_db()


class SimulateRequest(BaseModel):
    equation_name: str
    params: Dict[str, float]
    x0: List[float]
    time_points: List[float]
    original_data: Optional[List[float]] = None
    generate_latex: bool = True


@app.get("/api/equations")
async def list_equations():
    return {"equations": get_all_templates_info(), "count": len(get_all_templates_info())}


@app.post("/api/simulate")
async def simulate(request: SimulateRequest):
    result = simulate_ode(
        equation_name=request.equation_name,
        params=request.params,
        x0=request.x0,
        time_points=request.time_points,
        generate_latex=request.generate_latex
    )
    
    if not result.get("success"):
        return result
    
    if request.original_data is not None:
        comparison = compare_with_original(
            result.get("simulated_values", []),
            request.original_data
        )
        if comparison.get("success"):
            result["comparison"] = comparison
    
    return result


@app.post("/api/fit")
async def submit_fit_task(file: UploadFile = File(...)):
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="只支持CSV文件")
    
    content = await file.read()
    
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="文件为空")
    
    task_id = task_manager.submit_task(file.filename, content)
    
    return {
        "task_id": task_id,
        "status": "pending",
        "message": "任务已提交，请稍后查询结果"
    }


@app.get("/api/tasks/{task_id}")
async def get_task(task_id: str):
    status = task_manager.get_task_status(task_id)
    if status is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return status


@app.get("/api/tasks/{task_id}/results")
async def get_task_results(task_id: str):
    results = task_manager.get_task_results(task_id)
    if results is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    if results["status"] == "failed":
        return results
    
    if results["status"] != "completed":
        return {
            "id": results["id"],
            "status": results["status"],
            "message": "任务尚未完成"
        }
    
    return results


@app.get("/api/tasks")
async def list_tasks(limit: int = 50):
    tasks = task_manager.list_tasks(limit=limit)
    return {"tasks": tasks, "count": len(tasks)}


@app.delete("/api/tasks/{task_id}")
async def delete_task(task_id: str):
    success = task_manager.delete_task(task_id)
    if not success:
        raise HTTPException(status_code=404, detail="任务不存在")
    return {"message": "任务已删除"}


@app.get("/api/health")
async def health_check():
    return {"status": "ok"}


static_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")
if os.path.exists(static_dir):
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
