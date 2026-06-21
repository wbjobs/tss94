from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from .database import init_db
from .task_manager import task_manager


app = FastAPI(title="微分方程拟合工具", description="自动拟合实验数据的微分方程")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

init_db()


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
