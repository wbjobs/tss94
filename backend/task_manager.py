import uuid
import json
import numpy as np
import pandas as pd
from datetime import datetime
from typing import Optional, List
from concurrent.futures import ThreadPoolExecutor, Future
import threading

from .database import SessionLocal, FitTask
from .fitting import fit_all_equations, FitResult


class TaskManager:
    def __init__(self, max_workers: int = 2):
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self._lock = threading.Lock()
        self._futures = {}

    def submit_task(self, filename: str, csv_content: bytes) -> str:
        task_id = str(uuid.uuid4())
        
        db = SessionLocal()
        try:
            task = FitTask(
                id=task_id,
                filename=filename,
                status="pending",
                data_points=0
            )
            db.add(task)
            db.commit()
        finally:
            db.close()
        
        future = self.executor.submit(self._process_task, task_id, csv_content)
        with self._lock:
            self._futures[task_id] = future
        
        return task_id

    def _process_task(self, task_id: str, csv_content: bytes):
        db = SessionLocal()
        try:
            task = db.query(FitTask).filter(FitTask.id == task_id).first()
            if not task:
                return
            
            task.status = "processing"
            db.commit()
            
            import io
            df = pd.read_csv(io.BytesIO(csv_content))
            
            if df.shape[1] < 2:
                raise ValueError("CSV文件至少需要两列：时间和数据")
            
            t_data = df.iloc[:, 0].values.astype(float)
            y_data = df.iloc[:, 1].values.astype(float)
            
            valid_mask = ~(np.isnan(t_data) | np.isnan(y_data) | np.isinf(t_data) | np.isinf(y_data))
            t_data = t_data[valid_mask]
            y_data = y_data[valid_mask]
            
            if len(t_data) < 5:
                raise ValueError("有效数据点不足（至少需要5个）")
            
            task.data_points = len(t_data)
            db.commit()
            
            results = fit_all_equations(t_data, y_data)
            
            results_dicts = []
            for r in results:
                results_dicts.append({
                    "equation_name": r.equation_name,
                    "display_name": r.display_name,
                    "params": r.params,
                    "x0": r.x0,
                    "r_squared": r.r_squared,
                    "rmse": r.rmse,
                    "aic": r.aic,
                    "bic": r.bic,
                    "fitted_curve": r.fitted_curve,
                    "time_points": r.time_points,
                    "original_data": r.original_data,
                    "latex_equation": r.latex_equation,
                    "description": r.description,
                    "order": r.order,
                    "is_best": r.is_best,
                    "confidence_score": r.confidence_score
                })
            
            task.status = "completed"
            task.completed_at = datetime.utcnow()
            task.results_json = json.dumps(results_dicts)
            
            if results_dicts:
                best = results_dicts[0]
                task.best_equation = best["display_name"]
                task.best_r_squared = best["r_squared"]
                task.confidence_score = best["confidence_score"]
            
            db.commit()
            
        except Exception as e:
            task = db.query(FitTask).filter(FitTask.id == task_id).first()
            if task:
                task.status = "failed"
                task.error_message = str(e)
                task.completed_at = datetime.utcnow()
                db.commit()
        finally:
            db.close()
            with self._lock:
                self._futures.pop(task_id, None)

    def get_task_status(self, task_id: str) -> Optional[dict]:
        db = SessionLocal()
        try:
            task = db.query(FitTask).filter(FitTask.id == task_id).first()
            if not task:
                return None
            
            result = {
                "id": task.id,
                "filename": task.filename,
                "status": task.status,
                "created_at": task.created_at.isoformat() if task.created_at else None,
                "completed_at": task.completed_at.isoformat() if task.completed_at else None,
                "data_points": task.data_points,
                "error_message": task.error_message,
                "best_equation": task.best_equation,
                "best_r_squared": task.best_r_squared,
                "confidence_score": task.confidence_score
            }
            return result
        finally:
            db.close()

    def get_task_results(self, task_id: str) -> Optional[dict]:
        db = SessionLocal()
        try:
            task = db.query(FitTask).filter(FitTask.id == task_id).first()
            if not task:
                return None
            
            results_data = None
            if task.results_json:
                results_data = json.loads(task.results_json)
            
            return {
                "id": task.id,
                "filename": task.filename,
                "status": task.status,
                "created_at": task.created_at.isoformat() if task.created_at else None,
                "completed_at": task.completed_at.isoformat() if task.completed_at else None,
                "data_points": task.data_points,
                "error_message": task.error_message,
                "best_equation": task.best_equation,
                "best_r_squared": task.best_r_squared,
                "confidence_score": task.confidence_score,
                "results": results_data
            }
        finally:
            db.close()

    def list_tasks(self, limit: int = 50) -> List[dict]:
        db = SessionLocal()
        try:
            tasks = db.query(FitTask).order_by(FitTask.created_at.desc()).limit(limit).all()
            result = []
            for task in tasks:
                result.append({
                    "id": task.id,
                    "filename": task.filename,
                    "status": task.status,
                    "created_at": task.created_at.isoformat() if task.created_at else None,
                    "completed_at": task.completed_at.isoformat() if task.completed_at else None,
                    "data_points": task.data_points,
                    "best_equation": task.best_equation,
                    "best_r_squared": task.best_r_squared,
                    "confidence_score": task.confidence_score
                })
            return result
        finally:
            db.close()

    def delete_task(self, task_id: str) -> bool:
        db = SessionLocal()
        try:
            task = db.query(FitTask).filter(FitTask.id == task_id).first()
            if not task:
                return False
            db.delete(task)
            db.commit()
            return True
        finally:
            db.close()


task_manager = TaskManager(max_workers=2)
